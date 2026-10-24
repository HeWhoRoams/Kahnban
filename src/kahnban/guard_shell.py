"""Read a shell command line the way the role guard needs it.

The line is split into simple commands (on ``;``, ``&&``, ``||``, ``|``, ``&``, newlines and
parentheses). Words are assembled the way a shell builds them, so ``m""erge`` and ``"mer"ge``
are both ``merge``. Each command reports the words it runs, the environment it sets, the
directory it runs in, and the files it writes (redirections, ``tee``, ``sed -i``, ``cp``,
``rm`` and the PowerShell equivalents). The parser looks inside ``bash -c "..."``,
``$(...)`` and backticks, and skips here-document bodies, so the guard can hold a shell
write to the same blast radius as an edit tool.

A word that comes from an expansion (``$x``, ``%X%``, ``~``) is marked, because the guard
cannot know what it will become: it refuses an expansion where the command or its
subcommand should be.

ponytail: this reads the obvious ways to write a file, not every way. ``python -c`` or an
encoded payload still gets through; the real boundary is a container or another OS user.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

OPERATORS = (">>>", "&>>", "<<<", "<<-", "||", "&&", "|&", ">>", ">|", "&>", ">&", "<<", "<&", ";;", ";", "|", "&", "(", ")", ">", "<")
SEPARATORS = {";", ";;", "&&", "||", "|", "|&", "&", "(", ")"}
REDIRECT_OUT = {">", ">>", ">|", "&>", "&>>", ">&"}
REDIRECT_IN = {"<", "<<", "<<-", "<<<", "<&"}
POSIX_ESCAPABLE = set(" \t\"'$`\\;&|()<>#\n")
SHELLS = {"bash", "sh", "zsh", "dash", "cmd", "powershell", "pwsh"}
POWERSHELLS = {"powershell", "pwsh"}
EVAL_FLAGS = {"-c", "-lc", "-ec", "-command", "/c", "/k"}
WRAPPERS = {"env", "command", "exec", "sudo", "time", "nohup", "nice", "builtin", "call"}
WRAPPER_OPTIONS_WITH_VALUE = {
    "env": {"-u", "--unset", "-S", "-C", "--chdir"},
    "sudo": {"-u", "-g", "-h", "-p", "-C"},
    "nice": {"-n"},
}
CD_COMMANDS = {"cd", "pushd", "chdir", "set-location", "sl"}
NULL_DEVICES = {"/dev/null", "nul", "$null", "/dev/stderr", "/dev/stdout"}
WRITES_ALL_ARGS = {"rm", "del", "erase", "rmdir", "rd", "remove-item", "ri", "touch", "truncate", "mkdir", "md"}
WRITES_DEST_ONLY = {"cp", "copy", "install", "copy-item", "cpi"}
WRITES_SOURCE_TOO = {"mv", "move", "move-item", "mi"}
WRITES_PATH_FLAG = {"set-content", "add-content", "out-file", "sc", "ac", "new-item", "ni"}
MAX_DEPTH = 3
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WINDOWS_VARIABLE = re.compile(r"%\w+%")


@dataclass
class Token:
    op: str  # the operator, or "" for a word
    text: str = ""  # the word with its quotes removed
    raw: str = ""  # the word as written
    expands: bool = False  # the word contains something a shell would expand


@dataclass
class Simple:
    raw: list[str]
    words: list[str]  # what runs: assignments and wrappers stripped
    expands: list[bool] = field(default_factory=list)  # per word, aligned with ``words``
    env: list[str] = field(default_factory=list)  # assignments and wrapper words stripped from the front
    writes: list[str] = field(default_factory=list)  # files this command writes
    cwd: Path | None = None  # where it runs; None when a ``cd`` made that unknowable


def tokenize(command: str, *, powershell: bool = False) -> list[Token]:
    """Split ``command`` into words and operators; ``ValueError`` when a quote is left open."""
    text = command.replace("\r\n", "\n")
    tokens: list[Token] = []
    word: list[str] = []
    raw: list[str] = []
    expands = False
    started = False
    quote = ""
    in_backtick = False
    heredocs: list[tuple[str, bool]] = []
    expect_delimiter = ""
    index = 0

    def flush() -> None:
        nonlocal word, raw, expands, started, expect_delimiter
        if started:
            tokens.append(Token("", "".join(word), "".join(raw), expands))
            if expect_delimiter:
                heredocs.append(("".join(word), expect_delimiter == "<<-"))
                expect_delimiter = ""
        word, raw, expands, started = [], [], False, False

    while index < len(text):
        char = text[index]
        if quote:
            raw.append(char)
            if char == quote:
                quote = ""
            elif quote == '"' and char == "\\" and not powershell and text[index + 1 : index + 2] in {'"', "\\", "$", "`"}:
                index += 1
                word.append(text[index])
                raw.append(text[index])
            else:
                if quote == '"' and char in "$`":
                    expands = True
                word.append(char)
            index += 1
            continue
        if char in "'\"":
            quote, started = char, True
            raw.append(char)
            index += 1
            continue
        escape = "`" if powershell else "\\"
        following = text[index + 1 : index + 2]
        if char == escape and following and (powershell or following in POSIX_ESCAPABLE):
            word.append(following)
            raw.append(char + following)
            started = True
            index += 2
            continue
        if char == "\n":
            flush()
            tokens.append(Token(";"))
            index += 1
            if heredocs:
                index = _skip_heredocs(text, index, heredocs)
            continue
        if char in " \t":
            flush()
            index += 1
            continue
        if char == "#" and not started and not powershell:
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if char == "`" and not powershell:
            flush()
            tokens.append(Token(")" if in_backtick else "("))
            in_backtick = not in_backtick
            index += 1
            continue
        if char in "<>|&;()":
            operator = next(op for op in OPERATORS if text.startswith(op, index))
            if started and "".join(word).isdigit() and operator[0] in "<>":
                word, raw, expands, started = [], [], False, False  # a file descriptor: 2>file
            else:
                flush()
            tokens.append(Token(operator))
            if operator in {"<<", "<<-"}:
                expect_delimiter = operator
            index += len(operator)
            continue
        if char == "$" or (char == "~" and not started) or (char == "%" and WINDOWS_VARIABLE.match(text, index)):
            expands = True
        word.append(char)
        raw.append(char)
        started = True
        index += 1
    if quote or in_backtick:
        raise ValueError("unbalanced quote")
    flush()
    return tokens


def _skip_heredocs(text: str, index: int, pending: list[tuple[str, bool]]) -> int:
    """Skip the bodies of the here-documents opened on the line just ended."""
    for delimiter, strip_tabs in pending:
        while index < len(text):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            line = text[index:end]
            index = min(end + 1, len(text))
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                break
    pending.clear()
    return index


def parse(command: str, *, cwd: Path | None = None, powershell: bool = False, depth: int = 0) -> list[Simple]:
    """The simple commands in ``command``; raises ``ValueError`` when the quoting is unbalanced."""
    found: list[Simple] = []
    group: list[Token] = []
    stack: list[Path | None] = []
    here = cwd

    def close() -> None:
        nonlocal here
        if group:
            commands = _simple(list(group), here, powershell, depth)
            found.extend(commands)
            here = _after_cd(commands[0], here)
            group.clear()

    for token in tokenize(command, powershell=powershell):
        if token.op in SEPARATORS:
            close()
            if token.op == "(":
                stack.append(here)
            elif token.op == ")" and stack:
                here = stack.pop()
        else:
            group.append(token)
    close()
    return found


def _simple(group: list[Token], cwd: Path | None, powershell: bool, depth: int) -> list[Simple]:
    words: list[Token] = []
    writes: list[str] = []
    tokens = iter(group)
    for token in tokens:
        if token.op in REDIRECT_OUT:
            target = next(tokens, None)
            if target is None or target.op:
                continue
            if token.op == ">&" and (target.text.isdigit() or target.text == "-"):
                continue
            if target.text.lower() not in NULL_DEVICES:
                writes.append(target.text)
        elif token.op in REDIRECT_IN:
            next(tokens, None)
        elif not token.op:
            words.append(token)
    env, words = _strip_prefix(words)
    result = Simple(
        raw=[token.raw for token in group if not token.op],
        words=[token.text for token in words],
        expands=[token.expands for token in words],
        env=env,
        writes=writes,
        cwd=cwd,
    )
    result.writes += _written_files(result.words)
    children: list[Simple] = []
    if depth < MAX_DEPTH:
        for text, nested_powershell in _nested_commands(group, result.words):
            children += parse(text, cwd=cwd, powershell=nested_powershell, depth=depth + 1)
    return [result, *children]


def _basename(word: str) -> str:
    return Path(word).name.lower().removesuffix(".exe")


def _strip_prefix(words: list[Token]) -> tuple[list[str], list[Token]]:
    """Peel ``VAR=value`` assignments and wrappers such as ``env -u X`` off the front."""
    env: list[str] = []
    index = 0
    while index < len(words):
        word = words[index].text
        name = _basename(word)
        if ASSIGNMENT.match(word):
            env.append(word)
            index += 1
        elif name in WRAPPERS:
            env.append(word)
            index += 1
            while index < len(words) and words[index].text.startswith("-"):
                env.append(words[index].text)
                takes_value = words[index].text in WRAPPER_OPTIONS_WITH_VALUE.get(name, set())
                index += 1
                if takes_value and index < len(words):
                    env.append(words[index].text)
                    index += 1
        else:
            break
    return env, words[index:]


def _nested_commands(group: list[Token], words: list[str]) -> list[tuple[str, bool]]:
    """Command text hidden in ``bash -c "..."``, ``$(...)`` and backticks."""
    nested: list[tuple[str, bool]] = []
    if words and _basename(words[0]) in SHELLS:
        for position, word in enumerate(words[1:], 1):
            if word.lower() in EVAL_FLAGS and position + 1 < len(words):
                nested.append((" ".join(words[position + 1 :]), _basename(words[0]) in POWERSHELLS))
                break
    for token in group:
        if not token.op:
            nested += [(inner, False) for inner in substitutions(token.raw)]
    return nested


def substitutions(raw: str) -> list[str]:
    """The text inside ``$(...)`` and backticks in a word as written; single quotes keep them literal."""
    found: list[str] = []
    quote = ""
    index = 0
    while index < len(raw):
        char = raw[index]
        if quote == "'":
            quote = "" if char == "'" else quote
        elif char == "'" and not quote:
            quote = "'"
        elif char == '"':
            quote = "" if quote == '"' else '"'
        elif raw.startswith("$(", index):
            depth, end = 1, index + 2
            while end < len(raw) and depth:
                depth += (raw[end] == "(") - (raw[end] == ")")
                end += 1
            found.append(raw[index + 2 : end - 1])
            index = end
            continue
        elif char == "`":
            end = raw.find("`", index + 1)
            if end > 0:
                found.append(raw[index + 1 : end])
                index = end
        index += 1
    return found


def _after_cd(command: Simple, cwd: Path | None) -> Path | None:
    """Where the next command runs: unknown (None) whenever a ``cd`` cannot be followed."""
    if not command.words or _basename(command.words[0]) not in CD_COMMANDS:
        return cwd
    arguments = [word for word in command.words[1:] if not word.startswith("-") and word.lower() != "/d"]
    if cwd is None or not arguments or any(command.expands[1:]) or arguments[0].startswith("~"):
        return None
    return Path(os.path.normpath(cwd / arguments[0]))


def _written_files(words: list[str]) -> list[str]:
    """Files that the command in ``words`` creates, changes or deletes."""
    if not words:
        return []
    name = _basename(words[0])
    args = [word for word in words[1:] if not word.startswith("-")]
    flags = [word.lower() for word in words[1:] if word.startswith("-")]
    if name in WRITES_ALL_ARGS or name in WRITES_SOURCE_TOO or name == "tee":
        return args
    if name in WRITES_DEST_ONLY:
        return args[-1:]
    if name == "sed" and any(flag == "-i" or flag.startswith("-i") or flag.startswith("--in-place") for flag in flags):
        return args[1:]
    if name in WRITES_PATH_FLAG:
        for position, word in enumerate(words[1:], 1):
            if word.lower() in {"-path", "-filepath", "-literalpath"} and position + 1 < len(words):
                return [words[position + 1]]
        return args[:1]
    return []
