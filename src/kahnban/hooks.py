"""Zero-dependency lifecycle hook runner for Kahnban state transitions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kahnban import trust

HOOKS_DIR_NAME = ".kahnban/hooks"
FALLBACK_HOOKS_DIR_NAME = "plans/hooks"


@dataclass
class HookResult:
    event: str
    ticket_id: str
    executed: bool
    script_path: str | None = None
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    messages: list[str] = field(default_factory=list)


def find_hook_script(project_root: Path, event: str) -> Path | None:
    """Find hook script matching <event> in .kahnban/hooks/ or plans/hooks/."""
    candidates = [
        project_root / HOOKS_DIR_NAME,
        project_root / FALLBACK_HOOKS_DIR_NAME,
    ]
    extensions = ["", ".ps1", ".sh", ".bat", ".cmd", ".py"]

    for d in candidates:
        if not d.is_dir():
            continue
        for ext in extensions:
            target = d / f"{event}{ext}"
            if target.is_file():
                return target
    return None


def run_hook(
    project_root: Path,
    event: str,
    ticket_id: str,
    *,
    column: str = "",
    worktree: str = "",
    baton_path: str = "",
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> HookResult:
    """Execute a lifecycle hook script if present, passing structured context.

    The context arrives twice: as ``KAHNBAN_*`` environment variables, and as one
    JSON object on stdin (``event``, ``ticket``, ``column``, ``worktree``,
    ``baton_path`` plus the event's own ``payload`` fields). A ``pre-transition``
    hook that exits 2 vetoes the move; every other exit code only reports.
    """
    script = find_hook_script(project_root, event)
    if not script:
        return HookResult(
            event=event,
            ticket_id=ticket_id,
            executed=False,
            messages=[f"no hook found for {event}"],
        )
    pin_problem = trust.verify_file(project_root, script)
    if pin_problem and _strict(project_root):
        return HookResult(
            event=event,
            ticket_id=ticket_id,
            executed=True,
            script_path=str(script),
            exit_code=1,
            stderr=f"hook {event} not run: {pin_problem}",
            messages=[f"hook {event} not run: {pin_problem}"],
        )

    env = os.environ.copy()
    env["KAHNBAN_EVENT"] = str(event)
    env["KAHNBAN_TICKET"] = str(ticket_id)
    env["KAHNBAN_COLUMN"] = str(column)
    env["KAHNBAN_WORKTREE"] = str(worktree)
    env["KAHNBAN_PROJECT_ROOT"] = str(project_root)
    env["KAHNBAN_BATON_PATH"] = str(baton_path)
    if payload:
        env["KAHNBAN_PAYLOAD_JSON"] = json.dumps(payload, default=str)
    event_json = json.dumps(
        {
            "event": event,
            "ticket": ticket_id,
            "column": column,
            "worktree": worktree,
            "baton_path": baton_path,
            **(payload or {}),
        },
        default=str,
    )

    cmd: list[str] | str
    use_shell = False

    if script.suffix.lower() == ".py":
        cmd = [sys.executable, str(script)]
    elif script.suffix.lower() == ".ps1":
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
    elif script.suffix.lower() in (".bat", ".cmd"):
        cmd = [str(script)]
        use_shell = True
    elif script.suffix.lower() == ".sh":
        cmd = ["sh", str(script)]
    else:
        # Default executable / POSIX script
        cmd = [str(script)]

    try:
        completed = subprocess.run(
            cmd,
            shell=use_shell,
            cwd=str(project_root),
            input=event_json,
            capture_output=True,
            text=True,
            errors="replace",
            env=env,
            timeout=timeout,
        )
        return HookResult(
            event=event,
            ticket_id=ticket_id,
            executed=True,
            script_path=str(script),
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            messages=[f"hook {event} executed (exit {completed.returncode})", *([f"[WARN] {pin_problem}"] if pin_problem else [])],
        )
    except subprocess.TimeoutExpired as expired:
        return HookResult(
            event=event,
            ticket_id=ticket_id,
            executed=True,
            script_path=str(script),
            exit_code=124,
            stdout=expired.stdout or "" if isinstance(expired.stdout, str) else "",
            stderr=f"hook {event} timed out after {timeout}s",
            messages=[f"hook {event} timed out after {timeout}s"],
        )
    except Exception as ex:
        return HookResult(
            event=event,
            ticket_id=ticket_id,
            executed=True,
            script_path=str(script),
            exit_code=1,
            stderr=str(ex),
            messages=[f"hook {event} failed to execute: {ex}"],
        )


def _strict(project_root: Path) -> bool:
    """Whether the board asks hooks to fail closed (``strict_hooks``); a board that cannot be read is lenient."""
    try:
        from kahnban import core

        return core.load_config(project_root, check_version=False).strict_hooks
    except Exception:
        return False
