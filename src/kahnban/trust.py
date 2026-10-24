"""Pinned sources and signed approvals: what makes an unattended run safe to trust.

Skills and lifecycle hooks are instructions and code the factory runs with the
adopter's permissions, so ``kahnban skills lock`` records a SHA-256 of each one in
``.agents/skills.lock.json`` and ``kahnban skills check`` fails when one changes
without a re-lock. With ``require_signed_approvals`` an approval carries an HMAC over
the ticket, the reviewed tip and the reviewer, so a hand-edited ``reviewer:`` field
cannot pass the merge or done gate.

ponytail: the key is a file under .git (or ``KAHNBAN_SIGNING_KEY``). That stops edits
to board files and forged frontmatter, not a worker allowed to read .git; give
workers a sandbox without it, or keep the key in the runner's environment only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

LOCK = Path(".agents") / "skills.lock.json"
LOCKED_DIRS = (Path(".agents") / "skills", Path(".kahnban") / "hooks")
KEY_ENV = "KAHNBAN_SIGNING_KEY"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def collect(root: Path) -> dict[str, str]:
    """``{relative path: sha256}`` for every installed skill file and lifecycle hook."""
    return {
        path.relative_to(root).as_posix(): _digest(path)
        for directory in LOCKED_DIRS
        for path in sorted((root / directory).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def write_lock(root: Path) -> int:
    """Pin what is installed now; returns how many files are pinned."""
    files = collect(root)
    if not files:
        return 0
    (root / LOCK).parent.mkdir(parents=True, exist_ok=True)
    (root / LOCK).write_text(json.dumps({"version": 1, "files": files}, indent=2) + "\n", encoding="utf-8", newline="\n")
    return len(files)


def lock_problems(root: Path) -> list[str]:
    """Files that changed, appeared or vanished since they were pinned; empty when sound or unpinned."""
    path = root / LOCK
    if not path.is_file():
        return []
    try:
        pinned = json.loads(path.read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError, TypeError):
        return [f"{LOCK.as_posix()} is unreadable; re-run 'kahnban skills lock'"]
    now = collect(root)
    fix = "review the change, then run 'kahnban skills lock'"
    problems = [f"{name} changed since it was pinned; {fix}" for name in sorted(pinned.keys() & now.keys()) if pinned[name] != now[name]]
    problems += [f"{name} is not pinned; {fix}" for name in sorted(now.keys() - pinned.keys())]
    problems += [f"{name} was pinned but is gone; {fix}" for name in sorted(pinned.keys() - now.keys())]
    return problems


def _key(root: Path) -> bytes:
    from_env = os.environ.get(KEY_ENV, "").strip()
    if from_env:
        return from_env.encode()
    git_dir = root / ".git"
    if not git_dir.is_dir():
        raise ValueError(f"no signing key: set {KEY_ENV}, or run from a clone with a .git directory")
    path = git_dir / "kahnban-signing.key"
    if not path.is_file():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


def sign(root: Path, ticket_id: str, tip: str, reviewer: str) -> str:
    message = f"{ticket_id}\n{tip}\n{reviewer.strip().lower()}".encode()
    return hmac.new(_key(root), message, hashlib.sha256).hexdigest()


def signature_problem(root: Path, ticket_id: str, tip: str, reviewer: str, signature: str) -> str:
    """Why this approval cannot be trusted, or ''."""
    if not signature:
        return "approval is unsigned; a reviewer re-runs 'kahnban approve' (require_signed_approvals)"
    try:
        expected = sign(root, ticket_id, tip, reviewer)
    except ValueError as error:
        return str(error)
    if not hmac.compare_digest(expected, signature):
        return "approval signature does not match the reviewer and tip; it was edited or forged"
    return ""
