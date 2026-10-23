"""Each gate refuses the dishonest input that once got past it (audit probes A-J)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from kahnban import core, dispatcher, frontmatter, gitops
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
    ticket_id: str = "TST-001",
    validation: str = CHECK,
    acceptance: tuple[str, ...] = (CRITERION,),
    radius: tuple[str, ...] = ("src/app.py", "tests/check_app.py"),
) -> Path:
    write_ticket(
        config.board_path,
        "1-refining",
        ticket_id,
        "fix",
        acceptance=acceptance,
        blast_radius=radius,
        validation=validation,
    )
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", f"refine {ticket_id}")
    core.ready(config, ticket_id)
    core.claim(config, ticket_id, "coder", create_worktree=True)
    return config.project_root / ".worktrees" / ticket_id


def factory_board(repo: Path, **overrides: object) -> core.Config:
    """What `kahnban init` writes: proof, review and integration all required."""
    return strict_board(repo, require_review=True, require_integration=True, **overrides)


def verified(
    config: core.Config, ticket_id: str = "TST-001", files: dict[str, str] = FIX, **kwargs: object
) -> Path:
    tree = claimed(config, ticket_id=ticket_id, **kwargs)  # type: ignore[arg-type]
    commit_work(tree, files)
    result = core.verify(config, ticket_id)
    assert result.passed, result.output
    return tree


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


# --- rejection routes the ticket back (probe G) ------------------------------


def test_reject_sends_the_ticket_back_and_it_can_be_reverified(repo: Path) -> None:
    config = factory_board(repo)
    tree = verified(config)

    core.reject(config, "TST-001", "qa", "cover the overflow case")

    assert core.find_ticket(config, "TST-001").column == "3-in-progress"
    body = body_of(config)
    assert core.checkboxes(body) == (0, 1)
    assert "cover the overflow case" in core.section(body, "Log")
    recommendation = dispatcher.resolve_next_action(config)
    assert recommendation.assigned_role == "coder"
    assert recommendation.ticket_id == "TST-001"
    commit_work(tree, {"src/app.py": "def f():\n    return 2  # overflow-safe\n"})
    assert core.verify(config, "TST-001").passed


# --- approval by someone other than the owner (probe H) ----------------------


def test_the_owner_cannot_approve_and_done_needs_an_approval(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)

    with pytest.raises(core.GateError, match="different reviewer"):
        core.approve(config, "TST-001", "Coder")
    with pytest.raises(core.GateError, match="not approved"):
        core.merge(config, "TST-001")
    git(repo, "merge", "--no-ff", "-m", "self-merge", "ticket/TST-001")
    with pytest.raises(core.GateError, match="not approved") as error:
        core.done(config, "TST-001")
    assert "not integrated" in str(error.value)


def test_an_approval_covers_only_the_commit_it_saw(repo: Path) -> None:
    config = factory_board(repo)
    tree = verified(config)
    core.approve(config, "TST-001", "reviewer")
    commit_work(tree, {"src/app.py": "def f():\n    return 2\n\n\nLATE = 1\n"})

    with pytest.raises(core.GateError, match="not approved at"):
        core.merge(config, "TST-001")
    with pytest.raises(core.GateError, match="moved since verify"):
        core.approve(config, "TST-001", "reviewer")


def test_dispatcher_hands_approved_tickets_to_the_integrator(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    assert dispatcher.resolve_next_action(config).action == "review_and_gate"

    core.approve(config, "TST-001", "reviewer")

    recommendation = dispatcher.resolve_next_action(config)
    assert recommendation.action == "merge_and_close"
    assert recommendation.command == "kahnban merge TST-001 && kahnban done TST-001"


# --- the merge queue tests the merged result (probe J) -----------------------


def _check(module: str, name: str, value: int) -> str:
    return (
        f"import sys\nsys.path.insert(0, 'src')\nfrom {module} import {name}\n"
        f"assert {name} == {value}, {name}\n"
    )


def test_merge_queue_refuses_what_only_breaks_main_in_combination(repo: Path) -> None:
    config = factory_board(repo, regression_command=f"{PY} tests/check_sum.py")
    (repo / "src" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (repo / "src" / "b.py").write_text("Y = 1\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "check_sum.py").write_text(
        "import sys\nsys.path.insert(0, 'src')\nfrom a import X\nfrom b import Y\n"
        "assert X + Y < 4, X + Y\n",
        encoding="utf-8",
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "X + Y must stay below 4")
    for ticket_id, module, name in (("TST-001", "a", "X"), ("TST-002", "b", "Y")):
        check = f"{PY} tests/check_{module}.py"
        verified(
            config,
            ticket_id,
            {f"src/{module}.py": f"{name} = 2\n", f"tests/check_{module}.py": _check(module, name, 2)},
            validation=check,
            acceptance=(f"- [ ] {name} is 2 (test: `{check}`)",),
            radius=(f"src/{module}.py", f"tests/check_{module}.py"),
        )
        core.approve(config, ticket_id, "reviewer")

    assert core.merge(config, "TST-001").passed
    main_before = gitops.rev_parse(repo, "main")

    second = core.merge(config, "TST-002")

    assert not second.passed
    assert "INTEGRATION: REGRESSION TESTS" in second.output
    # main only gained the board commit that logs the refusal; no code landed
    assert all(path.startswith("plans/") for path in gitops.diff_names(repo, main_before, "main"))
    assert (repo / "src" / "b.py").read_text(encoding="utf-8") == "Y = 1\n"
    assert core.find_ticket(config, "TST-002").column == "4-verifying"
    with pytest.raises(core.GateError, match="not integrated"):
        core.done(config, "TST-002")
    assert core.done(config, "TST-001").to_column == "5-done"
    assert not (repo / ".worktrees" / ".merge-TST-002").exists()


def test_merge_refuses_a_conflict_and_leaves_main_alone(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    core.approve(config, "TST-001", "reviewer")
    (repo / "src" / "app.py").write_text("def f():\n    return 3\n", encoding="utf-8")
    git(repo, "commit", "-am", "main changes the same line")
    main_before = gitops.rev_parse(repo, "main")

    with pytest.raises(core.GateError, match="does not merge cleanly"):
        core.merge(config, "TST-001")

    assert gitops.rev_parse(repo, "main") == main_before
    assert not (repo / ".worktrees" / ".merge-TST-001").exists()


# --- a lock held through a long test run is not "stale" ----------------------


def test_a_lock_is_not_broken_before_its_holder_deadline(board: Path) -> None:
    config = core.load_config(board)
    lock = config.board_path / core.LOCK_NAME
    long_ago = time.time() - 10 * core.LOCK_STALE_SECONDS
    lock.write_text(f"pid=1 at=then until={int(time.time()) + 3600}\n", encoding="utf-8")
    os.utime(lock, (long_ago, long_ago))

    with pytest.raises(core.LockError):
        with core.board_lock(config, max_retries=1):
            pass

    lock.write_text("pid=1 at=then\n", encoding="utf-8")
    os.utime(lock, (long_ago, long_ago))
    with core.board_lock(config, max_retries=2) as warnings:
        assert any("stale" in warning for warning in warnings)
