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
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from kahnban import core, exit_checks, frontmatter, guard_shell, roles, trust

# Tool names differ per harness: Claude Code, Gemini CLI, Cursor.
EDIT_TOOLS = {
    "Edit", "Write", "MultiEdit", "NotebookEdit",
    "write_file", "replace",
    "StrReplace", "Delete", "EditNotebook",
}
SHELL_TOOLS = {"Bash", "run_shell_command", "Shell", "PowerShell"}
READ_TOOLS = {
    "Read", "NotebookRead", "Grep", "Glob", "LS",
    "read_file", "read_many_files", "glob", "search_file_content", "grep_search", "list_directory",
    "ReadFile",
}
SECRET_REFUSAL = "the signing key is the runner's, not a worker's to read"
PATH_KEYS = ("file_path", "notebook_path", "path", "target_file")
OVERRIDE_FLAGS = {"--force", "--force-scope", "--force-overlap", "--abandon", "--no-verify"}
GIT_FORBIDDEN = {
    "merge", "push", "rebase", "filter-branch", "update-ref", "cherry-pick", "worktree", "symbolic-ref", "replace", "gc",
}
MESSAGE_OPTIONS = {"-m", "--message", "-F", "--file", "--reason", "-C", "--author", "--date"}
ENV_COMMANDS = {"export", "unset", "set", "declare", "typeset", "readonly", "setx", "setenv", "set-item", "remove-item", "ri", "si"}
ENV_REFUSAL = "KAHNBAN_* variables and the environment are the runner's; a worker does not change or clear them"
KAHNBAN_GLOBAL_OPTIONS = {"--project-root", "--config"}


def _unescaped(word: str) -> str:
    """A shell drops a backslash before an ordinary letter, so ``mer`` + backslash + ``ge`` is ``merge``."""
    return word.replace("\\", "")


def _kahnban_subcommands(words: list[str], expands: list[bool]) -> tuple[list[str], bool]:
    """Subcommands of every ``kahnban`` / ``python -m kahnban`` call in ``words``, and whether one is an expansion."""
    found: list[str] = []
    opaque = False
    for index, word in enumerate(words):
        if Path(word).name.lower() not in ("kahnban", "kahnban.exe"):
            continue
        positions = iter(range(index + 1, len(words)))
        for position in positions:
            if words[position] in KAHNBAN_GLOBAL_OPTIONS:
                next(positions, None)
            elif not words[position].startswith("-"):
                if expands[position]:
                    opaque = True
                    break
                command = _unescaped(words[position]).lower()
                if command == "spec":  # its action decides: drafting is fine, approving is not
                    action = next((p for p in positions if not words[p].startswith("-")), None)
                    command = f"spec {words[action].lower()}" if action is not None else command
                found.append(command)
                break
    return found, opaque


def _relative_to(path: Path, base: Path) -> str | None:
    """``path`` under ``base`` as a posix string, or None; folds case where the filesystem does."""
    target, root = os.path.normcase(str(path)), os.path.normcase(str(base)).rstrip(os.sep)
    if target == root:
        return ""
    if not target.startswith(root + os.sep):
        return None
    return Path(str(path)[len(root) + 1 :]).as_posix()


def _edit_problem(role: str, path: Path, env: Mapping[str, str]) -> str | None:
    root = core.project_root_from_env(env)
    scope = roles.edits(role)
    if not scope:
        hint = f" {roles.finish(role, env.get(core.ENV_TICKET, ''))}" if role in roles.workers() else ""
        return f"a {role} does not edit files.{hint}"
    config = core.load_config(root)
    if scope == "blast_radius":
        tree = Path(env.get(core.ENV_WORKTREE, "")).resolve()
        relative = _relative_to(path, tree)
        if relative is None:
            return f"{path} is outside your worktree {tree}"
        ticket = core.find_ticket(config, env.get(core.ENV_TICKET, ""))
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


def _git_subcommand(words: list[str], expands: list[bool]) -> tuple[str, list[str], bool]:
    """The git subcommand in ``words``, what follows it, and whether it comes from an expansion."""
    if not words or Path(words[0]).name.lower().removesuffix(".exe") != "git":
        return "", [], False
    takes_value = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in takes_value else 1
    if index >= len(words):
        return "", [], False
    return _unescaped(words[index]).lower(), words[index + 1 :], expands[index]


def _rewrites_shared_state(subcommand: str, rest: list[str]) -> bool:
    """History and ref changes that are the runner's job, however git is asked to make them."""
    if subcommand in GIT_FORBIDDEN or (subcommand == "reset" and "--hard" in rest):
        return True
    flags = [word for word in rest if word.startswith("-")]
    if subcommand == "branch":
        return any(flag in {"--force", "--delete", "--move"} or re.match(r"^-[A-Za-z]*[fdDmM]", flag) for flag in flags)
    if subcommand == "tag":
        return any(flag in {"--force", "--delete"} or re.match(r"^-[A-Za-z]*[fd]", flag) for flag in flags)
    return False


def _override_flags(words: list[str]) -> list[str]:
    """Override flags among ``words``, not counting text given as a message or reason."""
    flags: set[str] = set()
    skip = False
    for word in words:
        if skip:
            skip = False
        elif word in MESSAGE_OPTIONS:
            skip = True
        elif _unescaped(word).split("=", 1)[0] in OVERRIDE_FLAGS:
            flags.add(_unescaped(word).split("=", 1)[0])
    return sorted(flags)


