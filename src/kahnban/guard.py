"""``kahnban guard`` — keep a factory worker inside its role.

Installed as a Claude Code ``PreToolUse`` hook, and as the equivalent hook in Gemini CLI
(``BeforeTool``) and Cursor (``beforeShellExecution``, ``preToolUse``). It reads the hook's JSON from
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

from kahnban import core, frontmatter, gitops, roles

# Tool names differ per harness: Claude Code, Gemini CLI, Cursor.
EDIT_TOOLS = {
    "Edit", "Write", "MultiEdit", "NotebookEdit",
    "write_file", "replace",
    "StrReplace", "Delete", "EditNotebook",
}
SHELL_TOOLS = {"Bash", "run_shell_command", "Shell"}
PATH_KEYS = ("file_path", "notebook_path", "path", "target_file")
# Which commands and files each role gets lives in templates/roles.json.
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
    scope = roles.edits(role)
    if not scope:
        hint = f" {roles.finish(role, env.get('KAHNBAN_TICKET', ''))}" if role in roles.workers() else ""
        return f"a {role} does not edit files.{hint}"
    config = core.load_config(root)
    if scope == "blast_radius":
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
    allowed = tuple(config.board_root if entry == "{board}" else entry for entry in scope)
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
    if not roles.edits(role) and GIT_COMMIT.search(command):
        return f"a {role} does not commit"
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
    if command in roles.runner_only() or command not in roles.commands(role):
        return f"'kahnban {command}' is not a {role}'s to run"
    return None


def decide(payload: Mapping[str, Any], env: Mapping[str, str]) -> str | None:
    """The reason to block this tool call, or None to allow it."""
    role = env.get("KAHNBAN_ROLE", "").strip()
    if not role:
        return None
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if not tool and "command" in payload:  # Cursor's beforeShellExecution has no tool name
        tool, tool_input = "Bash", {"command": payload["command"]}
    if tool in EDIT_TOOLS:
        raw = next((tool_input[key] for key in PATH_KEYS if tool_input.get(key)), "")
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = Path(str(payload.get("cwd") or env.get("KAHNBAN_WORKTREE") or ".")) / path
        try:
            return _edit_problem(role, path.resolve(), env)
        except core.KahnbanError as error:
            return f"guard could not check this edit ({error}); refusing"
    if tool in SHELL_TOOLS:
        return _bash_problem(role, str(tool_input.get("command") or ""))
    return None


def exit_problem(role: str, env: Mapping[str, str]) -> str | None:
    """Why a worker in ``role`` may not stop yet, or None.

    Escalating is always a valid way out. Otherwise a coder must leave every change
    committed, inside the blast radius, with at least one commit on its branch; a
    reviewer must have approved or rejected; a spec analyst's ticket must pass the
    ready gate. The runner still checks the board itself after the worker exits.
    """
    if role not in ("coder", "qa_reviewer", "spec_analyst"):
        return None
    config = core.load_config(Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve())
    ticket = core.find_ticket(config, env.get("KAHNBAN_TICKET", ""))
    fields, body = frontmatter.parse(ticket.text)
    if str(fields.get("blocked_on") or "").strip():
        return None
    if role == "coder":
        tree = Path(env.get("KAHNBAN_WORKTREE", "")).resolve()
        branch = core.ticket_branch(fields, ticket.ticket_id)
        try:
            core._require_clean_tip(config, tree, branch)
        except core.GateError as error:
            return str(error)
        offenders, _ = core._diff_scope_problems(config, ticket, fields, core.parse_blast_radius(body))
        if offenders:
            return f"{branch} changes files outside the blast radius: {', '.join(offenders)}"
        default = gitops.default_branch(config.project_root)
        ahead = gitops.run(tree, ["rev-list", "--count", f"{default}..HEAD"]).stdout.strip()
        if ahead == "0":
            return f"{branch} has no commits yet: finish the work and commit it, or escalate"
    elif role == "qa_reviewer":
        if ticket.column == config.verifying_column and not str(fields.get("reviewer") or "").strip():
            return f"{ticket.ticket_id} is neither approved nor rejected. {roles.finish(role, ticket.ticket_id)}"
    elif ticket.column in (config.backlog_column, config.refining_column):
        problems = core.ready_problems(config, ticket)
        if problems:
            return f"'kahnban ready {ticket.ticket_id}' would refuse it:\n" + "\n".join(
                f"  - {problem}" for problem in problems
            )
    return None


def main(*, stop: bool = False) -> int:
    """``kahnban guard`` as a PreToolUse hook, or with ``--stop`` as a Stop hook."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    if stop:
        role = os.environ.get("KAHNBAN_ROLE", "").strip()
        # One push back per stop: if the agent still stops, the runner's own check decides.
        if not role or payload.get("stop_hook_active") or payload.get("loop_count"):
            return 0
        try:
            reason = exit_problem(role, os.environ)
        except (core.KahnbanError, frontmatter.FrontmatterError, OSError) as error:
            print(f"kahnban guard --stop could not check this exit ({error})", file=sys.stderr)
            return 0
    else:
        reason = decide(payload, os.environ)
    if reason and stop and "conversation_id" in payload:
        # Cursor's stop hook can't block; it re-prompts the agent with followup_message.
        print(json.dumps({"followup_message": reason}))
        return 0
    if reason:
        print(reason, file=sys.stderr)  # Claude Code already labels it with the hook's name
        return 2
    return 0
