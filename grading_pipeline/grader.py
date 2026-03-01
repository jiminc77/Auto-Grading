from __future__ import annotations

import re
from pathlib import Path

from google.genai import types

from .api_errors import explain_empty_response, explain_gemini_exception, print_once
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

    last_error = None
    for _attempt in range(grading_cfg.max_retries + 1):
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
                model=model_name,
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
        finally:
            for uploaded in uploads:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:  # noqa: BLE001
                    pass

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
