#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> int:
    hw_number = input("Enter homework number (example: 3): ").strip()
    if not re.fullmatch(r"\d+", hw_number):
        print(f"ERROR: Invalid homework number: {hw_number!r}")
        return 1

    root = Path(__file__).resolve().parent
    hw_name = f"HW{int(hw_number)}"
    hw_dir = root / hw_name
    assignment_dir = hw_dir / "assignment"
    problems_dir = assignment_dir / "problems"
    rubrics_dir = assignment_dir / "rubrics"
    prompts_dir = assignment_dir / "prompts"
    submissions_dir = hw_dir / "submissions"
    results_dir = hw_dir / "results"
    artifacts_dir = results_dir / "artifacts"
    config_path = hw_dir / "assignment_config.json"

    for path in [
        hw_dir,
        assignment_dir,
        problems_dir,
        rubrics_dir,
        prompts_dir,
        submissions_dir,
        results_dir,
        artifacts_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        answer = input(
            f"Config already exists at {config_path}. Overwrite? [y/N]: "
        ).strip().lower()
        if answer in {"y", "yes"}:
            config_path.write_text(json.dumps(_default_assignment_config(), indent=2) + "\n", encoding="utf-8")
            print(f"[create-homework] Overwrote config: {config_path}")
        else:
            print(f"[create-homework] Kept existing config: {config_path}")
    else:
        config_path.write_text(json.dumps(_default_assignment_config(), indent=2) + "\n", encoding="utf-8")
        print(f"[create-homework] Wrote config: {config_path}")

    print(f"[create-homework] Homework folder ready: {hw_dir}")
    print("[create-homework] Naming rules:")
    print("  - problems: problem_pN.ipynb (or .md/.txt)")
    print("  - rubrics:  rubric_pN.md (or .txt)")
    print("  - prompts:  prompt_pN.md (generated)")
    print("[create-homework] Next steps:")
    print(f"  1) Add problems into {problems_dir}")
    print(f"  2) Add rubrics (.md/.txt) into {rubrics_dir}")
    print(f"  3) Add student folders/files into {submissions_dir}")
    print(
        f"  4) Generate prompts: python3 run_grading_pipeline.py --config {hw_name}/assignment_config.json --generate-prompts"
    )
    print(
        f"  5) Review prompts in {prompts_dir}"
    )
    print(
        f"  6) Run grading: python3 run_grading_pipeline.py --config {hw_name}/assignment_config.json"
    )
    return 0


def _default_assignment_config() -> dict:
    return {
        "course_name": "MECE6313",
        "assignment_dir": "assignment",
        "problems_dir": "assignment/problems",
        "rubrics_dir": "assignment/rubrics",
        "prompts_dir": "assignment/prompts",
        "submissions_dir": "submissions",
        "results_dir": "results",
        "artifacts_dir": "results/artifacts",
        "models": {
            "split_model": "gemini-3.1-pro-preview",
            "grade_model": "gemini-3.1-pro-preview",
            "prompt_model": "gemini-3.1-pro-preview",
        },
        "split": {
            "min_confidence": 0.55,
            "render_dpi": 180,
            "max_retries": 2,
            "temperature": 0.5,
            "unknown_token": "UNKNOWN",
        },
        "grading": {
            "temperature": 0.1,
            "max_retries": 2,
        },
        "prompt_generation": {
            "enabled": True,
            "temperature": 0.7,
            "max_problem_chars": 15000,
            "max_rubric_chars": 12000,
        },
        "report_pdf": {
            "enabled": True,
            "pdf_engine": "xelatex",
            "paper_size": "letterpaper",
            "margin": "0.85in",
            "font_size": "10pt",
            "line_spacing": 1.12,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
