"""Read a shell command line the way the role guard needs it.

``shlex`` splits the line into simple commands (on ``;``, ``&&``, ``||``, ``|``, ``&`` and
parentheses), strips quotes, and looks inside ``bash -c "..."`` and ``$(...)``. Each simple
command reports the words it runs and the files it writes (redirections, ``tee``, ``sed -i``,
``cp``, ``rm`` and the PowerShell equivalents), so the guard can hold a shell write to the
same blast radius as an edit tool.

ponytail: this reads the obvious ways to write a file, not every way. ``python -c`` or an
encoded payload still gets through; the real boundary is a container or another OS user.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "|&"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
SHELLS = {"bash", "sh", "zsh", "dash", "cmd", "powershell", "pwsh"}
EVAL_FLAGS = {"-c", "-lc", "-ec", "-command", "/c", "/k"}
WRAPPERS = {"env", "command", "exec", "sudo", "time", "nohup", "nice", "builtin", "call"}
NULL_DEVICES = {"/dev/null", "nul", "$null", "/dev/stderr", "/dev/stdout"}
WRITES_ALL_ARGS = {"rm", "del", "erase", "rmdir", "rd", "remove-item", "ri", "touch", "truncate", "mkdir", "md"}
WRITES_LAST_ARG = {"cp", "copy", "mv", "move", "install", "copy-item", "move-item", "cpi", "mi"}
WRITES_PATH_FLAG = {"set-content", "add-content", "out-file", "sc", "ac", "new-item", "ni"}
MAX_DEPTH = 3
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)")


@dataclass
class Simple:
    raw: list[str]  # as written, quotes kept
    words: list[str]  # quotes removed, wrappers and VAR=value stripped
    writes: list[str] = field(default_factory=list)  # files this command writes


def unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def parse(command: str, depth: int = 0) -> list[Simple]:
    """The simple commands in ``command``; raises ``ValueError`` when the quoting is unbalanced."""
    text = command.replace("\r\n", "\n").replace("\n", " ; ").replace("`", " ; ")
    lexer = shlex.shlex(text, posix=False, punctuation_chars=True)
    lexer.whitespace_split = True
    found: list[Simple] = []
    group: list[str] = []

    def close() -> None:
        if group:
            found.extend(_simple(list(group), depth))
            group.clear()

    for token in lexer:
        if token in SEPARATORS:
            close()
        else:
            group.append(token)
    close()
    return found


def _simple(raw: list[str], depth: int) -> list[Simple]:
    words: list[str] = []
    writes: list[str] = []
    tokens = iter(raw)
    for token in tokens:
        if token in REDIRECTS:
            target = unquote(next(tokens, ""))
            if target and target.lower() not in NULL_DEVICES and not target.startswith("&"):
                writes.append(target)
        elif token.startswith(">&") or token.endswith(">&") or token == "<" or token == "<<":
            continue
        else:
            words.append(unquote(token))
    words = _strip_wrappers(words)
    result = Simple(raw, words, writes)
    result.writes += _written_files(words)
    nested = _nested_commands(raw, words)
    if depth < MAX_DEPTH:
        children = [item for text in nested for item in parse(text, depth + 1)]
    else:
        children = []
    return [result, *children]


def _strip_wrappers(words: list[str]) -> list[str]:
    index = 0
    while index < len(words):
        word = words[index]
        name = Path(word).name.lower().removesuffix(".exe")
        if "=" in word and not word.startswith("-") and name not in WRAPPERS:
            index += 1  # VAR=value prefix
        elif name in WRAPPERS:
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index += 1
        else:
            break
    return words[index:]


def _nested_commands(raw: list[str], words: list[str]) -> list[str]:
    """Command text hidden in ``bash -c "..."`` and ``$(...)``."""
    nested: list[str] = []
    if words and Path(words[0]).name.lower().removesuffix(".exe") in SHELLS:
        for index, word in enumerate(words[1:], 1):
            if word.lower() in EVAL_FLAGS and index + 1 < len(words):
                nested.append(" ".join(words[index + 1 :]))
                break
    for token in raw:
        if token[:1] != "'":  # single quotes keep $(...) literal
            nested += SUBSTITUTION.findall(token)
    return nested


def _written_files(words: list[str]) -> list[str]:
    """Files that the command in ``words`` creates, changes or deletes."""
    if not words:
        return []
    name = Path(words[0]).name.lower().removesuffix(".exe")
    args = [word for word in words[1:] if not word.startswith("-")]
    flags = [word.lower() for word in words[1:] if word.startswith("-")]
    if name in WRITES_ALL_ARGS:
        return args
    if name in WRITES_LAST_ARG:
        return args[-1:] if name in {"cp", "copy", "install", "copy-item", "cpi"} else args
    if name == "tee":
        return args
    if name == "sed" and any(flag == "-i" or flag.startswith("-i") or flag.startswith("--in-place") for flag in flags):
        return args[1:]
    if name in WRITES_PATH_FLAG:
        for index, word in enumerate(words[1:], 1):
            if word.lower() in {"-path", "-filepath", "-literalpath"} and index + 1 < len(words):
                return [words[index + 1]]
        return args[:1]
    return []
