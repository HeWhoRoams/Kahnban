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


def checking(env: dict[str, str], command: str, role: str = "coder", tool: str = "Bash") -> str | None:
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": env["KAHNBAN_WORKTREE"]}
    return guard.decide(payload, {**env, "KAHNBAN_ROLE": role})


SPLIT_QUOTES = [
    ('git m""erge other', "runner's job"),
    ('git --no-pager "mer"ge x', "runner's job"),
    ("git 'pu''sh' origin main", "runner's job"),
    ('kahnban verify TST-001 --force""-scope --reason x', "override flags"),
    ("kahnban verify TST-001 --no-ver\"\"ify", "override flags"),
    ("git mer\\ge other", "runner's job"),
]
OPAQUE = [
    "x=merge; git $x",
    "git$IFS merge",
    "$tool push origin main",
    "kahnban $sub TST-001",
    'git "$sub" main',
]
OTHER_HISTORY = [
    "git branch -f main HEAD",
    "git branch --force main HEAD",
    "git -c core.x=y branch -D main",
    "git branch -m main old",
    "git cherry-pick abc123",
    "git worktree add ../elsewhere",
    "git tag -d v1",
    "git tag -f v1",
    "git symbolic-ref HEAD refs/heads/main",
]
CLEARING_THE_ROLE = [
    "KAHNBAN_ROLE= kahnban ready TST-001",
    "env -u KAHNBAN_ROLE kahnban approve TST-001 --reviewer x",
    "env --unset=KAHNBAN_ROLE kahnban ready TST-001",
    "env -i kahnban ready TST-001",
    "env KAHNBAN_ROLE=human kahnban ready TST-001",
    "export KAHNBAN_ROLE=",
    "unset KAHNBAN_ROLE; kahnban ready TST-001",
    "bash -c 'unset KAHNBAN_ROLE; kahnban ready TST-001'",
    "KAHNBAN_TICKET=TST-009 pytest -q",
]
MORE_ALLOWED = [
    'git commit -m "--no-verify is for humans"',
    'git commit -m "a `b` c"',
    "git commit -m \"$(cat <<'EOF'\nfix: merge docs, mention git push and --force\n\nbody (with parens)\nEOF\n)\"",
    "sudo -u builder pytest -q",
    "git branch --list",
    "git branch -a",
    'git tag -a v1 -m "release"',
    "cd src && echo x > app.py",
    "(cd src && pytest -q); echo ok",
    "echo KAHNBAN_ROLE is documented",
]


@pytest.mark.parametrize(("command", "why"), SPLIT_QUOTES)
def test_quotes_inside_a_word_do_not_hide_what_it_says(env: dict[str, str], command: str, why: str) -> None:
    assert why in (checking(env, command) or "")


@pytest.mark.parametrize("command", OPAQUE)
def test_a_command_or_subcommand_from_an_expansion_is_refused(env: dict[str, str], command: str) -> None:
    assert "cannot tell" in (checking(env, command) or "")


@pytest.mark.parametrize("command", OTHER_HISTORY)
def test_other_commands_that_rewrite_shared_refs_are_refused(env: dict[str, str], command: str) -> None:
    problem = checking(env, command) or ""
    assert "runner's job" in problem or "override flags" in problem, command


@pytest.mark.parametrize("command", CLEARING_THE_ROLE)
def test_a_worker_cannot_clear_or_change_its_own_role(env: dict[str, str], command: str) -> None:
    assert "runner's" in (checking(env, command) or ""), command


@pytest.mark.parametrize("command", MORE_ALLOWED)
def test_more_ordinary_commands_pass(env: dict[str, str], command: str) -> None:
    assert checking(env, command) is None, command


def test_a_write_after_cd_is_judged_where_it_lands(env: dict[str, str]) -> None:
    assert "outside your worktree" in (checking(env, "cd .. && echo x > a.txt") or "")
    assert "blast radius" in (checking(env, "cd src && echo x > other.py") or "")
    assert "cannot tell where" in (checking(env, "cd $ELSEWHERE && echo x > src/app.py") or "")
    assert checking(env, "(cd .. ); echo x > src/app.py") is None  # the subshell's cd does not leak


def test_unbalanced_quotes_are_refused_for_a_reviewer_and_judged_by_words_for_a_coder(env: dict[str, str]) -> None:
    assert "unbalanced quotes" in (checking(env, 'echo "oops', "qa_reviewer") or "")
    assert checking(env, 'echo "oops') is None
    assert "override flags" in (checking(env, 'echo "oops --force') or "")


def test_the_powershell_tool_gets_the_same_answers(env: dict[str, str]) -> None:
    assert "runner's job" in (checking(env, "git push origin main", tool="PowerShell") or "")
    assert "blast radius" in (checking(env, "Set-Content -Path README.md -Value x", tool="PowerShell") or "")
    assert "runner's" in (checking(env, "$env:KAHNBAN_ROLE = ''; kahnban ready TST-001", tool="PowerShell") or "")
    assert "runner's" in (checking(env, "Remove-Item Env:KAHNBAN_ROLE", tool="PowerShell") or "")
    assert checking(env, 'git commit -m "fix `"quoted`" text"', tool="PowerShell") is None


def test_the_engine_reads_the_workers_role_in_one_place(monkeypatch) -> None:
    from kahnban import core

    monkeypatch.delenv("KAHNBAN_ROLE", raising=False)
    assert core.worker_role() == ""
    monkeypatch.setenv("KAHNBAN_ROLE", " coder ")
    assert core.worker_role() == "coder"
    monkeypatch.setenv("KAHNBAN_ROLE", "")
    assert core.worker_role() == ""


def test_a_command_that_clears_the_role_never_reaches_a_gate(env: dict[str, str]) -> None:
    """The gates trust KAHNBAN_ROLE, so the guard is what keeps a worker from emptying it."""
    for command in CLEARING_THE_ROLE[:4]:
        assert "runner's" in (checking(env, command, role="spec_analyst") or ""), command


def test_a_refusal_is_written_to_the_guard_log(
    env: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    import json
    import sys

    from kahnban.cli import main

    log = tmp_path / "run.log.guard"
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("KAHNBAN_GUARD_LOG", str(log))
    monkeypatch.setenv("KAHNBAN_ROLE", "coder")
    blocked = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
    allowed = {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}}
    for payload in (blocked, allowed):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        main(["guard"])
    capsys.readouterr()

    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    assert lines[0]["role"] == "coder" and lines[0]["attempted"] == "git push origin main"
    assert "runner's job" in lines[0]["reason"]


def test_a_run_reports_what_the_guard_refused(repo: Path, tmp_path: Path) -> None:
    from kahnban import runner
    from test_factory_gates import CHECK_APP, PY, factory_board
    from test_factory_run import WORKER, ready_ticket

    script = tmp_path / "worker.py"
    script.write_text(
        WORKER.format(check_app=CHECK_APP).replace(
            "print(role, \"finished\")",
            "import json\n"
            "payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'git push origin main'}})\n"
            "subprocess.run([sys.executable, '-m', 'kahnban', 'guard'], input=payload, text=True)\n"
            "print(role, 'finished')",
        ),
        encoding="utf-8",
    )
    config = factory_board(repo, workers={"default": f"{PY} {script}"})
    ready_ticket(config)
    lines: list[str] = []

    result = runner.run(config, max_steps=10, echo=lines.append)

    assert result.guard_refusals >= 1
    assert any("the guard refused" in line for line in lines)
