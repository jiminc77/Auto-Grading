from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .models import GradeResult, ProblemBundle, ProblemSpec, StudentRunResult, SubmissionFile, SubmissionUnit


def load_completed_student_results(
    checkpoint_dir: Path,
    student_names: list[str],
) -> dict[str, StudentRunResult]:
    out: dict[str, StudentRunResult] = {}
    for student_name in student_names:
        path = _checkpoint_path(checkpoint_dir, student_name)
        if not path.exists():
            continue
        data = _read_json(path)
        if not data:
            continue
        if str(data.get("status", "")).lower() != "completed":
            continue
        parsed = _deserialize_student_result(data)
        if parsed is None:
            continue
        out[student_name] = parsed
    return out


def mark_student_in_progress(
    checkpoint_dir: Path,
    student_name: str,
    submissions: list[SubmissionFile],
) -> None:
    payload = {
        "version": 1,
        "status": "in_progress",
        "updated_at": _now_iso(),
        "student_name": student_name,
        "submissions": _serialize_submissions(submissions),
    }
    _write_json(_checkpoint_path(checkpoint_dir, student_name), payload)


def mark_student_failed(
    checkpoint_dir: Path,
    student_name: str,
    submissions: list[SubmissionFile],
    error: str,
) -> None:
    payload = {
        "version": 1,
        "status": "failed",
        "updated_at": _now_iso(),
        "student_name": student_name,
        "submissions": _serialize_submissions(submissions),
        "error": error,
    }
    _write_json(_checkpoint_path(checkpoint_dir, student_name), payload)


def mark_student_completed(
    checkpoint_dir: Path,
    result: StudentRunResult,
) -> None:
    payload = _serialize_student_result(result)
    payload["status"] = "completed"
    payload["updated_at"] = _now_iso()
    _write_json(_checkpoint_path(checkpoint_dir, result.student_name), payload)


def _serialize_student_result(result: StudentRunResult) -> dict:
    bundles = {}
    for problem_id, bundle in result.bundles.items():
        bundles[problem_id] = {
            "unit_count": len(bundle.units),
            "text_bundle_path": str(bundle.text_bundle_path) if bundle.text_bundle_path else None,
            "merged_pdf_path": str(bundle.merged_pdf_path) if bundle.merged_pdf_path else None,
        }
    grades = {}
    for problem_id, grade in result.grades.items():
        grades[problem_id] = {
            "problem_id": grade.problem_id,
            "prompt_path": str(grade.prompt_path),
            "response_text": grade.response_text,
            "parsed_score": grade.parsed_score,
            "parsed_max_score": grade.parsed_max_score,
            "raw_error": grade.raw_error,
        }
    return {
        "version": 1,
        "student_name": result.student_name,
        "submissions": _serialize_submissions(result.submissions),
        "unit_count": result.unit_count,
        "bundles": bundles,
        "grades": grades,
    }


def _deserialize_student_result(data: dict) -> StudentRunResult | None:
    student_name = str(data.get("student_name", "")).strip()
    if not student_name:
        return None

    submissions = []
    for row in data.get("submissions", []):
        try:
            submissions.append(
                SubmissionFile(
                    student_name=student_name,
                    path=Path(str(row.get("path", ""))),
                    kind=str(row.get("kind", "unknown")),
                )
            )
        except Exception:  # noqa: BLE001
            continue

    grades_raw = data.get("grades", {})
    grades: dict[str, GradeResult] = {}
    for problem_id, row in grades_raw.items():
        prompt_path = Path(str(row.get("prompt_path", ".")))
        grades[problem_id] = GradeResult(
            student_name=student_name,
            problem_id=str(row.get("problem_id", problem_id)),
            prompt_path=prompt_path,
            response_text=str(row.get("response_text", "")),
            parsed_score=_to_float_or_none(row.get("parsed_score")),
            parsed_max_score=_to_float_or_none(row.get("parsed_max_score")),
            raw_error=_to_str_or_none(row.get("raw_error")),
        )

    bundles: dict[str, ProblemBundle] = {}
    for problem_id, row in data.get("bundles", {}).items():
        unit_count = int(row.get("unit_count", 0) or 0)
        max_points = _infer_max_points(problem_id, grades)
        problem = ProblemSpec(
            problem_id=problem_id,
            title=problem_id,
            prompt_path=Path("."),
            problem_path=Path("."),
            rubric_path=None,
            max_points=max_points,
        )
        units = [
            SubmissionUnit(
                student_name=student_name,
                source_path=Path("."),
                source_kind="checkpoint",
                unit_id=f"checkpoint_{problem_id}_{idx+1}",
                ordinal=idx + 1,
                text="",
            )
            for idx in range(max(unit_count, 0))
        ]
        bundles[problem_id] = ProblemBundle(
            student_name=student_name,
            problem=problem,
            units=units,
            decisions=[],
            text_bundle_path=_to_path_or_none(row.get("text_bundle_path")),
            merged_pdf_path=_to_path_or_none(row.get("merged_pdf_path")),
            image_paths=[],
        )

    return StudentRunResult(
        student_name=student_name,
        submissions=submissions,
        unit_count=int(data.get("unit_count", 0) or 0),
        bundles=bundles,
        grades=grades,
    )


def _infer_max_points(problem_id: str, grades: dict[str, GradeResult]) -> float:
    grade = grades.get(problem_id)
    if grade is None or grade.parsed_max_score is None:
        return 0.0
    return float(grade.parsed_max_score)


def _serialize_submissions(submissions: list[SubmissionFile]) -> list[dict]:
    return [
        {
            "path": str(item.path),
            "kind": item.kind,
        }
        for item in submissions
    ]


def _checkpoint_path(checkpoint_dir: Path, student_name: str) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_file_token(student_name)
    return checkpoint_dir / f"{safe}.json"


def _safe_file_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return token or "student"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _to_float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_str_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_path_or_none(value) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
