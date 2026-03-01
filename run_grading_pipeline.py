#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from google import genai

from grading_pipeline.config import PipelineConfig, load_pipeline_config
from grading_pipeline.discovery import discover_students
from grading_pipeline.grader import grade_problem_bundle
from grading_pipeline.models import SplitDecision, StudentRunResult
from grading_pipeline.normalizer import build_submission_units
from grading_pipeline.problem_context import load_problem_statement
from grading_pipeline.prompt_generator import ensure_prompts
from grading_pipeline.reporter import write_json_snapshot, write_markdown_report
from grading_pipeline.splitter import split_submission_units


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split-and-grade pipeline for MECE6313 submissions using Gemini."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to pipeline configuration JSON file (example: HW2/assignment_config.json).",
    )
    parser.add_argument(
        "--student",
        action="append",
        default=[],
        help="Run only selected student folder names (repeatable).",
    )
    parser.add_argument(
        "--limit-students",
        type=int,
        default=0,
        help="Process only the first N students after filtering (0 means all).",
    )
    parser.add_argument(
        "--generate-prompts",
        action="store_true",
        help="Generate prompts from assignment/problems + assignment/rubrics, then exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = _resolve_config_path(args.config)
    if config_path is None:
        return 1
    cfg = load_pipeline_config(config_path)

    selected_students = set(args.student)

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GOOGLE_API_KEY is not set.")
        print("Set it first, for example:")
        print('  export GOOGLE_API_KEY="YOUR_API_KEY_HERE"')
        return 1
    client = genai.Client(api_key=api_key)

    if args.generate_prompts:
        if not cfg.prompt_generation.enabled:
            print("ERROR: prompt_generation.enabled is false in assignment_config.json.")
            return 1
        generated = ensure_prompts(
            client=client,
            cfg=cfg,
        )
        if generated:
            print(f"[pipeline] generated prompts: {len(generated)}")
            for path in generated:
                print(f"[pipeline]   - {path}")
        else:
            print("[pipeline] prompt generation: no changes")
        print("[pipeline] generate-prompts completed.")
        return 0

    missing_prompts = [p for p in cfg.problems if not p.prompt_path.exists()]
    if missing_prompts:
        print("ERROR: Missing prompt files. Generate/review prompts first, then run grading.")
        for problem in missing_prompts:
            print(f"  - {problem.problem_id}: expected {problem.prompt_path}")
        print(
            f"Tip: run `python3 run_grading_pipeline.py --config {config_path} --generate-prompts`."
        )
        return 1

    cfg = _hydrate_problem_statements(cfg)

    discovered = discover_students(cfg.submissions_dir)
    student_names = sorted(discovered.keys())
    if selected_students:
        student_names = [name for name in student_names if name in selected_students]
    if args.limit_students > 0:
        student_names = student_names[: args.limit_students]

    if not student_names:
        print("No students found after applying filters.")
        return 1

    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    cfg.artifacts_dir.mkdir(parents=True, exist_ok=True)

    results: list[StudentRunResult] = []
    for student_name in student_names:
        print(f"[pipeline] Processing student: {student_name}")
        submissions = discovered[student_name]
        student_artifact_dir = cfg.artifacts_dir / student_name
        student_artifact_dir.mkdir(parents=True, exist_ok=True)

        units = build_submission_units(
            submission_files=submissions,
            student_artifact_dir=student_artifact_dir,
            render_dpi=cfg.split.render_dpi,
        )
        print(f"[pipeline]   normalized units: {len(units)}")

        decisions, bundles = split_submission_units(
            client=client,
            model_name=cfg.models.split_model,
            split_cfg=cfg.split,
            student_name=student_name,
            units=units,
            problems=cfg.problems,
            student_artifact_dir=student_artifact_dir,
        )

        _write_split_manifest(student_artifact_dir, decisions)

        grades = {}
        for problem in cfg.problems:
            bundle = bundles[problem.problem_id]
            print(
                f"[pipeline]   grading {problem.problem_id} "
                f"(units={len(bundle.units)}, model={cfg.models.grade_model})"
            )
            grades[problem.problem_id] = grade_problem_bundle(
                client=client,
                model_name=cfg.models.grade_model,
                grading_cfg=cfg.grading,
                bundle=bundle,
            )

        results.append(
            StudentRunResult(
                student_name=student_name,
                submissions=submissions,
                unit_count=len(units),
                bundles=bundles,
                grades=grades,
            )
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_md = cfg.results_dir / f"Grading_Report_{timestamp}.md"
    report_json = cfg.results_dir / f"Grading_Report_{timestamp}.json"
    write_markdown_report(
        output_path=report_md,
        course_name=cfg.course_name,
        model_split=cfg.models.split_model,
        model_grade=cfg.models.grade_model,
        results=results,
    )
    write_json_snapshot(report_json, results)

    print(f"[pipeline] Report written: {report_md}")
    print(f"[pipeline] JSON snapshot written: {report_json}")
    return 0


def _hydrate_problem_statements(cfg: PipelineConfig) -> PipelineConfig:
    hydrated = []
    for problem in cfg.problems:
        statement = load_problem_statement(problem.problem_path)
        hydrated.append(replace(problem, statement=statement))
    return replace(cfg, problems=hydrated)


def _write_split_manifest(student_artifact_dir: Path, decisions: dict[str, SplitDecision]) -> None:
    manifest = []
    for unit_id, decision in decisions.items():
        manifest.append(
            {
                "unit_id": unit_id,
                "problem_id": decision.problem_id,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "unit_evidence": decision.unit_evidence,
                "problem_evidence": decision.problem_evidence,
                "raw_response": decision.raw_response,
            }
        )
    output_path = student_artifact_dir / "split_manifest.json"
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _resolve_config_path(config_arg: str | None) -> Path | None:
    script_dir = Path(__file__).resolve().parent
    cwd = Path.cwd().resolve()

    if config_arg:
        path = Path(config_arg)
        if path.is_absolute() and path.exists():
            return path.resolve()
        cwd_candidate = (cwd / path).resolve()
        if cwd_candidate.exists():
            return cwd_candidate
        script_candidate = (script_dir / path).resolve()
        if script_candidate.exists():
            return script_candidate
        print(f"ERROR: Config file not found: {config_arg}")
        return None

    cwd_default = (cwd / "assignment_config.json").resolve()
    if cwd_default.exists():
        print(f"[pipeline] Using config: {cwd_default}")
        return cwd_default

    script_default = (script_dir / "assignment_config.json").resolve()
    if script_default.exists():
        print(f"[pipeline] Using config: {script_default}")
        return script_default

    discovered: list[Path] = []

    for root in {cwd, script_dir}:
        for candidate in sorted(root.glob("HW*/assignment_config.json")):
            if candidate.exists():
                discovered.append(candidate.resolve())

    unique = []
    seen = set()
    for item in discovered:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    if len(unique) == 1:
        print(f"[pipeline] Using config: {unique[0]}")
        return unique[0]

    if len(unique) == 0:
        print("ERROR: No assignment_config.json found.")
        print("Use --config, for example: --config HW2/assignment_config.json")
        return None

    print("ERROR: Multiple config files found. Please choose one with --config.")
    for path in unique:
        print(f"  - {path}")
    return None


if __name__ == "__main__":
    sys.exit(main())
