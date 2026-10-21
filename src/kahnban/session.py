"""Cross-harness session continuity: ``.agents/state/ACTIVE_SESSION.md``.

Maintains live hand-off state across different AI harnesses (Claude Code, ChatGPT,
Antigravity, Cursor) so context, in-flight worktrees, modified files, blockers,
and the next immediate shell command are never lost during mid-feature handoffs.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter, gitops

SESSION_RELATIVE = Path(".agents") / "state" / "ACTIVE_SESSION.md"
PLANS_SESSION_RELATIVE = Path("plans") / "ACTIVE_SESSION.md"


@dataclass(frozen=True)
class SubagentRecord:
    id: str
    owner: str
    worktree: str
    branch: str = ""
    title: str = ""

    def to_dict(self) -> dict[str, str]:
        res = {
            "id": self.id,
            "owner": self.owner,
            "worktree": self.worktree,
            "branch": self.branch,
        }
        if self.title:
            res["title"] = self.title
        return res

    def __getitem__(self, key: str) -> str:
        return self.get(key)

    def get(self, key: str, default: str = "") -> str:
        if key == "id":
            return self.id
        elif key == "owner":
            return self.owner
        elif key == "worktree":
            return self.worktree
        elif key == "branch":
            return self.branch
        elif key in ("title", "objective"):
            return self.title or default
        return default


@dataclass(frozen=True)
class SessionState:
    last_updated: str
    active_ticket: str
    active_worktree: str
    branch: str
    agent_harness: str
    status: str
    context: str
    subagents: list[SubagentRecord] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    blockers: str = ""
    next_commands: list[str] = field(default_factory=list)


@dataclass
class SessionUpdate:
    ticket_id: str | None = None
    branch: str | None = None
    worktree: str | None = None
    agent_harness: str | None = None
    status: str | None = None
    context: str | None = None
    blockers: str | None = None
    next_commands: Sequence[str] | None = None
    modified_files: Sequence[str] | None = None

    def apply(self, inspected: dict[str, Any], timestamp: datetime | None = None) -> SessionState:
        resolved_ticket = self.ticket_id or inspected.get("active_ticket") or ""
        resolved_branch = self.branch or inspected.get("branch") or ""
        resolved_wt = self.worktree or inspected.get("active_worktree") or ""
        resolved_harness = self.agent_harness or "generic"
        resolved_status = self.status or ("in_progress" if resolved_ticket else "idle")
        resolved_context = (self.context or "").strip()
        resolved_blockers = (self.blockers or "").strip()
        resolved_cmds = list(self.next_commands) if self.next_commands is not None else []
        resolved_mods = (
            list(self.modified_files)
            if self.modified_files is not None
            else list(inspected.get("modified_files", []))
        )

        now = (timestamp or datetime.now()).isoformat(timespec="seconds")
        return SessionState(
            last_updated=now,
            active_ticket=resolved_ticket,
            active_worktree=resolved_wt,
            branch=resolved_branch,
            agent_harness=resolved_harness,
            status=resolved_status,
            context=resolved_context,
            subagents=[
                t if isinstance(t, SubagentRecord) else SubagentRecord(
                    id=t.get("id", ""),
                    owner=t.get("owner", ""),
                    worktree=t.get("worktree", ""),
                    branch=t.get("branch", ""),
                    title=t.get("title", ""),
                )
                for t in inspected.get("in_progress_tickets", [])
            ],
            modified_files=resolved_mods,
            blockers=resolved_blockers,
            next_commands=resolved_cmds,
        )


def get_session_path(project_root: Path) -> Path:
    """Return the canonical path to ACTIVE_SESSION.md, preferring .agents/state/."""
    root = Path(project_root).resolve()
    preferred = root / SESSION_RELATIVE
    if preferred.exists() or (root / ".agents").is_dir():
        return preferred
    legacy = root / PLANS_SESSION_RELATIVE
    if legacy.exists():
        return legacy
    return preferred


def write_text_atomic(path: Path, text: str) -> None:
    """Atomically write text to path using a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp.{os.getpid()}_{time.time_ns()}"
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


def _clean_porcelain_path(line: str) -> str:
    clean = line[3:].strip() if len(line) > 3 else line.strip()
    return clean.split(" -> ")[-1].strip() if " -> " in clean else clean


