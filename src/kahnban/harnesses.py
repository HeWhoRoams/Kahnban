"""What each AI harness is handed: agent files, guard hooks, rules and MCP config.

The guard (``kahnban guard``) and its stop check are wired into every harness that can run a
hook. The table below says which event each harness uses; ``merge_hooks`` adds them to the
harness's own config without disturbing what is already there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kahnban import roles
from kahnban.fsutil import write_text_atomic

GUARD_COMMAND = "kahnban guard"
STOP_COMMAND = "kahnban guard --stop"
AGENT_HARNESSES = ("claude", "gemini", "cursor")
# VS Code's mcp.json schema: a stdio server is "type": "stdio" plus command/args.
VSCODE_MCP_SERVER = {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "kahnban.mcp_server", "--project-root", "${workspaceFolder}"],
}


@dataclass(frozen=True)
class HookEvent:
    event: str
    command: str
    matcher: str = ""  # which tools, for harnesses that filter by tool name
    options: dict[str, Any] = field(default_factory=dict)  # extra keys such as Cursor's loop_limit


# Claude Code and Gemini CLI nest commands under a matcher; Cursor's hooks.json is a flat list.
# Cursor's stop hook re-prompts the agent instead of blocking, so it is capped at two follow-ups.
HARNESS_HOOKS: dict[str, tuple[HookEvent, ...]] = {
    "claude": (
        HookEvent("PreToolUse", GUARD_COMMAND, "Edit|Write|MultiEdit|NotebookEdit|Bash"),
        HookEvent("Stop", STOP_COMMAND),
    ),
    "gemini": (
        HookEvent("BeforeTool", GUARD_COMMAND, "write_file|replace|run_shell_command"),
        HookEvent("AfterAgent", STOP_COMMAND),
    ),
    "cursor": (
        HookEvent("beforeShellExecution", GUARD_COMMAND),
        HookEvent("preToolUse", GUARD_COMMAND),
        HookEvent("stop", STOP_COMMAND, options={"loop_limit": 2}),
    ),
}
HOOK_FILES = {
    "claude": Path(".claude") / "settings.json",
    "gemini": Path(".gemini") / "settings.json",
    "cursor": Path(".cursor") / "hooks.json",
}


def _entry(harness: str, hook: HookEvent) -> dict[str, Any]:
    if harness == "cursor":
        return {"command": hook.command, **hook.options}
    entry: dict[str, Any] = {"hooks": [{"type": "command", "command": hook.command}]}
    return {"matcher": hook.matcher, **entry} if hook.matcher else entry


def installed_commands(harness: str, data: dict[str, Any], event: str) -> list[str]:
    """The commands a harness config already runs for ``event``."""
    entries = data.get("hooks", {}).get(event, [])
    if harness == "cursor":
        return [entry.get("command") for entry in entries]
    return [h.get("command") for entry in entries for h in entry.get("hooks", [])]


def merge_hooks(path: Path, harness: str, messages: list[str]) -> None:
    """Add the guard and stop hooks to ``path``, keeping every setting and hook already there."""
    data: dict[str, Any] = {"version": 1} if harness == "cursor" else {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            messages.append(f"{path} is not valid JSON; add the '{GUARD_COMMAND}' hooks by hand.")
            return
    added = False
    for hook in HARNESS_HOOKS[harness]:
        if hook.command not in installed_commands(harness, data, hook.event):
            data.setdefault("hooks", {}).setdefault(hook.event, []).append(_entry(harness, hook))
            added = True
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, json.dumps(data, indent=2) + "\n")


def write_agents(agents_dir: Path, harness: str = "claude") -> None:
    """Render one native agent file per worker role from the role manifest."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in roles.workers():
        write_text_atomic(agents_dir / f"{roles.agent_name(name)}.md", roles.agent_markdown(name, harness))


CURSOR_MDC_CONTENT = """---
description: Kahnban Software Factory Rules & Matt Pocock Skills
globs: *
alwaysApply: true
---
# Kahnban Engineering Protocols

Always check `.agents/state/ACTIVE_SESSION.md` before starting work and synchronize it before handing off.
For full end-to-end autonomous lifecycle execution, use `/factory-mode` (`.agents/skills/factory-mode/SKILL.md`).
When working on features or bugfixes, strictly follow the 5-stage engineering pipeline:
1. Backlog Intake: `.agents/skills/grill-with-docs/SKILL.md` (Domain alignment in GLOSSARY.md & ADR/)
2. Specification: `.agents/specs/` and `.agents/skills/to-spec/SKILL.md`
3. Granular Breakdown: `.agents/skills/to-tickets/SKILL.md` (1-3 files touched)
4. TDD in Worktrees: Work inside `.worktrees/<ID>` and follow `.agents/skills/tdd/SKILL.md`
5. Defensive Verification: Run `.agents/skills/code-review/SKILL.md` before `kahnban verify <ID>`
6. Learning & Feedback: Run `/reflect` upon completing tickets and log patterns to `./learnings/`
"""
