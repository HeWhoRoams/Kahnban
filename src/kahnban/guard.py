"""``kahnban guard`` — keep a factory worker inside its role.

Installed as a Claude Code ``PreToolUse`` hook. It reads the hook's JSON from
stdin and exits 2 (block, reason on stderr) or 0 (allow). It only acts when
``KAHNBAN_ROLE`` is set, which ``kahnban run`` does for every worker it starts,
so ordinary interactive sessions are never affected.

ponytail: a tripwire against honest mistakes and casual shortcuts, not a
sandbox — a determined agent can still obfuscate a shell command. Run workers
in a container if they must not be able to touch the host.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Commands that belong to the runner or a human, never to a worker. Approving a
# spec is the one human gate in the whole flow.
RUNNER_ONLY = {"move", "merge", "done", "cleanup", "lease", "unblock", "run", "init", "spec approve"}
READ_ONLY = {
    "status", "lint", "next", "session", "handoff", "escalate", "spec", "spec list", "spec coverage",
}
ROLE_COMMANDS = {
    "coder": READ_ONLY | {"verify", "learnings"},
    "qa_reviewer": READ_ONLY | {"approve", "reject", "learnings"},
    "spec_analyst": READ_ONLY | {"ready", "new", "capture", "ingest", "spec new"},
    "curator": READ_ONLY | {"learnings", "capture", "new"},
}
OVERRIDE_FLAGS = {"--force", "--force-scope", "--force-overlap", "--abandon", "--no-verify"}
GIT_FORBIDDEN = re.compile(
    r"\bgit\b(?:\s+-C\s+\S+)?\s+(merge|push|rebase|reset\s+--hard|filter-branch|update-ref)\b"
)
GIT_COMMIT = re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+commit\b")
KAHNBAN_GLOBAL_OPTIONS = {"--project-root", "--config"}


def _kahnban_subcommands(command: str) -> list[str]:
    """Subcommands of every ``kahnban`` / ``python -m kahnban`` call in a command line."""
    try:
        tokens = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        tokens = command.split()
    found: list[str] = []
    for index, token in enumerate(tokens):
        name = Path(token.strip("\"'")).name.lower()
        if name not in ("kahnban", "kahnban.exe"):
            continue
        rest = iter(tokens[index + 1 :])
        for item in rest:
            if item in KAHNBAN_GLOBAL_OPTIONS:
                next(rest, None)
            elif not item.startswith("-"):
                command = item.lower()
                if command == "spec":  # its action decides: drafting is fine, approving is not
                    action = next((t for t in rest if not t.startswith("-")), "")
                    command = f"spec {action.lower()}".strip()
                found.append(command)
                break
    return found


def _edit_problem(role: str, path: Path, env: Mapping[str, str]) -> str | None:
    root = Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve()
    if role == "qa_reviewer":
        return "a reviewer does not edit files: approve, or reject with what to fix"
    config = core.load_config(root)
    if role == "coder":
        tree = Path(env.get("KAHNBAN_WORKTREE", "")).resolve()
        try:
            relative = path.relative_to(tree).as_posix()
        except ValueError:
            return f"{path} is outside your worktree {tree}"
        ticket = core.find_ticket(config, env.get("KAHNBAN_TICKET", ""))
        radius = core.parse_blast_radius(frontmatter.parse(ticket.text)[1])
        if core.path_within(relative, (config.board_root,)):
            return "board files are the engine's; never edit them from a ticket"
        if not core.path_within(relative, radius):
            return (
                f"{relative} is outside {ticket.ticket_id}'s blast radius "
                f"({', '.join(radius)}); report it instead of editing it"
            )
        return None
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return f"{path} is outside the project"
    allowed = {
        "spec_analyst": (config.board_root, ".agents/specs", "GLOSSARY.md", "ADR"),
        "curator": ("learnings",),
    }.get(role, ())
    if not core.path_within(relative, allowed):
        return f"a {role} may only edit {', '.join(allowed) or 'nothing'}, not {relative}"
    return None


def _bash_problem(role: str, command: str) -> str | None:
    tokens = set(command.split())
    flags = sorted(OVERRIDE_FLAGS & {token.split("=", 1)[0] for token in tokens})
    if flags:
        return f"override flags are for humans: {', '.join(flags)}"
    if GIT_FORBIDDEN.search(command):
        return "merging, pushing and rewriting history is the runner's job"
    if role == "qa_reviewer" and GIT_COMMIT.search(command):
        return "a reviewer does not commit"
    for subcommand in _kahnban_subcommands(command):
        problem = command_problem(role, subcommand)
        if problem:
            return problem
    return None


def command_problem(role: str, command: str) -> str | None:
    """Why a worker in ``role`` may not run ``kahnban <command>``, or None.

    Shared by this hook, the CLI and the MCP server, so a worker is held to its
    role whichever harness or surface it uses.
    """
    if command in RUNNER_ONLY or command not in ROLE_COMMANDS.get(role, set()):
        return f"'kahnban {command}' is not a {role}'s to run"
    return None


def decide(payload: Mapping[str, Any], env: Mapping[str, str]) -> str | None:
    """The reason to block this tool call, or None to allow it."""
    role = env.get("KAHNBAN_ROLE", "").strip()
    if not role:
        return None
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if tool in EDIT_TOOLS:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = Path(str(payload.get("cwd") or env.get("KAHNBAN_WORKTREE") or ".")) / path
        try:
            return _edit_problem(role, path.resolve(), env)
        except core.KahnbanError as error:
            return f"guard could not check this edit ({error}); refusing"
    if tool == "Bash":
        return _bash_problem(role, str(tool_input.get("command") or ""))
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    reason = decide(payload, os.environ)
    if reason:
        print(reason, file=sys.stderr)  # Claude Code already labels it with the hook's name
        return 2
    return 0
