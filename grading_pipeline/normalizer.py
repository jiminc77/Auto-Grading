from __future__ import annotations

import json
import re
from pathlib import Path

import fitz  # PyMuPDF

from .models import SubmissionFile, SubmissionUnit


def build_submission_units(
    submission_files: list[SubmissionFile],
    student_artifact_dir: Path,
    render_dpi: int,
) -> list[SubmissionUnit]:
    units: list[SubmissionUnit] = []
    raw_pages_dir = student_artifact_dir / "raw_pages"
    raw_pages_dir.mkdir(parents=True, exist_ok=True)

    ordinal = 0
    for entry in submission_files:
        if entry.kind == "pdf":
            page_units = _units_from_pdf(entry, raw_pages_dir, render_dpi, start_ordinal=ordinal)
            units.extend(page_units)
            ordinal += len(page_units)
        elif entry.kind == "ipynb":
            cell_units = _units_from_ipynb(entry, start_ordinal=ordinal)
            units.extend(cell_units)
            ordinal += len(cell_units)
        elif entry.kind == "text":
            units.append(_unit_from_text_file(entry, ordinal))
            ordinal += 1
        elif entry.kind == "image":
            units.append(_unit_from_image_file(entry, student_artifact_dir, ordinal))
            ordinal += 1

    return units


def _units_from_pdf(
    entry: SubmissionFile,
    raw_pages_dir: Path,
    render_dpi: int,
    start_ordinal: int,
) -> list[SubmissionUnit]:
    doc = fitz.open(entry.path)
    units: list[SubmissionUnit] = []
    scale = render_dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        text = page.get_text("text")
        page_png = raw_pages_dir / f"{entry.path.stem}_p{page_idx + 1:03d}.png"
        page.get_pixmap(matrix=matrix, alpha=False).save(page_png)
        units.append(
            SubmissionUnit(
                student_name=entry.student_name,
                source_path=entry.path,
                source_kind=entry.kind,
                unit_id=f"{entry.path.name}::p{page_idx + 1}",
                ordinal=start_ordinal + page_idx,
                text=_sanitize_text(text),
                page_number=page_idx + 1,
                image_path=page_png.resolve(),
            )
        )
    doc.close()
    return units


def _units_from_ipynb(entry: SubmissionFile, start_ordinal: int) -> list[SubmissionUnit]:
    with entry.path.open("r", encoding="utf-8") as fh:
        notebook = json.load(fh)

    units: list[SubmissionUnit] = []
    cell_index = 0
    for cell in notebook.get("cells", []):
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        compact = _sanitize_text(src)
        if len(compact) > 6000:
            compact = compact[:6000] + "\n..."
        units.append(
            SubmissionUnit(
                student_name=entry.student_name,
                source_path=entry.path,
                source_kind=entry.kind,
                unit_id=f"{entry.path.name}::cell{cell_index:03d}",
                ordinal=start_ordinal + len(units),
                text=compact,
            )
        )
        cell_index += 1
    return units


def _unit_from_text_file(entry: SubmissionFile, ordinal: int) -> SubmissionUnit:
    text = entry.path.read_text(encoding="utf-8", errors="ignore")
    if len(text) > 10000:
        text = text[:10000] + "\n..."
    return SubmissionUnit(
        student_name=entry.student_name,
        source_path=entry.path,
        source_kind=entry.kind,
        unit_id=f"{entry.path.name}::fulltext",
        ordinal=ordinal,
        text=_sanitize_text(text),
    )


def _unit_from_image_file(entry: SubmissionFile, student_artifact_dir: Path, ordinal: int) -> SubmissionUnit:
    image_dir = student_artifact_dir / "raw_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    output_path = image_dir / entry.path.name
    if output_path.resolve() != entry.path.resolve():
        output_path.write_bytes(entry.path.read_bytes())
    else:
        output_path = entry.path

    return SubmissionUnit(
        student_name=entry.student_name,
        source_path=entry.path,
        source_kind=entry.kind,
        unit_id=f"{entry.path.name}::image",
        ordinal=ordinal,
        text="",
        image_path=output_path.resolve(),
    )


def _sanitize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

