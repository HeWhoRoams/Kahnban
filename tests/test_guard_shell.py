"""The guard reads a shell line as a shell would: quoting, wrappers, git's global options and writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import guard, guard_shell
from test_factory_gates import claimed, strict_board


@pytest.fixture
def env(repo: Path) -> dict[str, str]:
    config = strict_board(repo)
    tree = claimed(config)
    return {
        "KAHNBAN_ROLE": "coder",
        "KAHNBAN_TICKET": "TST-001",
        "KAHNBAN_PROJECT_ROOT": str(repo),
        "KAHNBAN_WORKTREE": str(tree),
    }


def check(env: dict[str, str], command: str, role: str = "coder") -> str | None:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": env["KAHNBAN_WORKTREE"]}
    return guard.decide(payload, {**env, "KAHNBAN_ROLE": role})


OVERRIDES = [
    "kahnban verify TST-001 --force-scope --reason x",
    "kahnban verify TST-001 '--force-scope' --reason x",
    'kahnban verify TST-001 "--force-scope" --reason x',
    "kahnban verify TST-001 --force-scope=1",
]
HISTORY = [
    "git push origin main",
    "git -c core.editor=true merge main",
    "git --git-dir=.git push",
    "git -C . push origin main",
    "git --no-pager rebase main",
    "git reset --hard HEAD~1",
    "pytest -q && git push",
    "echo done | git push",
    "bash -c 'git push origin main'",
    'sh -c "git merge other"',
    "echo $(git push)",
    'echo "$(git merge other)"',
    "echo `git push`",
    "FOO=1 git push",
    "env git push",
]
NOT_THE_CODERS = [
    "kahnban done TST-001",
    "FOO=1 kahnban approve TST-001 --reviewer x",
    "env kahnban claim TST-001",
    "sh -c 'kahnban done TST-001'",
    "python -m kahnban merge TST-001",
]
WRITES_OUTSIDE_THE_RADIUS = [
    "echo x > README.md",
    "echo x >> ../outside.txt",
    "sed -i s/a/b/ README.md",
    "sed --in-place s/a/b/ README.md",
    "tee README.md",
    "cp src/app.py README.md",
    "rm README.md",
    "Set-Content -Path README.md -Value x",
    "echo x > '../other file.txt'",
    "pytest -q; echo x > README.md",
    "bash -c 'echo x > README.md'",
]
ALLOWED = [
    "pytest -q",
    "git status",
    "git log --oneline | head",
    'git commit -m "fix: merge the docs, no --force and no git push here"',
    "kahnban escalate TST-001 --reason 'could not git push'",
    "pytest -q 2>&1",
    "pytest -q > /dev/null",
    "pytest -q > NUL",
    "echo x > src/app.py",
    "sed -i s/a/b/ src/app.py",
    "pytest -q && git diff --stat",
]


@pytest.mark.parametrize("command", OVERRIDES)
def test_quoted_and_joined_override_flags_are_refused(env: dict[str, str], command: str) -> None:
    assert "override flags" in (check(env, command) or "")


@pytest.mark.parametrize("command", HISTORY)
def test_history_rewriting_is_refused_however_it_is_spelled(env: dict[str, str], command: str) -> None:
    assert "runner's job" in (check(env, command) or "")


@pytest.mark.parametrize("command", NOT_THE_CODERS)
def test_gates_stay_the_runners_inside_wrappers_and_subshells(env: dict[str, str], command: str) -> None:
    assert "not a coder's" in (check(env, command) or "")


@pytest.mark.parametrize("command", WRITES_OUTSIDE_THE_RADIUS)
def test_a_shell_write_is_held_to_the_blast_radius(env: dict[str, str], command: str) -> None:
    problem = check(env, command) or ""
    assert "blast radius" in problem or "outside your worktree" in problem, problem


@pytest.mark.parametrize("command", ALLOWED)
def test_ordinary_commands_pass(env: dict[str, str], command: str) -> None:
    assert check(env, command) is None


def test_a_reviewer_may_not_write_files_from_the_shell(env: dict[str, str]) -> None:
    assert "does not edit files" in (check(env, "echo x > notes.txt", "qa_reviewer") or "")
    assert check(env, "kahnban approve TST-001 --reviewer q", "qa_reviewer") is None


def test_an_unknown_write_target_is_refused(env: dict[str, str]) -> None:
    assert "cannot tell where" in (check(env, "echo x > $HOME/a") or "")


def test_unbalanced_quotes_fall_back_to_the_words() -> None:
    with pytest.raises(ValueError):
        guard_shell.parse('echo "unterminated')
