"""Every board move is a handoff: the baton follows the ticket, hooks hear every move and refusal,
and a worker cannot stop before its role's exit condition holds."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from kahnban import core, exit_checks, guard, handoff
from kahnban.cli import main
from conftest import git, write_ticket
from test_factory_gates import CHECK_APP, FIX, claimed, commit_work, factory_board


def baton(repo: Path, ticket_id: str = "TST-001") -> handoff.HandoffBaton:
    found = handoff.read_handoff_baton(repo, ticket_id)
    assert found is not None
    return found


def test_every_move_hands_the_baton_to_whoever_acts_next(repo: Path) -> None:
    config = factory_board(repo)
    (repo / ".agents").mkdir()
    tree = claimed(config)
    assert baton(repo).assigned_role == "coder"
    assert baton(repo).context["last_event"].startswith("claimed by coder")
    mirror = tree / core.HANDOFF_IN_WORKTREE
    assert json.loads(mirror.read_text(encoding="utf-8"))["assigned_role"] == "coder"

    commit_work(tree, {"src/app.py": "def f():\n    return 3\n", "tests/check_app.py": CHECK_APP})
    assert not core.verify(config, "TST-001").passed
    failed = baton(repo)
    assert failed.assigned_role == "coder" and failed.context["last_event"].startswith("verify failed")
    assert not failed.verification_results.feature_tests_passed

    commit_work(tree, FIX)
    assert core.verify(config, "TST-001").passed
    review = baton(repo)
    assert review.assigned_role == "qa_reviewer"
    assert review.verification_results.feature_tests_passed
    assert review.verification_results.regression_tests_passed
    assert review.verification_results.feature_log
    assert json.loads(mirror.read_text(encoding="utf-8"))["assigned_role"] == "qa_reviewer"

    core.approve(config, "TST-001", "qa-reviewer")
    assert baton(repo).assigned_role == "integrator"

    core.reject(config, "TST-001", "qa-reviewer", "the check only covers one input")
    rework = baton(repo)
    assert rework.assigned_role == "coder"
    assert "the check only covers one input" in rework.next_action["prompt"]
    assert not rework.verification_results.feature_tests_passed


def test_hooks_can_veto_a_move_and_hear_every_refusal(board: Path) -> None:
    repo = board
    config = core.load_config(repo)
    hooks_dir = repo / ".kahnban" / "hooks"
    hooks_dir.mkdir(parents=True)
    veto = hooks_dir / "pre-transition.py"
    veto.write_text(
        "import json, sys\n"
        "event = json.load(sys.stdin)\n"
        "if event['to'] == '2-ready':\n"
        "    print('needs a design review first', file=sys.stderr)\n"
        "    sys.exit(2)\n",
        encoding="utf-8",
    )
    (hooks_dir / "on-refusal.py").write_text(
        "import json, sys\n"
        "with open('refusals.jsonl', 'a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(json.load(sys.stdin)) + chr(10))\n",
        encoding="utf-8",
    )
    write_ticket(config.board_path, "1-refining", "TST-001", "fix")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine TST-001")

    with pytest.raises(core.GateError, match="needs a design review first"):
        core.ready(config, "TST-001")
    assert core.find_ticket(config, "TST-001").column == "1-refining"
    refusal = json.loads((repo / "refusals.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert refusal["event"] == "on-refusal" and refusal["gate"] == "ready"
    assert "needs a design review first" in refusal["reason"]

    veto.unlink()
    (hooks_dir / "post-transition.py").write_text(
        "import json, sys\n"
        "with open('moves.json', 'w', encoding='utf-8') as log:\n"
        "    json.dump(json.load(sys.stdin), log)\n",
        encoding="utf-8",
    )
    result = core.ready(config, "TST-001")
    move = json.loads((repo / "moves.json").read_text(encoding="utf-8"))
    assert (move["from"], move["to"], move["commit"]) == ("1-refining", "2-ready", result.commit)


def test_a_worker_cannot_stop_before_its_role_is_done(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = factory_board(repo)
    tree = claimed(config)
    coder = {
        "KAHNBAN_ROLE": "coder",
        "KAHNBAN_TICKET": "TST-001",
        "KAHNBAN_PROJECT_ROOT": str(repo),
        "KAHNBAN_WORKTREE": str(tree),
    }
    assert "no commits yet" in guard.exit_problem("coder", coder)
    (tree / "src" / "app.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    assert "uncommitted changes" in guard.exit_problem("coder", coder)

    # The Stop hook pushes back max_stop_nudges (2) times, then lets the stop through to the
    # runner's own check; a new worker starts with a full budget again.
    for name, value in coder.items():
        monkeypatch.setenv(name, value)
    for _ in range(2):
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"stop_hook_active": true}'))
        assert main(["guard", "--stop"]) == 2
        assert "uncommitted changes" in capsys.readouterr().err
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"stop_hook_active": true}'))
    assert main(["guard", "--stop"]) == 0
    exit_checks.reset_nudges(config, "coder", "TST-001")
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert main(["guard", "--stop"]) == 2
    capsys.readouterr()

    commit_work(tree, FIX)
    assert guard.exit_problem("coder", coder) is None

    assert core.verify(config, "TST-001").passed
    reviewer = {**coder, "KAHNBAN_ROLE": "qa_reviewer"}
    assert "neither approved nor rejected" in guard.exit_problem("qa_reviewer", reviewer)
    core.approve(config, "TST-001", "qa-reviewer")
    assert guard.exit_problem("qa_reviewer", reviewer) is None

    other = claimed(config, ticket_id="TST-002", radius=("src/other.py", "tests/check_other.py"))
    commit_work(other, {"README.md": "scope creep\n"})
    outside = {**coder, "KAHNBAN_TICKET": "TST-002", "KAHNBAN_WORKTREE": str(other)}
    assert "outside the blast radius: README.md" in guard.exit_problem("coder", outside)

    write_ticket(config.board_path, "0-backlog", "TST-003", "idea", acceptance=())
    analyst = {**coder, "KAHNBAN_ROLE": "spec_analyst", "KAHNBAN_TICKET": "TST-003"}
    assert "has no checkboxes" in guard.exit_problem("spec_analyst", analyst)


def test_the_curator_cannot_stop_while_a_recurring_learning_has_no_fix(board: Path) -> None:
    from kahnban import learnings

    env = {"KAHNBAN_ROLE": "curator", "KAHNBAN_PROJECT_ROOT": str(board), "KAHNBAN_TICKET": ""}
    assert guard.exit_problem("curator", env) is None

    for _ in range(2):
        learnings.capture_learning(board, title="Flaky clock", problem="sleep races", ticket_id="TST-001")

    assert "1 recurring learning(s) still need a structural fix ticket" in guard.exit_problem("curator", env)


def test_nudges_are_per_worker_and_reset_for_the_next_one(repo: Path) -> None:
    config = factory_board(repo)
    env = {"KAHNBAN_PROJECT_ROOT": str(repo), "KAHNBAN_TICKET": "TST-001"}

    assert [exit_checks.spend_nudge("coder", env) for _ in range(3)] == [True, True, False]
    assert exit_checks.spend_nudge("qa_reviewer", env)  # another role has its own budget
    exit_checks.reset_nudges(config, "coder", "TST-001")
    assert exit_checks.spend_nudge("coder", env)


def hook_dir(repo: Path) -> Path:
    directory = repo / ".kahnban" / "hooks"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


LOG_REFUSALS = (
    "import json, sys\n"
    "with open('refusals.jsonl', 'a', encoding='utf-8') as log:\n"
    "    log.write(json.dumps(json.load(sys.stdin)) + chr(10))\n"
)


def refused_gates(repo: Path) -> set[str]:
    lines = (repo / "refusals.jsonl").read_text(encoding="utf-8").splitlines()
    return {json.loads(line)["gate"] for line in lines}


def test_a_vetoed_claim_leaves_no_worktree_branch_or_lease(repo: Path) -> None:
    from test_factory_run import ready_ticket

    config = factory_board(repo)
    ready_ticket(config)
    (hook_dir(repo) / "pre-transition.py").write_text(
        "import sys\nprint('freeze: release week', file=sys.stderr)\nsys.exit(2)\n", encoding="utf-8"
    )

    with pytest.raises(core.GateError, match="freeze: release week"):
        core.claim(config, "TST-001", "coder", create_worktree=True)

    assert not (repo / ".worktrees" / "TST-001").exists()
    assert not core.branch_tip(config, "ticket/TST-001")
    assert not core.live_lease(config, "TST-001")
    assert core.find_ticket(config, "TST-001").column == "2-ready"


def test_strict_hooks_refuse_a_move_when_the_veto_hook_itself_fails(repo: Path) -> None:
    from test_factory_run import ready_ticket

    config = factory_board(repo)
    ready_ticket(config)
    (hook_dir(repo) / "pre-transition.py").write_text("raise SystemExit(1)\n", encoding="utf-8")

    strict = core.load_config(repo)
    object.__setattr__(strict, "strict_hooks", True)
    with pytest.raises(core.GateError, match="strict_hooks is on"):
        core.claim(strict, "TST-001", "coder", create_worktree=False)
    assert not (repo / ".worktrees" / "TST-001").exists()

    core.claim(config, "TST-001", "coder", create_worktree=False)  # lenient by default: a broken hook only reports


def test_a_way_out_is_never_vetoed_not_even_by_a_broken_hook_under_strict_hooks(repo: Path) -> None:
    from test_factory_run import ready_ticket

    config = factory_board(repo, autonomy="attended")
    ready_ticket(config)
    (hook_dir(repo) / "pre-transition.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
    strict = core.load_config(repo)
    object.__setattr__(strict, "strict_hooks", True)

    core.escalate(strict, "TST-001", "which currency?")
    core.unblock(strict, "TST-001", "EUR")
    with pytest.raises(core.GateError, match="strict_hooks is on"):
        core.claim(strict, "TST-001", "coder", create_worktree=False)  # a column move still is


def test_refusals_of_every_error_type_reach_on_refusal(repo: Path) -> None:
    config = factory_board(repo)
    (hook_dir(repo) / "on-refusal.py").write_text(LOG_REFUSALS, encoding="utf-8")

    with pytest.raises(core.KahnbanError):  # a missing ticket is a plain KahnbanError, not a GateError
        core.countersign(config, "TST-404")

    lines = [json.loads(line) for line in (repo / "refusals.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {line["gate"] for line in lines} == {"countersign"}
    assert all(line["kind"] for line in lines)


def test_every_command_that_can_refuse_tells_the_on_refusal_hook(repo: Path) -> None:
    from test_factory_run import ready_ticket

    config = factory_board(repo)
    ready_ticket(config)
    (hook_dir(repo) / "on-refusal.py").write_text(LOG_REFUSALS, encoding="utf-8")

    refusals = [
        lambda: core.escalate(config, "TST-001", ""),
        lambda: core.unblock(config, "TST-001", ""),
        lambda: core.confirm(config, "TST-001"),
        lambda: core.move(config, "TST-001", "2-ready", reason=""),
        lambda: core.cleanup(config, "TST-001"),
    ]
    for attempt in refusals:
        with pytest.raises(core.KahnbanError):
            attempt()

    assert refused_gates(repo) == {"escalate", "unblock", "confirm", "move", "cleanup"}


def test_a_guard_refusal_reaches_the_on_refusal_hook(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory_board(repo)
    (hook_dir(repo) / "on-refusal.py").write_text(LOG_REFUSALS, encoding="utf-8")
    monkeypatch.setenv("KAHNBAN_ROLE", "qa_reviewer")
    monkeypatch.setenv("KAHNBAN_PROJECT_ROOT", str(repo))
    payload = {"tool_name": "Bash", "tool_input": {"command": "kahnban claim TST-001"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    assert main(["guard"]) == 2
    assert "not a qa_reviewer's" in capsys.readouterr().err
    assert refused_gates(repo) == {"guard"}


def test_a_move_survives_an_unwritable_baton_but_the_next_worker_is_not_started_on_it(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_factory_run import ready_ticket

    config = factory_board(repo)
    (repo / ".agents").mkdir()
    ready_ticket(config)

    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(handoff, "write_handoff_baton", refuse)

    claimed_result = core.claim(config, "TST-001", "coder", create_worktree=False)
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"
    assert any("handoff baton not refreshed" in message for message in claimed_result.messages)
    with pytest.raises(core.KahnbanError, match="cannot be written"):
        core.refresh_baton_strict(config, "TST-001", "starting the coder")


def test_a_parked_ticket_tells_the_person_what_to_run(repo: Path) -> None:
    from test_factory_run import ready_ticket

    config = factory_board(repo)
    (repo / ".agents").mkdir()
    ready_ticket(config)

    core.escalate(config, "TST-001", "which currency?")
    parked = baton(repo)
    assert parked.assigned_role == "human"
    assert "which currency?" in parked.next_action["prompt"]
    assert parked.next_action["command"].startswith("kahnban unblock TST-001 --reason")

    core.unblock(config, "TST-001", "EUR")
    core.escalate(config, "TST-001", f"{handoff.ATTENDED_REASON} review TST-001, then 'kahnban confirm TST-001'")
    assert baton(repo).next_action["command"] == "kahnban confirm TST-001"
