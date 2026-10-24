"""File helpers shared across modules."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
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


@contextmanager
def exclusive(path: Path, *, wait: float = 10.0, stale: float = 30.0) -> Iterator[None]:
    """Hold a lock file at ``path`` while the block runs.

    Waits up to ``wait`` seconds. A lock older than ``stale`` seconds belongs to a process
    that died and is broken; the holds here last milliseconds, so ``stale`` stays far above
    any real hold and well above ``wait``. Windows reports a lock file that another process is
    deleting as ``PermissionError`` rather than ``FileExistsError``, so both mean "try again".
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait
    while True:
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except (FileExistsError, PermissionError):
            try:
                if time.time() - path.stat().st_mtime > stale:
                    path.unlink()
                    continue
            except OSError:
                continue  # it vanished between the open and the stat: the holder just finished
            if time.monotonic() > deadline:
                raise TimeoutError(f"could not lock {path}")
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass
