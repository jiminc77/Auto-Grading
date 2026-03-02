from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import ProblemSpec


@dataclass(frozen=True)
class ModelConfig:
    split_model: str
    grade_model: str
    prompt_model: str
    grade_fallback_models: tuple[str, ...]


@dataclass(frozen=True)
class SplitConfig:
    min_confidence: float
    render_dpi: int
    max_retries: int
    temperature: float
    unknown_token: str


@dataclass(frozen=True)
class GradeConfig:
    temperature: float
    max_retries: int


@dataclass(frozen=True)
class PromptGenerationConfig:
    enabled: bool
    temperature: float
    max_problem_chars: int
    max_rubric_chars: int


@dataclass(frozen=True)
class ReportPdfConfig:
    enabled: bool
    pdf_engine: str
    paper_size: str
    margin: str
    font_size: str
    line_spacing: float


@dataclass(frozen=True)
class PipelineConfig:
    course_name: str
    assignment_dir: Path
    problems_dir: Path
    rubrics_dir: Path
    prompts_dir: Path
    submissions_dir: Path
    results_dir: Path
    artifacts_dir: Path
    models: ModelConfig
    split: SplitConfig
    grading: GradeConfig
    prompt_generation: PromptGenerationConfig
    report_pdf: ReportPdfConfig
    problems: list[ProblemSpec]


