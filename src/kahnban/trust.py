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

from kahnban.fsutil import write_text_atomic

LOCK = Path(".agents") / "skills.lock.json"
LOCKED_DIRS = (Path(".agents") / "skills", Path(".kahnban") / "hooks", Path("plans") / "hooks")
KEY_ENV = "KAHNBAN_SIGNING_KEY"
KEY_DIR_ENV = "KAHNBAN_KEY_DIR"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def fingerprints(root: Path) -> dict[str, str]:
    """``{relative path: sha256}`` for every installed skill file and lifecycle hook."""
    return {
        path.relative_to(root).as_posix(): _digest(path)
        for directory in LOCKED_DIRS
        for path in sorted((root / directory).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def write_lock(root: Path) -> int:
    """Pin what is installed now; returns how many files are pinned."""
    files = fingerprints(root)
    if not files:
        return 0
    write_text_atomic(root / LOCK, json.dumps({"version": 1, "files": files}, indent=2) + "\n")
    return len(files)


FIX = "review the change, then run 'kahnban skills lock'"


def _pinned(root: Path) -> dict[str, str] | None:
    """The pinned ``{path: sha256}`` map, or None when there is no lock (or it cannot be read)."""
    try:
        files = json.loads((root / LOCK).read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return files if isinstance(files, dict) else None


def drift(root: Path) -> dict[str, str]:
    """Pinned files that ``changed``, are ``unpinned`` or are ``gone``; empty when sound or unpinned."""
    if not (root / LOCK).is_file():
        return {}
    pinned = _pinned(root)
    if pinned is None:
        return {LOCK.as_posix(): "unreadable"}
    now = fingerprints(root)
    found = {name: "changed" for name in pinned.keys() & now.keys() if pinned[name] != now[name]}
    found |= {name: "unpinned" for name in now.keys() - pinned.keys()}
    found |= {name: "gone" for name in pinned.keys() - now.keys()}
    return dict(sorted(found.items()))


def lock_problems(root: Path) -> list[str]:
    """The drift in words, for ``skills check``."""
    said = {
        "changed": "changed since it was pinned",
        "unpinned": "is not pinned",
        "gone": "was pinned but is gone",
    }
    return [
        f"{LOCK.as_posix()} is unreadable; re-run 'kahnban skills lock'"
        if kind == "unreadable"
        else f"{name} {said[kind]}; {FIX}"
        for name, kind in drift(root).items()
    ]


def verify_file(root: Path, script: Path) -> str:
    """Why one file about to run does not match the lock, or '' (also when nothing is locked)."""
    pinned = _pinned(root)
    if pinned is None:
        return ""
    try:
        name = script.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""
    if not any(Path(name).is_relative_to(directory) for directory in LOCKED_DIRS):
        return ""
    if name not in pinned:
        return f"{name} is not pinned; {FIX}"
    return "" if pinned[name] == _digest(script) else f"{name} changed since it was pinned; {FIX}"


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


def _reviewers_dir(root: Path) -> Path:
    name = hashlib.sha256(os.path.normcase(str(root.resolve())).encode()).hexdigest()[:16]
    return key_dir() / "reviewers" / name


def _reviewer_file(root: Path, reviewer: str) -> Path:
    return _reviewers_dir(root) / (hashlib.sha256(reviewer.strip().lower().encode()).hexdigest()[:16] + ".json")


def register_reviewer(root: Path, reviewer: str) -> None:
    """Give ``reviewer`` a key of their own; refuses a name that already has one."""
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("a reviewer needs a name")
    path = _reviewer_file(root, reviewer)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(f"reviewer '{reviewer}' is already registered") from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"name": reviewer, "key": secrets.token_hex(32)}, handle)


def registered_reviewers(root: Path) -> list[str]:
    directory = _reviewers_dir(root)
    if not directory.is_dir():
        return []
    return sorted(json.loads(path.read_text(encoding="utf-8"))["name"] for path in directory.glob("*.json"))


def sign_reviewer(root: Path, approval: Approval) -> str:
    """The reviewer's own seal on an approval; ValueError when that name has no key."""
    path = _reviewer_file(root, approval.reviewer)
    if not path.is_file():
        raise ValueError(f"reviewer '{approval.reviewer}' is not registered; run 'kahnban reviewers add {approval.reviewer}'")
    key = json.loads(path.read_text(encoding="utf-8"))["key"].encode()
    message = f"reviewer\n{approval.ticket_id}\n{approval.tip}\n{approval.reviewer.strip().lower()}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def reviewer_problem(root: Path, approval: Approval, signature: str) -> str:
    """Why this approval is not by a registered reviewer, or ''. Empty when no reviewer is registered."""
    if not registered_reviewers(root):
        return ""
    if not signature:
        return "approval has no reviewer signature; a registered reviewer re-runs 'kahnban approve'"
    try:
        expected = sign_reviewer(root, approval)
    except ValueError as error:
        return str(error)
    return "" if hmac.compare_digest(expected, signature) else "reviewer signature does not match the reviewer and tip; it was edited or forged"


def sign_contract(root: Path, ticket_id: str, digest: str) -> str:
    """The engine's seal on one ticket's frozen contract hash."""
    return hmac.new(_key(root), f"contract\n{ticket_id}\n{digest}".encode(), hashlib.sha256).hexdigest()


def contract_problem(root: Path, ticket_id: str, digest: str, signature: str) -> str:
    """Why this frozen contract cannot be trusted, or ''. An empty signature is the caller's call."""
    try:
        expected = sign_contract(root, ticket_id, digest)
    except ValueError as error:
        return str(error)
    return "" if hmac.compare_digest(expected, signature) else "contract signature does not match its hash; the hash was edited or forged"


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
