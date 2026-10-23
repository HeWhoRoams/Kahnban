"""Each gate refuses the dishonest input that once got past it (audit probes A-F)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kahnban import core, frontmatter
from conftest import git, scaffold_board, write_ticket

PY = sys.executable
CHECK = f"{PY} tests/check_app.py"
CRITERION = f"- [ ] f() returns 2 (test: `{CHECK}`)"
CHECK_APP = (
    "import sys\n"
    "sys.path.insert(0, 'src')\n"
    "from app import f\n"
    "assert f() == 2, f()\n"
    "print('app ok')\n"
)
FIX = {"src/app.py": "def f():\n    return 2\n", "tests/check_app.py": CHECK_APP}


def strict_board(repo: Path, **overrides: object) -> core.Config:
    scaffold_board(repo, {"require_proof": True, **overrides})
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "app returns 1")
    return core.load_config(repo)


def claimed(
    config: core.Config,
    *,
    validation: str = CHECK,
    acceptance: tuple[str, ...] = (CRITERION,),
    radius: tuple[str, ...] = ("src/app.py", "tests/check_app.py"),
) -> Path:
    write_ticket(
        config.board_path,
        "1-refining",
        "TST-001",
        "fix-f",
        acceptance=acceptance,
        blast_radius=radius,
        validation=validation,
    )
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", "refine TST-001")
    core.ready(config, "TST-001")
    core.claim(config, "TST-001", "coder", create_worktree=True)
    return config.project_root / ".worktrees" / "TST-001"


def commit_work(tree: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        (tree / relative).parent.mkdir(parents=True, exist_ok=True)
        (tree / relative).write_text(text, encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "work")


def body_of(config: core.Config) -> str:
    return frontmatter.parse(core.find_ticket(config, "TST-001").text)[1]


def edit_ticket(config: core.Config, old: str, new: str) -> None:
    ticket = core.find_ticket(config, "TST-001")
    core.write_text(ticket.path, ticket.text.replace(old, new))
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", "edit TST-001")


# --- the honest path (probe C) -----------------------------------------------


def test_factory_path_reaches_done_without_hand_ticking(repo: Path) -> None:
    config = strict_board(repo)
    commit_work(claimed(config), FIX)

    result = core.verify(config, "TST-001")

    assert result.passed, result.output
    assert "RED CHECK" in result.output
    assert core.checkboxes(body_of(config)) == (1, 0)
    git(repo, "merge", "--no-ff", "-m", "merge", "ticket/TST-001")
    assert core.done(config, "TST-001").to_column == "5-done"


# --- fail-fast execution (probe A) -------------------------------------------


def test_an_earlier_failing_line_fails_the_block(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "multiline",
        validation=f'{PY} -c "import sys; sys.exit(3)"\n{PY} -c "print(1)"',
    )
    git(board, "add", "-A")
    git(board, "commit", "-m", "ticket")
    core.claim(config, "TST-001", "coder", create_worktree=False)

    result = core.verify(config, "TST-001")

    assert not result.passed
    assert "line 1 of 2" in result.output
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"


def test_command_lines_join_continuations_and_skip_comments() -> None:
    block = "pytest \\\n  -q tests\n# a comment\n\nInvoke-Thing `\n  -Flag\n"
    assert core.command_lines(block) == ["pytest -q tests", "Invoke-Thing -Flag"]


# --- proof of work (probe B) and the red check -------------------------------


def test_a_branch_without_source_changes_is_refused(repo: Path) -> None:
    config = strict_board(repo)
    commit_work(claimed(config), {"tests/check_app.py": CHECK_APP})

    with pytest.raises(core.GateError, match="changes no source files"):
        core.verify(config, "TST-001")


def test_feature_tests_that_pass_without_the_change_are_refused(repo: Path) -> None:
    config = strict_board(repo)
    green = f'{PY} -c "print(0)"'
    tree = claimed(
        config, validation=green, acceptance=(f"- [ ] f() returns 2 (test: `{green}`)",)
    )
    commit_work(tree, {"src/app.py": FIX["src/app.py"]})

    result = core.verify(config, "TST-001")

    assert not result.passed
    assert "do not prove it" in result.output
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"
    assert (tree / "src" / "app.py").read_text(encoding="utf-8") == FIX["src/app.py"]


# --- the frozen contract (probe D) -------------------------------------------


def test_editing_validation_after_claim_is_refused(repo: Path) -> None:
    config = strict_board(repo)
    claimed(config)
    edit_ticket(config, f"```\n{CHECK}\n```", "```\necho ok\n```")

    with pytest.raises(core.GateError, match="after the ready gate"):
        core.verify(config, "TST-001")


def test_editing_criteria_in_ready_is_refused_at_claim(repo: Path) -> None:
    config = strict_board(repo)
    write_ticket(
        config.board_path, "1-refining", "TST-001", "fix-f", acceptance=(CRITERION,)
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")
    core.ready(config, "TST-001")
    edit_ticket(config, "f() returns 2", "f() returns anything")

    with pytest.raises(core.GateError, match="after the ready gate"):
        core.claim(config, "TST-001", "coder", create_worktree=False)


# --- verify tests what will merge (probe E) ----------------------------------


def test_uncommitted_work_is_refused(repo: Path) -> None:
    config = strict_board(repo)
    tree = claimed(config)
    (tree / "src" / "app.py").write_text(FIX["src/app.py"], encoding="utf-8")
    (tree / "src" / "helper.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(core.GateError, match="uncommitted changes") as error:
        core.verify(config, "TST-001")

    assert "src/app.py" in str(error.value)
    assert "src/helper.py" in str(error.value)


# --- scope covers tests, CI and agent rules (probe F) ------------------------


def test_undeclared_test_and_ci_changes_are_out_of_scope(repo: Path) -> None:
    config = strict_board(repo)
    tree = claimed(config, radius=("src/app.py",))
    commit_work(tree, {**FIX, ".github/workflows/ci.yml": "on: push\n"})

    with pytest.raises(core.GateError, match="outside its blast radius") as error:
        core.verify(config, "TST-001")

    assert "tests/check_app.py" in str(error.value)
    assert ".github/workflows/ci.yml" in str(error.value)


# --- evidence per criterion --------------------------------------------------


def test_only_criteria_whose_own_test_passed_are_ticked(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "mixed",
        acceptance=(f'- [ ] proven (test: `{PY} -c "print(1)"`)', "- [ ] judged by a reviewer"),
    )
    git(board, "add", "-A")
    git(board, "commit", "-m", "ticket")
    core.claim(config, "TST-001", "coder", create_worktree=False)

    assert core.verify(config, "TST-001").passed
    criteria = core.section(body_of(config), "Acceptance criteria")
    assert "- [x] proven" in criteria
    assert "- [ ] judged by a reviewer" in criteria


def test_a_failing_criterion_test_fails_verify(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "failing",
        acceptance=(f'- [ ] broken (test: `{PY} -c "import sys; sys.exit(2)"`)',),
    )
    git(board, "add", "-A")
    git(board, "commit", "-m", "ticket")
    core.claim(config, "TST-001", "coder", create_worktree=False)

    result = core.verify(config, "TST-001")

    assert not result.passed
    assert "[FAIL]" in result.output
    assert core.checkboxes(body_of(config)) == (0, 1)


def test_strict_ready_requires_a_test_per_criterion(repo: Path) -> None:
    config = strict_board(repo)
    write_ticket(
        config.board_path, "1-refining", "TST-001", "vague", acceptance=("- [ ] works well",)
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")

    with pytest.raises(core.GateError, match="name no test"):
        core.ready(config, "TST-001")


def test_regression_command_from_config_is_run(repo: Path) -> None:
    scaffold_board(repo, {"regression_command": f'{PY} -c "import sys; sys.exit(5)"'})
    config = core.load_config(repo)
    write_ticket(config.board_path, "2-ready", "TST-001", "regress")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "ticket")
    core.claim(config, "TST-001", "coder", create_worktree=False)

    result = core.verify(config, "TST-001")

    assert not result.passed
    assert "TIER 2: REGRESSION TESTS" in result.output

