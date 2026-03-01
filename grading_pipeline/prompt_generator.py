from __future__ import annotations

import re
from pathlib import Path

from google.genai import types

from .api_errors import explain_empty_response, explain_gemini_exception
from .config import PipelineConfig
from .models import ProblemSpec
from .problem_context import load_problem_statement

_REQUIRED_TOKENS = [
    "# 1. Reference Solution",
    "# 2. Grading Rubric (Strict TA Mode)",
    "Ground-Truth Derivation",
    "Strict Rules",
    "Fatal Error Policy",
    "Output Format",
    "Student Answer (Verbatim, Only If Deduction Exists)",
]


def ensure_prompts(
    client,
    cfg: PipelineConfig,
) -> list[Path]:
    generated: list[Path] = []

    cfg.prompts_dir.mkdir(parents=True, exist_ok=True)
    for problem in cfg.problems:
        if problem.prompt_path.exists():
            continue

        problem_text = load_problem_statement(
            problem.problem_path, max_chars=cfg.prompt_generation.max_problem_chars
        )
        rubric_text = _load_rubric_text(problem.rubric_path, cfg.prompt_generation.max_rubric_chars)

        if client is None:
            raise ValueError("Prompt generation requires a valid Gemini client.")
        prompt_text = _generate_prompt_with_model(
            client=client,
            model_name=cfg.models.prompt_model,
            temperature=cfg.prompt_generation.temperature,
            problem=problem,
            problem_text=problem_text,
            rubric_text=rubric_text,
        )
        if not prompt_text.strip() or not _looks_like_strict_prompt(
            prompt_text, problem.problem_id
        ):
            prompt_text = _build_fallback_prompt(problem, problem_text, rubric_text)
            print(
                f"[prompt-generation] WARNING: fallback prompt used for {problem.problem_id}. "
                "Review the generated prompt before grading."
            )

        problem.prompt_path.parent.mkdir(parents=True, exist_ok=True)
        problem.prompt_path.write_text(prompt_text, encoding="utf-8")
        generated.append(problem.prompt_path)
    return generated


def _generate_prompt_with_model(
    client,
    model_name: str,
    temperature: float,
    problem: ProblemSpec,
    problem_text: str,
    rubric_text: str,
) -> str:
    system_instruction = (
        "You are writing strict, production-grade grading prompts for LLM-based TA automation."
    )
    pid = problem.problem_id.upper()
    max_points = float(problem.max_points)
    pnum = re.sub(r"[^0-9]", "", pid) or pid
    user_prompt = f"""
Create ONE grading prompt in ENGLISH ONLY for {pid}.

HARD REQUIREMENTS:
1) Grade only from explicit evidence in the student's PDF/submission.
2) No hidden-work assumptions.
3) Unreadable/OCR-ambiguous text must be treated as missing evidence.
4) Deductions are cumulative and scores are clamped to >= 0.00.
5) All scores must be printed with two decimals.
6) Fatal tag trigger must force total score to 0.00 / {max_points:.2f}.
7) Include fatal tag [{pid}_F2] for fundamental BC/IC/PDE (or core-constraint) violation.
8) Include the "Student Answer (Verbatim, Only If Deduction Exists)" section.
9) Do not use markdown tables.
10) Do not wrap the whole output in a code block.

MANDATORY TAG FAMILY:
- Analytical tags: [{pid}_A1], [{pid}_A2], ...
- Plot/implementation tags: include [{pid}_P0] and [{pid}_P1], ...
- Discussion tags: [{pid}_D1], [{pid}_D2], ...
- Fatal tags: [{pid}_F1], [{pid}_F2]

Use exactly these top-level sections:
- # 1. Reference Solution
- # 2. Grading Rubric (Strict TA Mode)

Inside section 1 include these subsections:
- ## Problem
- ## Ground-Truth Derivation (What must be recognized)
- ## Ground-Truth Implementation Evidence
- ## Ground-Truth Discussion Points

Inside section 2 include these subsections:
- ## Role
- ## Strict Rules
- ## Fatal Error Policy
- ## Point Breakdown & Deduction Tags (Max {max_points:.2f})
- ## Required Output Format

Required output-format block must include these headings:
- ### Problem {pnum} Grade
- ### Applied Deduction Tags
- ### Student Answer (Verbatim, Only If Deduction Exists)
- ### Brief Feedback
- ### Confidence

Grounding data:
Problem ID: {pid}
Problem Title: {problem.title}
Max Points: {max_points:.2f}

Problem statement:
{problem_text}

Rubric:
{rubric_text if rubric_text.strip() else "[No rubric file provided]"}
"""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[user_prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_level="high"),
            ),
        )
        text = (response.text or "").strip()
        if not text:
            print(
                f"[prompt-generation] ERROR ({problem.problem_id}): "
                f"{explain_empty_response('Prompt generation')}"
            )
            return ""
        return text
    except Exception as exc:  # noqa: BLE001
        print(
            f"[prompt-generation] ERROR ({problem.problem_id}): "
            f"{explain_gemini_exception(exc, 'Prompt generation')}"
        )
        return ""