def _environment_problem(item: guard_shell.Simple) -> str | None:
    """The worker's role and run state are the runner's: refuse a command that would clear or change them."""
    words = [word.lower() for word in item.words]
    name = Path(item.words[0]).name.lower().removesuffix(".exe") if item.words else ""
    env_words = [word.lower() for word in item.env]
    mentions = any("kahnban_" in word for word in [*env_words, *words])
    wrapped_in_env = any(Path(word).name.lower().removesuffix(".exe") == "env" for word in item.env)
    clears = wrapped_in_env and any(word in {"-i", "--ignore-environment", "-u", "--unset"} for word in item.env)
    sets = name in ENV_COMMANDS or any(word.startswith(("$env:", "env:")) for word in words)
    if (mentions and (sets or any("kahnban_" in word for word in env_words))) or clears:
        return ENV_REFUSAL
    return None


def _item_problem(role: str, item: guard_shell.Simple, env: Mapping[str, str]) -> str | None:
    if _names_the_key(*item.words):
        return SECRET_REFUSAL
    problem = _environment_problem(item)
    if problem:
        return problem
    flags = _override_flags(item.words)
    if flags:
        return f"override flags are for humans: {', '.join(flags)}"
    if item.words and item.expands[0]:
        return "cannot tell what this runs: the command name comes from an expansion"
    subcommand, rest, expanded = _git_subcommand(item.words, item.expands)
    if expanded:
        return "cannot tell which git command this is: the subcommand comes from an expansion"
    if _rewrites_shared_state(subcommand, rest):
        return "merging, pushing and rewriting history is the runner's job"
    if subcommand == "commit" and not roles.edits(role):
        return f"a {role} does not commit"
    commands, opaque = _kahnban_subcommands(item.words, item.expands)
    if opaque:
        return "cannot tell which kahnban command this is: the subcommand comes from an expansion"
    for kahnban_command in commands:
        problem = command_problem(role, kahnban_command)
        if problem:
            return problem
    for target in item.writes:
        if item.cwd is None:
            return f"cannot tell where '{target}' writes: an earlier cd could not be followed"
        problem = _write_problem(role, target, item.cwd, env)
        if problem:
            return problem
    return None


def _write_problem(role: str, target: str, cwd: Path, env: Mapping[str, str]) -> str | None:
    if any(mark in target for mark in "$%~*?"):
        return f"cannot tell where '{target}' writes; name the file"
    path = Path(target)
    path = (path if path.is_absolute() else cwd / path).resolve()
    try:
        return _edit_problem(role, path, env)
    except core.KahnbanError as error:
        return f"guard could not check this write ({error}); refusing"


def _bash_problem(role: str, command: str, cwd: Path, env: Mapping[str, str], *, powershell: bool = False) -> str | None:
    try:
        commands = guard_shell.parse(command, cwd=cwd, powershell=powershell)
    except ValueError:
        if not roles.edits(role):
            return "cannot read this command line (unbalanced quotes); write it plainly"
        words = command.split()  # a coder keeps working, judged on the words as they stand
        commands = [guard_shell.Simple(words, words, [False] * len(words), [], [], cwd)]
    for item in commands:
        problem = _item_problem(role, item, env)
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
    role = env.get(core.ENV_ROLE, "").strip()
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
            path = Path(str(payload.get("cwd") or env.get(core.ENV_WORKTREE) or ".")) / path
        try:
            return _edit_problem(role, path.resolve(), env)
        except core.KahnbanError as error:
            return f"guard could not check this edit ({error}); refusing"
    if tool in SHELL_TOOLS:
        cwd = Path(str(payload.get("cwd") or env.get(core.ENV_WORKTREE) or "."))
        return _bash_problem(role, str(tool_input.get("command") or ""), cwd, env, powershell=tool == "PowerShell")
    return None


def exit_problem(role: str, env: Mapping[str, str]) -> str | None:
    """Why a worker in ``role`` may not stop yet, or None; see :mod:`kahnban.exit_checks`."""
    return exit_checks.problem(role, env)


def _log_refusal(reason: str, payload: Mapping[str, Any]) -> None:
    """Append one JSON line to ``KAHNBAN_GUARD_LOG`` so a run can show what it blocked."""
    path = os.environ.get("KAHNBAN_GUARD_LOG", "")
    if not path:
        return
    tool_input = payload.get("tool_input") or {}
    attempted = tool_input.get("command") or tool_input.get("file_path") or payload.get("command") or ""
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "role": os.environ.get(core.ENV_ROLE, ""),
        "ticket": os.environ.get(core.ENV_TICKET, ""),
        "tool": payload.get("tool_name") or "shell",
        "reason": reason,
        "attempted": str(attempted)[:200],
    }
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _report_refusal(reason: str) -> None:
    """Tell the ``on-refusal`` hook; a hook that fails never changes the guard's answer."""
    root = os.environ.get(core.ENV_PROJECT_ROOT, "")
    if not root:
        return
    try:
        from kahnban import hooks

        hooks.run_hook(
            Path(root),
            "on-refusal",
            os.environ.get(core.ENV_TICKET, ""),
            payload={"gate": "guard", "role": os.environ.get(core.ENV_ROLE, ""), "reason": reason},
            timeout=5.0,
        )
    except Exception:
        pass


def main(*, stop: bool = False) -> int:
    """``kahnban guard`` as a PreToolUse hook, or with ``--stop`` as a Stop hook."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    if stop:
        role = os.environ.get(core.ENV_ROLE, "").strip()
        if not role:
            return 0
        try:
            reason = exit_problem(role, os.environ)
            # A few pushes back (max_stop_nudges), then the runner's own check decides.
            if reason and not exit_checks.spend_nudge(role, os.environ):
                reason = None
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
        _log_refusal(reason, payload)
        _report_refusal(reason)
        print(reason, file=sys.stderr)  # Claude Code already labels it with the hook's name
        return 2
    return 0
