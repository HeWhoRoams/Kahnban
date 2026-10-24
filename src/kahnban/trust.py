"""Pinned sources and signed approvals: what makes an unattended run safe to trust.

Skills and lifecycle hooks are instructions and code the factory runs with the
adopter's permissions, so ``kahnban skills lock`` records a SHA-256 of each one in
``.agents/skills.lock.json`` and ``kahnban skills check`` fails when one changes
without a re-lock. With ``require_signed_approvals`` an approval carries an HMAC over
the ticket, the reviewed tip and the reviewer, so a hand-edited ``reviewer:`` field
cannot pass the merge or done gate.

The key lives in a per-user directory outside the repository (or in
``KAHNBAN_SIGNING_KEY``). A worker never signs: ``kahnban run`` strips the key from its
environment, the worker's ``approve`` records no signature, and the runner countersigns once
the review is in. The guard also refuses a worker's reads of the key.

ponytail: the key file is readable by the same OS user the worker runs as. That stops forged
frontmatter and a casual ``cat``, not a determined agent; run workers under another account
or in a container if they must not be able to reach it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

LOCK = Path(".agents") / "skills.lock.json"
LOCKED_DIRS = (Path(".agents") / "skills", Path(".kahnban") / "hooks")
KEY_ENV = "KAHNBAN_SIGNING_KEY"
KEY_DIR_ENV = "KAHNBAN_KEY_DIR"


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


def key_dir() -> Path:
    """Where signing keys live: per user, outside every repository."""
    override = os.environ.get(KEY_DIR_ENV, "").strip()
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "kahnban" / "keys"


def _key(root: Path) -> bytes:
    from_env = os.environ.get(KEY_ENV, "").strip()
    if from_env:
        return from_env.encode()
    name = hashlib.sha256(os.path.normcase(str(root.resolve())).encode()).hexdigest()[:16]
    path = key_dir() / f"{name}.key"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(secrets.token_hex(32))
    return path.read_text(encoding="utf-8").strip().encode()


@dataclass(frozen=True)
class Approval:
    """One reviewer's sign-off on one commit of one ticket."""

    ticket_id: str
    tip: str
    reviewer: str
    signature: str = ""

    @classmethod
    def from_fields(cls, fields: Mapping[str, object]) -> Approval:
        return cls(
            str(fields.get("id") or ""),
            str(fields.get("approved_sha") or "").strip(),
            str(fields.get("reviewer") or "").strip(),
            str(fields.get("approval_sig") or "").strip(),
        )


def sign(root: Path, approval: Approval) -> str:
    message = f"{approval.ticket_id}\n{approval.tip}\n{approval.reviewer.strip().lower()}".encode()
    return hmac.new(_key(root), message, hashlib.sha256).hexdigest()


def signature_problem(root: Path, approval: Approval) -> str:
    """Why this approval cannot be trusted, or ''."""
    if not approval.signature:
        return "approval is unsigned; a reviewer re-runs 'kahnban approve' (require_signed_approvals)"
    try:
        expected = sign(root, approval)
    except ValueError as error:
        return str(error)
    if not hmac.compare_digest(expected, approval.signature):
        return "approval signature does not match the reviewer and tip; it was edited or forged"
    return ""
