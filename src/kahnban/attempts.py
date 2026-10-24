"""Retry counts that survive between ``kahnban run`` invocations.

A ticket that keeps coming back to the same action is escalated after ``max_attempts``.
Each count carries a fingerprint of the ticket's progress (column, branch tip, verified
commit), so a rework cycle that changes something starts counting again and only a ticket
that is stuck in one state escalates. Updates take a lock, because two runners may share
a board.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ARTIFACT_DIR = ".artifacts"
LOCK_WAIT_SEC = 10.0
LOCK_STALE_SEC = 10.0


@dataclass
class Attempt:
    count: int = 0
    last: str = "none"
    fingerprint: str = ""


def artifact_dir(config: Any) -> Path:
    """The board's git-ignored scratch directory for run state."""
    directory = config.board_path / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8", newline="\n")
    return directory


def _path(config: Any) -> Path:
    return config.board_path / ARTIFACT_DIR / "attempts.json"


def _key(action: str, ticket: str) -> str:
    return f"{action}|{ticket}"


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    deadline = time.monotonic() + LOCK_WAIT_SEC
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE_SEC:
                    lock.unlink()
                    continue
            except OSError:
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"could not lock {lock}")
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _read(path: Path) -> dict[str, Attempt]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        return {key: Attempt(**value) for key, value in json.loads(text).items()}
    except (ValueError, TypeError, AttributeError):
        saved = path.with_name(path.name + ".corrupt")
        path.replace(saved)
        print(f"[WARN] {path.name} was unreadable; kept as {saved.name} and counting afresh", file=sys.stderr)
        return {}


def _write(path: Path, attempts: dict[str, Attempt]) -> None:
    data = {key: asdict(value) for key, value in attempts.items()}
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    temp.replace(path)


def load(config: Any) -> dict[str, Attempt]:
    return _read(_path(config))


def bump(config: Any, action: str, ticket: str, fingerprint: str) -> Attempt:
    """Count one more try at ``action``; a changed ``fingerprint`` means progress, so restart at one."""
    artifact_dir(config)
    path = _path(config)
    with _locked(path):
        attempts = _read(path)
        entry = attempts.get(_key(action, ticket)) or Attempt()
        if entry.fingerprint != fingerprint:
            entry = Attempt(fingerprint=fingerprint)
        entry.count += 1
        attempts[_key(action, ticket)] = entry
        _write(path, attempts)
        return entry


def note(config: Any, action: str, ticket: str, last: str) -> None:
    """Remember how the latest try ended, unless the ticket's counts were cleared meanwhile."""
    path = _path(config)
    with _locked(path):
        attempts = _read(path)
        if _key(action, ticket) in attempts:
            attempts[_key(action, ticket)].last = last
            _write(path, attempts)


def clear(config: Any, ticket_id: str) -> None:
    """Forget a ticket's counts: a human or the gates have moved it on."""
    path = _path(config)
    if not path.exists():
        return
    with _locked(path):
        attempts = _read(path)
        kept = {key: value for key, value in attempts.items() if not key.endswith(f"|{ticket_id}")}
        if kept != attempts:
            _write(path, kept)
