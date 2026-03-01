from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProblemSpec:
    problem_id: str
    title: str
    prompt_path: Path
    problem_path: Path
    rubric_path: Optional[Path]
    max_points: float
    statement: str = ""


@dataclass(frozen=True)
class SubmissionFile:
    student_name: str
    path: Path
    kind: str


@dataclass
class SubmissionUnit:
    student_name: str
    source_path: Path
    source_kind: str
    unit_id: str
    ordinal: int
    text: str = ""
    page_number: Optional[int] = None
    image_path: Optional[Path] = None


@dataclass
class SplitDecision:
    unit_id: str
    problem_id: str
    confidence: float
    reason: str
    unit_evidence: str
    problem_evidence: str
    raw_response: str = ""


@dataclass
class ProblemBundle:
    student_name: str
    problem: ProblemSpec
    units: list[SubmissionUnit] = field(default_factory=list)
    decisions: list[SplitDecision] = field(default_factory=list)
    text_bundle_path: Optional[Path] = None
    merged_pdf_path: Optional[Path] = None
    image_paths: list[Path] = field(default_factory=list)


@dataclass
class GradeResult:
    student_name: str
    problem_id: str
    prompt_path: Path
    response_text: str
    parsed_score: Optional[float]
    parsed_max_score: Optional[float]
    raw_error: Optional[str] = None


@dataclass
class StudentRunResult:
    student_name: str
    submissions: list[SubmissionFile]
    unit_count: int
    bundles: dict[str, ProblemBundle]
    grades: dict[str, GradeResult]