def _git_modified_files(repo_path: Path) -> list[str]:
    """Helper to collect clean modified file paths from git status --porcelain."""
    if not (repo_path.is_dir() and gitops.is_repo(repo_path)):
        return []
    try:
        return [
            _clean_porcelain_path(line)
            for line in gitops.status_porcelain(repo_path)
            if _clean_porcelain_path(line)
        ]
    except Exception:
        return []


def read_session(project_root: Path) -> SessionState | None:
    """Read and parse ACTIVE_SESSION.md if present; return None if missing."""
    session_path = get_session_path(project_root)
    if not session_path.exists():
        return None
    try:
        text = session_path.read_text(encoding="utf-8")
        fields, body = frontmatter.parse(text)
    except Exception:
        return None

    context = core.section(body, "Current Context") or ""
    blockers = core.section(body, "Failing Test Traces / Blockers") or ""

    raw_sub = core.section(body, "In-Flight Sub-Agents & Worktrees") or ""
    subagents: list[dict[str, str]] = []
    has_branch_column = any(
        line.strip().startswith("|") and "branch" in line.lower()
        for line in raw_sub.splitlines()
    )
    for line in raw_sub.splitlines():
        trimmed = line.strip()
        if not trimmed.startswith("|") or trimmed.startswith("| :---"):
            continue
        cells = [c.strip().strip("`") for c in trimmed.strip("|").split("|")]
        if not cells or cells[0].lower() in ("ticket id", "id", "-"):
            continue
        t_id = cells[0] if len(cells) > 0 else ""
        owner = cells[1] if len(cells) > 1 else ""
        wt = cells[2] if len(cells) > 2 else ""
        if has_branch_column or len(cells) >= 5:
            br = cells[3] if len(cells) > 3 else ""
            obj = cells[4] if len(cells) > 4 else ""
        else:
            br = ""
            obj = cells[3] if len(cells) > 3 else ""
        if t_id and t_id != "-":
            record = SubagentRecord(id=t_id, owner=owner, worktree=wt, branch=br, title=obj if obj != "-" else "")
            subagents.append(record)

    raw_next = core.section(body, "Immediate Next Shell Commands") or ""
    next_commands: list[str] = []
    in_code = False
    for line in raw_next.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if stripped and not stripped.startswith("#"):
            next_commands.append(stripped)

    raw_files = core.section(body, "Modified Files") or ""
    modified_files: list[str] = []
    for line in raw_files.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            path_str = stripped.lstrip("-* `").rstrip("`").strip()
            if path_str and not path_str.startswith("_none"):
                modified_files.append(path_str)

    return SessionState(
        last_updated=str(fields.get("last_updated", "")),
        active_ticket=str(fields.get("active_ticket", "")),
        active_worktree=str(fields.get("active_worktree", "")),
        branch=str(fields.get("branch", "")),
        agent_harness=str(fields.get("agent_harness", "generic")),
        status=str(fields.get("status", "idle")),
        context=context.strip(),
        subagents=subagents,
        modified_files=modified_files,
        blockers=blockers.strip(),
        next_commands=next_commands,
    )


def inspect_session(config: core.Config) -> dict[str, Any]:
    """Inspect current git repo and worktrees to determine live session reality."""
    root = config.project_root
    in_progress_tickets = []
    for ticket in core.iter_tickets(config):
        if ticket.column == config.in_progress_column:
            try:
                fm, _ = frontmatter.parse(ticket.text)
            except Exception:
                fm = {}
            in_progress_tickets.append(
                {
                    "id": ticket.ticket_id,
                    "title": fm.get("title", ""),
                    "owner": fm.get("owner", "unassigned"),
                    "branch": fm.get("branch", ""),
                    "worktree": fm.get("worktree", ""),
                }
            )

    active_ticket = in_progress_tickets[0]["id"] if in_progress_tickets else ""
    active_worktree = in_progress_tickets[0]["worktree"] if in_progress_tickets else ""
    branch = in_progress_tickets[0]["branch"] if in_progress_tickets else ""

    modified_files: list[str] = []
    if active_worktree:
        modified_files = _git_modified_files(root / active_worktree)
    if not modified_files and gitops.is_repo(root):
        modified_files = _git_modified_files(root)

    return {
        "active_ticket": active_ticket,
        "active_worktree": active_worktree,
        "branch": branch,
        "in_progress_tickets": in_progress_tickets,
        "modified_files": modified_files,
    }


