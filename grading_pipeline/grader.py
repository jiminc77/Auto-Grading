from __future__ import annotations

import re
import time
from pathlib import Path

from google.genai import types

from .api_errors import (
    explain_empty_response,
    explain_gemini_exception,
    is_model_not_found_error,
    is_transient_overload_error,
    print_once,
)
from .config import GradeConfig
from .models import GradeResult, ProblemBundle

SCORE_PATTERN = re.compile(
    r"Total:\s*\[?\s*(?P<score>\d+(?:\.\d+)?)\s*\]?\s*/\s*(?P<max>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_LOGGED_ERRORS: set[str] = set()


def grade_problem_bundle(
    client,
    model_name: str,
    grading_cfg: GradeConfig,
    bundle: ProblemBundle,
    fallback_model_names: list[str] | tuple[str, ...] | None = None,
) -> GradeResult:
    prompt_text = bundle.problem.prompt_path.read_text(encoding="utf-8")
    context_text = ""
    if bundle.text_bundle_path and bundle.text_bundle_path.exists():
        context_text = bundle.text_bundle_path.read_text(encoding="utf-8", errors="ignore")
    if len(context_text) > 120_000:
        context_text = context_text[:120_000] + "\n..."

    user_prompt = f"""
Student: {bundle.student_name}
Problem ID: {bundle.problem.problem_id}
Problem Title: {bundle.problem.title}
Max Points: {bundle.problem.max_points}

Your task:
1. Grade only this problem using the provided rubric in system instruction.
2. Use only the split materials below and attached files.
3. If evidence is missing for required rubric items, deduct strictly.
4. Keep the output format exactly as requested by the rubric prompt.

Split material text bundle:
{context_text if context_text.strip() else "[No text bundle content]"}
"""

    model_candidates = _build_model_candidates(model_name, fallback_model_names)
    last_error = None
    for model_idx, current_model in enumerate(model_candidates):
        for attempt in range(grading_cfg.max_retries + 1):
            uploads = []
            contents = [user_prompt]
            try:
                if bundle.merged_pdf_path and bundle.merged_pdf_path.exists():
                    up = client.files.upload(file=str(bundle.merged_pdf_path))
                    uploads.append(up)
                    contents.append(up)

                # For cases where no PDF pages were assigned, pass image artifacts if available.
                if not bundle.merged_pdf_path and bundle.image_paths:
                    for path in bundle.image_paths[:8]:
                        up = client.files.upload(file=str(path))
                        uploads.append(up)
                        contents.append(up)

                response = client.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=prompt_text,
                        temperature=grading_cfg.temperature,
                        thinking_config=types.ThinkingConfig(thinking_level="high"),
                    ),
                )
                text = (response.text or "").strip()
                if not text:
                    message = explain_empty_response("Grading")
                    print_once(_LOGGED_ERRORS, message, prefix="grading")
                    last_error = RuntimeError(message)
                    _maybe_wait_before_retry(
                        current_model=current_model,
                        attempt=attempt,
                        max_retries=grading_cfg.max_retries,
                        problem_id=bundle.problem.problem_id,
                        reason="empty response",
                    )
                    continue
                score, max_score = _parse_score(text)
                return GradeResult(
                    student_name=bundle.student_name,
                    problem_id=bundle.problem.problem_id,
                    prompt_path=bundle.problem.prompt_path,
                    response_text=text,
                    parsed_score=score,
                    parsed_max_score=max_score,
                )
            except Exception as exc:  # noqa: BLE001
                message = explain_gemini_exception(exc, "Grading")
                print_once(_LOGGED_ERRORS, message, prefix="grading")
                last_error = RuntimeError(message)
                if is_model_not_found_error(exc):
                    print(
                        f"[grading] WARN: model not available for {bundle.problem.problem_id}: "
                        f"{current_model}"
                    )
                    break
                if is_transient_overload_error(exc):
                    _maybe_wait_before_retry(
                        current_model=current_model,
                        attempt=attempt,
                        max_retries=grading_cfg.max_retries,
                        problem_id=bundle.problem.problem_id,
                        reason="temporary overload",
                    )
            finally:
                for uploaded in uploads:
                    try:
                        client.files.delete(name=uploaded.name)
                    except Exception:  # noqa: BLE001
                        pass

        if model_idx < len(model_candidates) - 1:
            print(
                f"[grading] WARN: switching model for {bundle.problem.problem_id} "
                f"from {current_model} to {model_candidates[model_idx + 1]}"
            )

    if last_error is not None:
        return GradeResult(
            student_name=bundle.student_name,
            problem_id=bundle.problem.problem_id,
            prompt_path=bundle.problem.prompt_path,
            response_text=f"Grading failed: {last_error}",
            parsed_score=None,
            parsed_max_score=None,
            raw_error=str(last_error),
        )

    return GradeResult(
        student_name=bundle.student_name,
        problem_id=bundle.problem.problem_id,
        prompt_path=bundle.problem.prompt_path,
        response_text="Grading failed: unknown error",
        parsed_score=None,
        parsed_max_score=None,
        raw_error="unknown error",
    )


def _parse_score(response_text: str) -> tuple[float | None, float | None]:
    match = SCORE_PATTERN.search(response_text or "")
    if not match:
        return None, None
    try:
        return float(match.group("score")), float(match.group("max"))
    except ValueError:
        return None, None


def _build_model_candidates(
    primary_model: str,
    fallback_models: list[str] | tuple[str, ...] | None,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in [primary_model] + list(fallback_models or []):
        name = str(raw).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out or [primary_model]


def _maybe_wait_before_retry(
    current_model: str,
    attempt: int,
    max_retries: int,
    problem_id: str,
    reason: str,
) -> None:
    if attempt >= max_retries:
        return
    wait_sec = min(2 ** attempt, 8)
    print(
        f"[grading] WARN: {problem_id} model={current_model} retry in {wait_sec}s "
        f"(reason: {reason})"
    )
    time.sleep(wait_sec)