def _resolve_path(config_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (config_dir / path).resolve()


def load_pipeline_config(config_path: Path) -> PipelineConfig:
    config_path = config_path.resolve()
    config_dir = config_path.parent
    with config_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    assignment_dir = _resolve_path(config_dir, raw.get("assignment_dir", "assignment"))
    problems_dir = _resolve_path(config_dir, raw.get("problems_dir", str(assignment_dir / "problems")))
    rubrics_dir = _resolve_path(config_dir, raw.get("rubrics_dir", str(assignment_dir / "rubrics")))
    prompts_dir = _resolve_path(config_dir, raw.get("prompts_dir", str(assignment_dir / "prompts")))

    models = raw.get("models", {})
    split = raw.get("split", {})
    grading = raw.get("grading", {})
    prompt_generation = raw.get("prompt_generation", {})
    report_pdf = raw.get("report_pdf", {})

    split_model = models.get("split_model") or models.get("grade_model") or "gemini-3.1-pro-preview"
    grade_model = models.get("grade_model") or "gemini-3.1-pro-preview"
    prompt_model = models.get("prompt_model") or grade_model
    grade_fallback_models = _normalize_model_list(models.get("grade_fallback_models"))

    problems = _load_problem_specs(
        raw=raw,
        config_dir=config_dir,
        problems_dir=problems_dir,
        rubrics_dir=rubrics_dir,
        prompts_dir=prompts_dir,
    )

    return PipelineConfig(
        course_name=raw.get("course_name", "Homework"),
        assignment_dir=assignment_dir,
        problems_dir=problems_dir,
        rubrics_dir=rubrics_dir,
        prompts_dir=prompts_dir,
        submissions_dir=_resolve_path(config_dir, raw.get("submissions_dir", "submissions")),
        results_dir=_resolve_path(config_dir, raw.get("results_dir", "results")),
        artifacts_dir=_resolve_path(config_dir, raw.get("artifacts_dir", "results/artifacts")),
        models=ModelConfig(
            split_model=split_model,
            grade_model=grade_model,
            prompt_model=prompt_model,
            grade_fallback_models=tuple(grade_fallback_models),
        ),
        split=SplitConfig(
            min_confidence=float(split.get("min_confidence", 0.55)),
            render_dpi=int(split.get("render_dpi", 180)),
            max_retries=int(split.get("max_retries", 2)),
            temperature=float(split.get("temperature", 0.5)),
            unknown_token=str(split.get("unknown_token", "UNKNOWN")),
        ),
        grading=GradeConfig(
            temperature=float(grading.get("temperature", 0.1)),
            max_retries=int(grading.get("max_retries", 2)),
        ),
        prompt_generation=PromptGenerationConfig(
            enabled=bool(prompt_generation.get("enabled", True)),
            temperature=float(prompt_generation.get("temperature", 1.0)),
            max_problem_chars=int(prompt_generation.get("max_problem_chars", 15000)),
            max_rubric_chars=int(prompt_generation.get("max_rubric_chars", 12000)),
        ),
        report_pdf=ReportPdfConfig(
            enabled=bool(report_pdf.get("enabled", True)),
            pdf_engine=str(report_pdf.get("pdf_engine", "xelatex")),
            paper_size=str(report_pdf.get("paper_size", "letterpaper")),
            margin=str(report_pdf.get("margin", "0.85in")),
            font_size=str(report_pdf.get("font_size", "10pt")),
            line_spacing=float(report_pdf.get("line_spacing", 1.12)),
        ),
        problems=problems,
    )


def _load_problem_specs(
    raw: dict,
    config_dir: Path,
    problems_dir: Path,
    rubrics_dir: Path,
    prompts_dir: Path,
) -> list[ProblemSpec]:
    if raw.get("problems"):
        return _load_problem_specs_from_config(raw["problems"], config_dir, rubrics_dir, prompts_dir)
    return _discover_problem_specs(problems_dir, rubrics_dir, prompts_dir)


def _load_problem_specs_from_config(
    rows: list[dict],
    config_dir: Path,
    rubrics_dir: Path,
    prompts_dir: Path,
) -> list[ProblemSpec]:
    specs: list[ProblemSpec] = []
    for row in rows:
        problem_path = _resolve_path(config_dir, row["problem_file"])
        inferred_number = _extract_problem_number_from_problem_stem(problem_path.stem)

        problem_id = row.get("id")
        if problem_id is None:
            if inferred_number is None:
                raise ValueError(
                    f"Cannot infer problem id from filename {problem_path.name}. "
                    "Use filename pattern problem_pN.ext or set explicit id (e.g., P1)."
                )
            problem_id = f"P{inferred_number}"

        id_number = _extract_problem_number_from_problem_id(problem_id)
        problem_number = id_number if id_number is not None else inferred_number

        rubric_path = _resolve_path(config_dir, row["rubric_file"]) if row.get("rubric_file") else None
        if rubric_path is None and problem_number is not None:
            rubric_path = _resolve_rubric_for_problem_number(rubrics_dir, problem_number)

        prompt_file = row.get("prompt_file")
        if prompt_file:
            prompt_path = _resolve_path(config_dir, prompt_file)
        else:
            if problem_number is None:
                raise ValueError(
                    f"Cannot infer prompt filename for problem id={problem_id!r}. "
                    "Set prompt_file explicitly or use id pattern Pn."
                )
            prompt_path = (prompts_dir / f"prompt_p{problem_number}.md").resolve()

        title = row.get("title") or infer_title(problem_path)
        max_points = float(row.get("max_points", _infer_max_points_from_rubric(rubric_path) or 10.0))

        specs.append(
            ProblemSpec(
                problem_id=problem_id,
                title=title,
                prompt_path=prompt_path,
                problem_path=problem_path,
                rubric_path=rubric_path,
                max_points=max_points,
            )
        )
    return _sort_problem_specs(specs)


def _discover_problem_specs(
    problems_dir: Path,
    rubrics_dir: Path,
    prompts_dir: Path,
) -> list[ProblemSpec]:
    if not problems_dir.exists():
        raise FileNotFoundError(f"Problems directory not found: {problems_dir}")

    problem_files = [
        p for p in sorted(problems_dir.iterdir()) if p.is_file() and p.suffix.lower() in {".ipynb", ".md", ".txt"}
    ]
    if not problem_files:
        raise FileNotFoundError(
            f"No problem files were found in {problems_dir}. "
            "Expected .ipynb/.md/.txt files."
        )

    rubric_map = _discover_rubrics_by_problem_number(rubrics_dir)

    specs: list[ProblemSpec] = []
    seen_problem_numbers: set[int] = set()
    for problem_path in problem_files:
        problem_number = _extract_problem_number_from_problem_stem(problem_path.stem)
        if problem_number is None:
            raise ValueError(
                f"Invalid problem filename: {problem_path.name}. "
                "Expected pattern: problem_pN.<ipynb|md|txt> (example: problem_p1.ipynb)."
            )
        if problem_number in seen_problem_numbers:
            raise ValueError(
                f"Duplicate problem number detected for P{problem_number}. "
                f"Check file naming in {problems_dir}."
            )
        seen_problem_numbers.add(problem_number)

        problem_id = f"P{problem_number}"
        rubric_path = rubric_map.get(problem_number)
        max_points = _infer_max_points_from_rubric(rubric_path) or 10.0
        specs.append(
            ProblemSpec(
                problem_id=problem_id,
                title=infer_title(problem_path),
                prompt_path=(prompts_dir / f"prompt_p{problem_number}.md").resolve(),
                problem_path=problem_path.resolve(),
                rubric_path=rubric_path.resolve() if rubric_path else None,
                max_points=float(max_points),
            )
        )
    return _sort_problem_specs(specs)


def _discover_rubrics_by_problem_number(rubrics_dir: Path) -> dict[int, Path]:
    if not rubrics_dir.exists():
        return {}

    rubric_map: dict[int, Path] = {}
    for path in sorted(rubrics_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        number = _extract_problem_number_from_rubric_stem(path.stem)
        if number is None:
            raise ValueError(
                f"Invalid rubric filename: {path.name}. "
                "Expected pattern: rubric_pN.<md|txt> (example: rubric_p1.md)."
            )
        if number in rubric_map:
            raise ValueError(
                f"Duplicate rubric for P{number}: {rubric_map[number].name} and {path.name}"
            )
        rubric_map[number] = path
    return rubric_map


def _extract_problem_number_from_problem_stem(stem: str) -> int | None:
    m = re.fullmatch(r"problem_p(\d+)", stem)
    if not m:
        return None
    return int(m.group(1))


def _extract_problem_number_from_rubric_stem(stem: str) -> int | None:
    m = re.fullmatch(r"rubric_p(\d+)", stem)
    if not m:
        return None
    return int(m.group(1))


def _extract_problem_number_from_problem_id(problem_id: str) -> int | None:
    m = re.fullmatch(r"[Pp](\d+)", str(problem_id).strip())
    if not m:
        return None
    return int(m.group(1))


def _resolve_rubric_for_problem_number(rubrics_dir: Path, problem_number: int) -> Path | None:
    md = rubrics_dir / f"rubric_p{problem_number}.md"
    if md.exists():
        return md.resolve()
    txt = rubrics_dir / f"rubric_p{problem_number}.txt"
    if txt.exists():
        return txt.resolve()
    return None


def infer_title(problem_path: Path) -> str:
    stem = problem_path.stem
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return stem.title() if stem else problem_path.name


def _infer_max_points_from_rubric(rubric_path: Path | None) -> float | None:
    if rubric_path is None or not rubric_path.exists():
        return None
    text = rubric_path.read_text(encoding="utf-8", errors="ignore")
    # Prefer explicit "Problem X (Y pts)" if available.
    m = re.search(r"\((\d+(?:\.\d+)?)\s*pts?\)", text, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Fallback to first numeric with pts token.
    m = re.search(r"(\d+(?:\.\d+)?)\s*pts?\b", text, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _sort_problem_specs(specs: list[ProblemSpec]) -> list[ProblemSpec]:
    def sort_key(item: ProblemSpec):
        m = re.search(r"(\d+)$", item.problem_id)
        if m:
            return (0, int(m.group(1)), item.problem_id)
        return (1, 10**9, item.problem_id)

    return sorted(specs, key=sort_key)


def _normalize_model_list(value) -> list[str]:
    if not value:
        return ["gemini-3-flash"]
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(x) for x in value]
    else:
        return ["gemini-3-flash"]

    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        name = str(raw).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out or ["gemini-3-flash"]