def write_session(
    project_root: Path,
    state: SessionState | None = None,
    *,
    active_ticket: str = "",
    active_worktree: str = "",
    branch: str = "",
    agent_harness: str = "generic",
    status_text: str = "in_progress",
    context: str = "",
    subagents: list[dict[str, str]] | None = None,
    modified_files: list[str] | None = None,
    blockers: str = "",
    next_commands: list[str] | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Write or update .agents/state/ACTIVE_SESSION.md atomically."""
    target = get_session_path(project_root)

    if state is not None:
        active_ticket = state.active_ticket
        active_worktree = state.active_worktree
        branch = state.branch
        agent_harness = state.agent_harness
        status_text = state.status
        context = state.context
        subagents = state.subagents
        modified_files = state.modified_files
        blockers = state.blockers
        next_commands = state.next_commands
        now = state.last_updated or (timestamp or datetime.now()).isoformat(timespec="seconds")
    else:
        now = (timestamp or datetime.now()).isoformat(timespec="seconds")

    lines = [
        "---",
        f'last_updated: "{now}"',
        f'active_ticket: "{active_ticket}"',
        f'active_worktree: "{active_worktree}"',
        f'branch: "{branch}"',
        f'agent_harness: "{agent_harness}"',
        f'status: "{status_text}"',
        "---",
        "",
        "# Active Session State",
        "",
        "## Current Context",
        context.strip() or "_No specific context recorded._",
        "",
        "## In-Flight Sub-Agents & Worktrees",
    ]

    sub = subagents or []
    if sub:
        lines.extend(
            [
                "| Ticket ID | Owner / Agent | Worktree Path | Branch | Objective |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for item in sub:
            t_id = item.get("id", "-")
            owner = item.get("owner", "-")
            wt = item.get("worktree", "-")
            br = item.get("branch", "-")
            obj = item.get("title") or item.get("objective", "-")
            lines.append(f"| {t_id} | {owner} | `{wt}` | `{br}` | {obj} |")
    else:
        lines.append("_No parallel sub-agents active._")
    lines.append("")

    lines.append("## Modified Files")
    mods = modified_files or []
    if mods:
        for f in mods:
            lines.append(f"- `{f}`")
    else:
        lines.append("_Working tree clean._")
    lines.append("")

    lines.append("## Failing Test Traces / Blockers")
    if blockers.strip():
        lines.append(blockers.strip())
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## Immediate Next Shell Commands")
    cmds = next_commands or []
    if cmds:
        lines.append("```bash")
        for cmd in cmds:
            lines.append(cmd)
        lines.append("```")
    else:
        lines.append("_No immediate commands queued._")
    lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    write_text_atomic(target, content)
    return target


def sync_session(
    config: core.Config,
    update: SessionUpdate | None = None,
    *,
    ticket_id: str | None = None,
    branch: str | None = None,
    worktree: str | None = None,
    agent_harness: str | None = None,
    status: str | None = None,
    context: str | None = None,
    blockers: str | None = None,
    next_commands: Sequence[str] | None = None,
    modified_files: Sequence[str] | None = None,
    timestamp: datetime | None = None,
) -> tuple[SessionState, Path]:
    """Authoritative in-process routine to inspect live state, reconcile, and persist ACTIVE_SESSION.md."""
    if update is None:
        update = SessionUpdate(
            ticket_id=ticket_id,
            branch=branch,
            worktree=worktree,
            agent_harness=agent_harness,
            status=status,
            context=context,
            blockers=blockers,
            next_commands=next_commands,
            modified_files=modified_files,
        )
    else:
        # Honor keyword argument overrides if explicitly supplied alongside update object
        if ticket_id is not None:
            update.ticket_id = ticket_id
        if branch is not None:
            update.branch = branch
        if worktree is not None:
            update.worktree = worktree
        if agent_harness is not None:
            update.agent_harness = agent_harness
        if status is not None:
            update.status = status
        if context is not None:
            update.context = context
        if blockers is not None:
            update.blockers = blockers
        if next_commands is not None:
            update.next_commands = next_commands
        if modified_files is not None:
            update.modified_files = modified_files

    inspected = inspect_session(config)
    state = update.apply(inspected, timestamp=timestamp)
    written = write_session(config.project_root, state=state, timestamp=timestamp)
    return state, written
