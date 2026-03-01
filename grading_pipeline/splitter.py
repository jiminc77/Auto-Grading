from __future__ import annotations

import json
from pathlib import Path

import fitz  # PyMuPDF
from google.genai import types

from .api_errors import explain_empty_response, explain_gemini_exception, print_once
from .config import SplitConfig
from .models import ProblemBundle, ProblemSpec, SplitDecision, SubmissionUnit

_LOGGED_ERRORS: set[str] = set()


def split_submission_units(
    client,
    model_name: str,
    split_cfg: SplitConfig,
    student_name: str,
    units: list[SubmissionUnit],
    problems: list[ProblemSpec],
    student_artifact_dir: Path,
) -> tuple[dict[str, SplitDecision], dict[str, ProblemBundle]]:
    problem_ids = [p.problem_id for p in problems]
    catalog_text = _build_problem_catalog(problems)
    ordered_units = sorted(units, key=lambda x: x.ordinal)

    decisions: dict[str, SplitDecision] = {}
    for unit in ordered_units:
        decision = _classify_unit(
            client=client,
            model_name=model_name,
            split_cfg=split_cfg,
            unit=unit,
            catalog_text=catalog_text,
            allowed_problem_ids=problem_ids,
            context_hint=None,
        )
        decisions[unit.unit_id] = decision

    # Retry low-confidence/unknown with neighbor context to improve boundary assignment.
    for idx, unit in enumerate(ordered_units):
        decision = decisions[unit.unit_id]
        if decision.problem_id != split_cfg.unknown_token and decision.confidence >= split_cfg.min_confidence:
            continue
        context_hint = _neighbor_hint(ordered_units, decisions, idx, unknown_token=split_cfg.unknown_token)
        rescue = _classify_unit(
            client=client,
            model_name=model_name,
            split_cfg=split_cfg,
            unit=unit,
            catalog_text=catalog_text,
            allowed_problem_ids=problem_ids,
            context_hint=context_hint,
        )
        if rescue.problem_id != split_cfg.unknown_token and rescue.confidence >= decision.confidence:
            decisions[unit.unit_id] = rescue

    bundles = _build_problem_bundles(
        student_name=student_name,
        problems=problems,
        units=ordered_units,
        decisions=decisions,
        student_artifact_dir=student_artifact_dir,
        unknown_token=split_cfg.unknown_token,
    )
    return decisions, bundles


def build_problem_bundles(
    student_name: str,
    problems: list[ProblemSpec],
    units: list[SubmissionUnit],
    decisions: dict[str, SplitDecision],
    student_artifact_dir: Path,
    unknown_token: str,
) -> dict[str, ProblemBundle]:
    return _build_problem_bundles(
        student_name=student_name,
        problems=problems,
        units=units,
        decisions=decisions,
        student_artifact_dir=student_artifact_dir,
        unknown_token=unknown_token,
    )


def _build_problem_catalog(problems: list[ProblemSpec]) -> str:
    lines: list[str] = []
    for p in problems:
        statement = (p.statement or "").strip()
        if len(statement) > 3000:
            statement = statement[:3000] + "\n..."
        lines.append(f"Problem ID: {p.problem_id}\nTitle: {p.title}\nStatement:\n{statement}")
    return "\n\n---\n\n".join(lines)


def _neighbor_hint(
    units: list[SubmissionUnit],
    decisions: dict[str, SplitDecision],
    idx: int,
    unknown_token: str,
) -> str:
    hints: list[str] = []
    for offset in (-1, 1):
        neighbor_idx = idx + offset
        if neighbor_idx < 0 or neighbor_idx >= len(units):
            continue
        neighbor = units[neighbor_idx]
        d = decisions.get(neighbor.unit_id)
        if not d:
            continue
        if d.problem_id == unknown_token:
            continue
        hints.append(
            f"Neighbor unit {neighbor.unit_id} assigned to {d.problem_id} "
            f"(confidence={d.confidence:.2f}, evidence={d.unit_evidence[:180]!r})"
        )
    return "\n".join(hints)


