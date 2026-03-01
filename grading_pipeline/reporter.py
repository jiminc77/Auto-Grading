from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .models import StudentRunResult


def write_markdown_report(
    output_path: Path,
    course_name: str,
    model_split: str,
    model_grade: str,
    results: list[StudentRunResult],
) -> None:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.extend(
        [
            f"# {course_name} Automated Grading Report",
            "",
            f"- Generated at: {now}",
            f"- Split model: `{model_split}`",
            f"- Grade model: `{model_grade}`",
            f"- Students processed: `{len(results)}`",
            "",
        ]
    )

    for item in results:
        lines.extend(_render_student_section(item))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_json_snapshot(output_path: Path, results: list[StudentRunResult]) -> None:
    payload = []
    for item in results:
        payload.append(
            {
                "student_name": item.student_name,
                "submissions": [str(x.path) for x in item.submissions],
                "unit_count": item.unit_count,
                "bundles": {
                    pid: {
                        "unit_count": len(bundle.units),
                        "text_bundle_path": str(bundle.text_bundle_path) if bundle.text_bundle_path else None,
                        "merged_pdf_path": str(bundle.merged_pdf_path) if bundle.merged_pdf_path else None,
                    }
                    for pid, bundle in item.bundles.items()
                },
                "grades": {
                    pid: {
                        "parsed_score": grade.parsed_score,
                        "parsed_max_score": grade.parsed_max_score,
                        "raw_error": grade.raw_error,
                    }
                    for pid, grade in item.grades.items()
                },
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _render_student_section(item: StudentRunResult) -> list[str]:
    lines = [
        f"## Student: {item.student_name}",
        "",
        "### Submission Files",
    ]
    for submission in item.submissions:
        lines.append(f"- `{submission.path}` ({submission.kind})")
    lines.extend(
        [
            "",
            f"### Split Summary",
            f"- Total units analyzed: `{item.unit_count}`",
        ]
    )
    assigned_units = sum(len(bundle.units) for bundle in item.bundles.values())
    lines.append(f"- Unassigned units: `{max(item.unit_count - assigned_units, 0)}`")

    for problem_id, bundle in item.bundles.items():
        lines.append(
            f"- `{problem_id}`: {len(bundle.units)} unit(s), "
            f"text bundle: `{bundle.text_bundle_path}`, merged pdf: `{bundle.merged_pdf_path}`"
        )

    lines.append("")
    lines.append("### Grading Outputs")
    for problem_id, grade in item.grades.items():
        rendered = _normalize_grader_markdown(grade.response_text)
        lines.extend(
            [
                "",
                f"#### {problem_id}",
                f"- Parsed score: `{grade.parsed_score}` / `{grade.parsed_max_score}`",
            ]
        )
        if grade.raw_error:
            lines.append(f"- Error: `{grade.raw_error}`")
        lines.extend(
            [
                "",
                "##### Rendered Grading Result",
                "",
                rendered,
            ]
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def _normalize_grader_markdown(text: str | None) -> str:
    if not text or not text.strip():
        return "[Empty response]"

    normalized = text.strip()
    normalized = _strip_wrapping_code_fence(normalized)
    normalized = _demote_headings(normalized, by=2)
    return normalized


def _strip_wrapping_code_fence(text: str) -> str:
    lines = text.splitlines()
    if len(lines) < 2:
        return text

    first = lines[0].strip()
    last = lines[-1].strip()
    if not first.startswith("```") or last != "```":
        return text

    return "\n".join(lines[1:-1]).strip()


def _demote_headings(text: str, by: int = 1) -> str:
    out: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})(\s+.*)$", line)
        if match:
            level = min(len(match.group(1)) + by, 6)
            out.append("#" * level + match.group(2))
        else:
            out.append(line)
    return "\n".join(out)
