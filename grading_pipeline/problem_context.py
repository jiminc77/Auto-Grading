from __future__ import annotations

import json
from pathlib import Path


def load_problem_statement(problem_file: Path, max_chars: int = 8000) -> str:
    suffix = problem_file.suffix.lower()
    if suffix == ".ipynb":
        return _load_ipynb_statement(problem_file, max_chars=max_chars)
    text = problem_file.read_text(encoding="utf-8", errors="ignore")
    return text[:max_chars]


def _load_ipynb_statement(path: Path, max_chars: int) -> str:
    with path.open("r", encoding="utf-8") as fh:
        notebook = json.load(fh)

    lines: list[str] = []
    for cell in notebook.get("cells", []):
        cell_type = cell.get("cell_type", "")
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        if cell_type == "markdown":
            lines.append(src.strip())
        elif cell_type == "code":
            # Keep short code skeleton because some assignments include expected function names.
            snippet = src.strip()
            if len(snippet) > 1200:
                snippet = snippet[:1200] + "\n..."
            lines.append("```python\n" + snippet + "\n```")
        if sum(len(x) for x in lines) >= max_chars:
            break

    combined = "\n\n".join(lines)
    return combined[:max_chars]