def _classify_unit(
    client,
    model_name: str,
    split_cfg: SplitConfig,
    unit: SubmissionUnit,
    catalog_text: str,
    allowed_problem_ids: list[str],
    context_hint: str | None,
) -> SplitDecision:
    allowed = ", ".join(allowed_problem_ids + [split_cfg.unknown_token])
    unit_text = unit.text.strip()
    if len(unit_text) > 2500:
        unit_text = unit_text[:2500] + "\n..."

    prompt = f"""
You are classifying ONE submission unit into one homework problem.

Problem catalog (grounding source):
{catalog_text}

Allowed labels: {allowed}

Unit metadata:
- unit_id: {unit.unit_id}
- source: {unit.source_path.name}
- page_number: {unit.page_number if unit.page_number is not None else "N/A"}

Unit text (may be empty for image-only pages):
{unit_text if unit_text else "[No extracted text]"}

Neighbor context:
{context_hint if context_hint else "[None]"}

Return JSON ONLY with this exact schema:
{{
  "problem_id": "<one of allowed labels>",
  "confidence": <float between 0 and 1>,
  "reason": "<short rationale>",
  "unit_evidence": "<quote/paraphrase from unit content>",
  "problem_evidence": "<quote/paraphrase from matched problem statement>"
}}
"""

    raw = ""
    last_error = None
    for _attempt in range(split_cfg.max_retries + 1):
        uploaded = None
        try:
            contents = [prompt]
            if unit.image_path is not None and unit.image_path.exists():
                uploaded = client.files.upload(file=str(unit.image_path))
                contents.append(uploaded)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=split_cfg.temperature,
                    thinking_config=types.ThinkingConfig(thinking_level="high"),
                ),
            )
            raw = response.text or ""
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            raw = ""
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:  # noqa: BLE001
                    pass

    if last_error is not None and not raw:
        message = explain_gemini_exception(last_error, "Split")
        print_once(_LOGGED_ERRORS, message, prefix="split")
        raw = json.dumps(
            {
                "problem_id": split_cfg.unknown_token,
                "confidence": 0.0,
                "reason": message,
                "unit_evidence": "",
                "problem_evidence": "",
            }
        )
    elif not raw.strip():
        message = explain_empty_response("Split")
        print_once(_LOGGED_ERRORS, message, prefix="split")
        raw = json.dumps(
            {
                "problem_id": split_cfg.unknown_token,
                "confidence": 0.0,
                "reason": message,
                "unit_evidence": "",
                "problem_evidence": "",
            }
        )

    data = _extract_json(raw)
    problem_id = str(data.get("problem_id", split_cfg.unknown_token))
    if problem_id not in set(allowed_problem_ids + [split_cfg.unknown_token]):
        problem_id = split_cfg.unknown_token

    confidence = _safe_float(data.get("confidence"), default=0.0)
    reason = str(data.get("reason", "")).strip()
    unit_evidence = str(data.get("unit_evidence", "")).strip()
    problem_evidence = str(data.get("problem_evidence", "")).strip()

    if confidence < split_cfg.min_confidence:
        problem_id = split_cfg.unknown_token

    return SplitDecision(
        unit_id=unit.unit_id,
        problem_id=problem_id,
        confidence=max(0.0, min(1.0, confidence)),
        reason=reason,
        unit_evidence=unit_evidence,
        problem_evidence=problem_evidence,
        raw_response=raw,
    )


def _extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    chunk = text[start : end + 1]
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        return {}


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_problem_bundles(
    student_name: str,
    problems: list[ProblemSpec],
    units: list[SubmissionUnit],
    decisions: dict[str, SplitDecision],
    student_artifact_dir: Path,
    unknown_token: str,
) -> dict[str, ProblemBundle]:
    bundles = {
        p.problem_id: ProblemBundle(student_name=student_name, problem=p, units=[], decisions=[])
        for p in problems
    }

    for unit in units:
        decision = decisions[unit.unit_id]
        if decision.problem_id == unknown_token:
            continue
        bundle = bundles.get(decision.problem_id)
        if bundle is None:
            continue
        bundle.units.append(unit)
        bundle.decisions.append(decision)
        if unit.image_path is not None:
            bundle.image_paths.append(unit.image_path)

    split_root = student_artifact_dir / "split"
    for problem_id, bundle in bundles.items():
        folder_id = problem_id.lower()
        problem_dir = split_root / folder_id
        problem_dir.mkdir(parents=True, exist_ok=True)

        bundle.text_bundle_path = problem_dir / f"{folder_id}_bundle.md"
        bundle.text_bundle_path.write_text(_render_bundle_markdown(bundle), encoding="utf-8")

        pdf_path = problem_dir / f"{folder_id}_bundle.pdf"
        created_pdf = _merge_pdf_pages(bundle.units, pdf_path)
        bundle.merged_pdf_path = created_pdf

        # Keep deterministic ordering and deduplicate images.
        deduped = []
        seen = set()
        for p in sorted(bundle.image_paths, key=lambda x: str(x)):
            if str(p) in seen:
                continue
            seen.add(str(p))
            deduped.append(p)
        bundle.image_paths = deduped

    return bundles


def _render_bundle_markdown(bundle: ProblemBundle) -> str:
    lines = [
        f"# Split Bundle: {bundle.problem.problem_id}",
        "",
        f"- Student: {bundle.student_name}",
        f"- Problem: {bundle.problem.title}",
        f"- Matched units: {len(bundle.units)}",
        "",
        "## Unit Assignments",
    ]
    if not bundle.units:
        lines.append("- No units were assigned by splitter.")
        return "\n".join(lines) + "\n"

    for unit, decision in sorted(
        zip(bundle.units, bundle.decisions, strict=False), key=lambda x: x[0].ordinal
    ):
        lines.extend(
            [
                "",
                f"### {unit.unit_id}",
                f"- Source: {unit.source_path.name}",
                f"- Page: {unit.page_number if unit.page_number is not None else 'N/A'}",
                f"- Confidence: {decision.confidence:.2f}",
                f"- Reason: {decision.reason}",
                f"- Unit Evidence: {decision.unit_evidence}",
                f"- Problem Evidence: {decision.problem_evidence}",
                "",
                "```text",
                unit.text if unit.text else "[No text extracted]",
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def _merge_pdf_pages(units: list[SubmissionUnit], output_path: Path) -> Path | None:
    pdf_units = [u for u in units if u.source_kind == "pdf" and u.page_number is not None]
    if not pdf_units:
        return None

    merged = fitz.open()
    open_docs: dict[str, fitz.Document] = {}
    try:
        for unit in sorted(pdf_units, key=lambda u: u.ordinal):
            key = str(unit.source_path)
            if key not in open_docs:
                open_docs[key] = fitz.open(unit.source_path)
            src = open_docs[key]
            page_idx = unit.page_number - 1
            if 0 <= page_idx < src.page_count:
                merged.insert_pdf(src, from_page=page_idx, to_page=page_idx)
        if merged.page_count == 0:
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.save(output_path)
        return output_path.resolve()
    finally:
        merged.close()
        for doc in open_docs.values():
            doc.close()
