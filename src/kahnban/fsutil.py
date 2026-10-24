"""File helpers shared across modules."""

from __future__ import annotations

import os
import time
from pathlib import Path

from kahnban import frontmatter


def write_text_atomic(path: Path, text: str) -> None:
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        temp_path.write_text(frontmatter.normalize_newlines(text), encoding="utf-8", newline="\n")
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