def _build_fallback_prompt(problem: ProblemSpec, problem_text: str, rubric_text: str) -> str:
    pid = problem.problem_id.upper()
    max_points = float(problem.max_points)
    pnum = re.sub(r"[^0-9]", "", pid) or pid
    a_score, p_score, d_score = _default_category_weights(max_points)
    a_ded = _fmt(a_score / 4.0)
    p_major_ded = _fmt(p_score)
    p_minor_ded = _fmt(p_score / 2.0)
    d_ded = _fmt(d_score / 2.0)
    rubric_ref = rubric_text if rubric_text.strip() else "No rubric file provided."
    return f"""# 1. Reference Solution

## Problem
- Problem ID: `{pid}`
- Title: `{problem.title}`
- Max Points: `{max_points:.2f}`

## Official Problem Statement
{problem_text}

## Official Rubric
{rubric_ref}

## Ground-Truth Derivation (What must be recognized)
1. Correct governing-equation setup and required assumptions must be explicitly shown.
2. Required constraints (e.g., BC/IC/domain conditions) must be applied consistently.
3. Intermediate derivation logic must be visible and mathematically valid.
4. Final expression/result must be consistent with the governing equations and constraints.
5. Equivalent methods are acceptable only if they are mathematically and physically consistent.

## Ground-Truth Implementation Evidence
- Student work must include executable logic, code fragments, or explicit computational steps tied to the required result.
- Missing or unreadable code/output evidence must be treated as missing.
- Result behavior must be consistent with the analytical/physical expectation from the problem.

## Ground-Truth Discussion Points
- Student must explain the key physical/technical interpretation requested by the problem.
- Student must connect conclusions to shown equations/results, not unsupported claims.
- If a required comparison/limitation is requested, it must be addressed explicitly.

---

# 2. Grading Rubric (Strict TA Mode)

## Role
You are a strict TA grading only `{pid}` with evidence-only rules.

## Strict Rules
1. Grade only from explicit student evidence (no hidden-work assumptions).
2. Treat unreadable/OCR-ambiguous content as missing evidence.
3. Apply all matching deductions cumulatively.
4. Clamp category scores and total score to a minimum of `0.00`.
5. If a fatal tag is triggered, total score is fixed to `0.00 / {max_points:.2f}`.
6. Report all numeric scores with two decimals.

## Fatal Error Policy
- Any fatal tag (`{pid}_F*`) sets total score to `0.00 / {max_points:.2f}`.
- Include fatal tag `[{pid}_F2]` when the final answer fundamentally violates required BC/IC/PDE or core constraints.

## Point Breakdown & Deduction Tags (Max {max_points:.2f})

### Category 1: Analytical Derivation ({a_score:.2f} pts max)
- `[{pid}_A1]` (-{a_ded}): Missing or incorrect core governing equations/setup.
- `[{pid}_A2]` (-{a_ded}): Missing or incorrect boundary/constraint application.
- `[{pid}_A3]` (-{a_ded}): Missing or incorrect intermediate derivation logic.
- `[{pid}_A4]` (-{a_ded}): Missing or incorrect final analytical form/consistency.

### Category 2: Plot/Implementation ({p_score:.2f} pts max)
- `[{pid}_P0]` (-{p_major_ded}): No valid implementation/plot/result evidence for this problem.
- `[{pid}_P1]` (-{p_minor_ded}): Partial or incomplete implementation/result evidence.
- `[{pid}_P2]` (-{p_minor_ded}): Results/plots are present but fundamentally inconsistent with expected behavior.

### Category 3: Discussion ({d_score:.2f} pts max)
- `[{pid}_D1]` (-{d_ded}): Missing/incorrect physical interpretation.
- `[{pid}_D2]` (-{d_ded}): Missing/incorrect conclusion linked to the observed results.

### Fatal Tags
- `[{pid}_F1]` (-{max_points:.2f}): Submission for this problem is blank, unreadable, or irrelevant.
- `[{pid}_F2]` (-{max_points:.2f}): Fundamental contradiction with required equations/BC/IC/task constraints.

## Required Output Format
Use exactly this structure:

### Problem {pnum} Grade
- Total: `[x.xx] / {max_points:.2f}`
- Analytical Derivation: `[x.xx] / {a_score:.2f}`
- Plot/Implementation: `[x.xx] / {p_score:.2f}`
- Discussion: `[x.xx] / {d_score:.2f}`

### Applied Deduction Tags
- `[TAG] (-x.xx)`: concise reason + concrete evidence location.
- If none: `None`.

### Student Answer (Verbatim, Only If Deduction Exists)
- Include only when deductions were applied.
- Quote relevant student text verbatim.
- No translation, no paraphrase, no summary.
- If unreadable, write: `[Unreadable in submission]`.

### Brief Feedback
- 3-6 sentences in English.
- The first sentence must state the highest-impact technical issue.
- If full score, state why the response matches the reference solution.

### Confidence
- `High`, `Medium`, or `Low`.
- If not High, state what was unreadable or ambiguous.
"""


