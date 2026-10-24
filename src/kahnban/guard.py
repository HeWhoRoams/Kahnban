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
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter, gitops, guard_shell, roles, trust

# Tool names differ per harness: Claude Code, Gemini CLI, Cursor.
EDIT_TOOLS = {
    "Edit", "Write", "MultiEdit", "NotebookEdit",
    "write_file", "replace",
    "StrReplace", "Delete", "EditNotebook",
}
SHELL_TOOLS = {"Bash", "run_shell_command", "Shell"}
READ_TOOLS = {"Read", "read_file", "ReadFile", "Grep", "Glob"}
SECRET_REFUSAL = "the signing key is the runner's, not a worker's to read"
PATH_KEYS = ("file_path", "notebook_path", "path", "target_file")
# Which commands and files each role gets lives in templates/roles.json.
OVERRIDE_FLAGS = {"--force", "--force-scope", "--force-overlap", "--abandon", "--no-verify"}
GIT_FORBIDDEN = {"merge", "push", "rebase", "filter-branch", "update-ref"}
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


def _relative_to(path: Path, base: Path) -> str | None:
    """``path`` under ``base`` as a posix string, or None; folds case where the filesystem does."""
    target, root = os.path.normcase(str(path)), os.path.normcase(str(base)).rstrip(os.sep)
    if target == root:
        return ""
    if not target.startswith(root + os.sep):
        return None
    return Path(str(path)[len(root) + 1 :]).as_posix()


def _edit_problem(role: str, path: Path, env: Mapping[str, str]) -> str | None:
    root = Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve()
    scope = roles.edits(role)
    if not scope:
        hint = f" {roles.finish(role, env.get('KAHNBAN_TICKET', ''))}" if role in roles.workers() else ""
        return f"a {role} does not edit files.{hint}"
    config = core.load_config(root)
    if scope == "blast_radius":
        tree = Path(env.get("KAHNBAN_WORKTREE", "")).resolve()
        relative = _relative_to(path, tree)
        if relative is None:
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
    relative = _relative_to(path, root)
    if relative is None:
        return f"{path} is outside the project"
    allowed = tuple(config.board_root if entry == "{board}" else entry for entry in scope)
    if not core.path_within(relative, allowed):
        return f"a {role} may only edit {', '.join(allowed) or 'nothing'}, not {relative}"
    return None


def _names_the_key(*texts: str) -> bool:
    folder = os.path.normcase(str(trust.key_dir()))
    return any(trust.KEY_ENV.lower() in text.lower() or folder in os.path.normcase(text) for text in texts)


def _git_subcommand(words: list[str]) -> tuple[str, list[str]]:
    """The git subcommand in ``words`` and what follows it, skipping git's global options."""
    if not words or Path(words[0]).name.lower().removesuffix(".exe") != "git":
        return "", []
    takes_value = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in takes_value else 1
    return (words[index].lower(), words[index + 1 :]) if index < len(words) else ("", [])


def _write_problem(role: str, target: str, cwd: Path, env: Mapping[str, str]) -> str | None:
    if any(mark in target for mark in "$%~*?"):
        return f"cannot tell where '{target}' writes; name the file"
    path = Path(target)
    path = (path if path.is_absolute() else cwd / path).resolve()
    try:
        return _edit_problem(role, path, env)
    except core.KahnbanError as error:
        return f"guard could not check this write ({error}); refusing"


def _bash_problem(role: str, command: str, cwd: Path, env: Mapping[str, str]) -> str | None:
    try:
        commands = guard_shell.parse(command)
    except ValueError:  # unbalanced quoting: judge the words as they stand
        commands = [guard_shell.Simple(command.split(), command.split())]
    for item in commands:
        if _names_the_key(*item.words):
            return SECRET_REFUSAL
        flags = sorted(OVERRIDE_FLAGS & {word.split("=", 1)[0] for word in item.words})
        if flags:
            return f"override flags are for humans: {', '.join(flags)}"
        subcommand, rest = _git_subcommand(item.words)
        if subcommand in GIT_FORBIDDEN or (subcommand == "reset" and "--hard" in rest):
            return "merging, pushing and rewriting history is the runner's job"
        if subcommand == "commit" and not roles.edits(role):
            return f"a {role} does not commit"
        for kahnban_command in _kahnban_subcommands(" ".join(item.raw)):
            problem = command_problem(role, kahnban_command)
            if problem:
                return problem
        for target in item.writes:
            problem = _write_problem(role, target, cwd, env)
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
    if tool in READ_TOOLS and _names_the_key(*(str(value) for value in tool_input.values())):
        return SECRET_REFUSAL
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
        cwd = Path(str(payload.get("cwd") or env.get("KAHNBAN_WORKTREE") or "."))
        return _bash_problem(role, str(tool_input.get("command") or ""), cwd, env)
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
