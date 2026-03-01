from __future__ import annotations

from pathlib import Path

from .models import SubmissionFile

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".ipynb",
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def _classify_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".ipynb":
        return "ipynb"
    if ext in {".md", ".txt"}:
        return "text"
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    return "unsupported"


def discover_students(submissions_dir: Path) -> dict[str, list[SubmissionFile]]:
    if not submissions_dir.exists():
        raise FileNotFoundError(f"Submissions directory not found: {submissions_dir}")

    discovered: dict[str, list[SubmissionFile]] = {}
    for student_dir in sorted(submissions_dir.iterdir()):
        if not student_dir.is_dir():
            continue
        student_name = student_dir.name
        files: list[SubmissionFile] = []
        for path in sorted(student_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            kind = _classify_file(path)
            if kind == "unsupported":
                continue
            files.append(SubmissionFile(student_name=student_name, path=path.resolve(), kind=kind))
        if files:
            discovered[student_name] = files
    return discovered