def _looks_like_strict_prompt(text: str, problem_id: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    for token in _REQUIRED_TOKENS:
        if token.lower() not in lowered:
            return False
    if "point breakdown" not in lowered and "grading rubric (max" not in lowered:
        return False
    pid = problem_id.upper()
    if "hidden-work" not in lowered and "hidden work" not in lowered:
        return False
    if "unreadable" not in lowered:
        return False
    if "clamp" not in lowered:
        return False
    if "two decimals" not in lowered and "two-decimal" not in lowered:
        return False
    if not _contains_tag(normalized, pid, "A1"):
        return False
    if not _contains_tag(normalized, pid, "P0"):
        return False
    if not _contains_tag(normalized, pid, "D1"):
        return False
    if not _contains_tag(normalized, pid, "F1") or not _contains_tag(normalized, pid, "F2"):
        return False
    if not _contains_tag_family(normalized, pid, "A"):
        return False
    if not _contains_tag_family(normalized, pid, "P"):
        return False
    if not _contains_tag_family(normalized, pid, "D"):
        return False
    if not _contains_tag_family(normalized, pid, "F"):
        return False
    return True


def _contains_tag(text: str, pid: str, suffix: str) -> bool:
    pattern = rf"(?:\[{re.escape(pid)}_{re.escape(suffix)}\]|{re.escape(pid)}_{re.escape(suffix)})(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def _contains_tag_family(text: str, pid: str, family: str) -> bool:
    pattern = rf"(?:\[{re.escape(pid)}_{re.escape(family)}\d+\]|{re.escape(pid)}_{re.escape(family)}\d+)(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def _default_category_weights(max_points: float) -> tuple[float, float, float]:
    # Derivation-heavy default split: 50%, 30%, 20%
    a = round(max_points * 0.5, 2)
    p = round(max_points * 0.3, 2)
    d = round(max_points - a - p, 2)
    if d < 0:
        d = 0.0
    return a, p, d


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def _load_rubric_text(rubric_path: Path | None, max_chars: int) -> str:
    if rubric_path is None or not rubric_path.exists():
        return ""
    text = rubric_path.read_text(encoding="utf-8", errors="ignore")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n..."
    return text.strip()
