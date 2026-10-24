"""Retry counts that survive between ``kahnban run`` invocations.

A ticket that keeps coming back to the same action is escalated after ``max_attempts``.
Each count carries a fingerprint of the ticket's progress (column, branch tip, verified
commit), so a rework cycle that changes something starts counting again and only a ticket
that is stuck in one state escalates. Updates take a lock, because two runners may share
a board.
"""

from __future__ import annotations

import json
import sys
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kahnban.fsutil import exclusive, write_text_atomic

if TYPE_CHECKING:
    from kahnban.core import Config

ARTIFACT_DIR = ".artifacts"


@dataclass
class Attempt:
    count: int = 0
    last: str = "none"
    fingerprint: str = ""


def artifact_dir(config: Config) -> Path:
    """The board's git-ignored scratch directory for run state."""
    directory = config.board_path / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8", newline="\n")
    return directory


def _path(config: Config) -> Path:
    return config.board_path / ARTIFACT_DIR / "attempts.json"


def _key(action: str, ticket: str) -> str:
    return f"{action}|{ticket}"


def _locked(path: Path) -> AbstractContextManager[None]:
    return exclusive(path.with_suffix(".lock"))


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
    write_text_atomic(path, json.dumps(data, indent=2) + "\n")


def load(config: Config) -> dict[str, Attempt]:
    return _read(_path(config))


def bump(config: Config, action: str, ticket: str, fingerprint: str) -> Attempt:
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


def note(config: Config, action: str, ticket: str, last: str) -> None:
    """Remember how the latest try ended, unless the ticket's counts were cleared meanwhile."""
    path = _path(config)
    with _locked(path):
        attempts = _read(path)
        if _key(action, ticket) in attempts:
            attempts[_key(action, ticket)].last = last
            _write(path, attempts)


def clear(config: Config, ticket_id: str) -> None:
    """Forget a ticket's counts: a human or the gates have moved it on."""
    path = _path(config)
    if not path.exists():
        return
    with _locked(path):
        attempts = _read(path)
        kept = {key: value for key, value in attempts.items() if not key.endswith(f"|{ticket_id}")}
        if kept != attempts:
            _write(path, kept)
