from __future__ import annotations

import json
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
                "```markdown",
                grade.response_text.strip() if grade.response_text else "[Empty response]",
                "```",
            ]
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    return lines
