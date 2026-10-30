"""``kahnban run --jobs N``: coder workers overlap; every board transition stays on the main thread."""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import pytest

from kahnban import core, dispatcher, runner
from kahnban.cli import main as cli_main
from conftest import git, write_ticket
from test_factory_gates import CHECK_APP, PY, factory_board

# The coder drops a marker and waits for the other coder's marker, so it can only finish if both run at once.
WORKER = """\
import os, subprocess, sys, time
sys.stdin.read()
if os.environ["KAHNBAN_ROLE"] != "coder":
    sys.exit(0)
root, ticket = os.environ["KAHNBAN_PROJECT_ROOT"], os.environ["KAHNBAN_TICKET"]
open(os.path.join(root, "started-" + ticket), "w").close()
deadline = time.time() + {wait}
while len([n for n in os.listdir(root) if n.startswith("started-")]) < 2:
    if time.time() > deadline:
        sys.exit(3)
    time.sleep(0.05)
n = ticket[-3:]
with open("src/app_" + n + ".py", "w") as handle:
    handle.write("def f():\\n    return 2\\n")
os.makedirs("tests", exist_ok=True)
with open("tests/check_" + n + ".py", "w") as handle:
    handle.write({check_app!r}.replace("from app import", "from app_" + n + " import"))
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "commit", "-qm", "fix f"], check=True)
"""


def two_ready_tickets(repo: Path, tmp_path: Path, wait: int) -> core.Config:
    worker = tmp_path / "worker.py"
    worker.write_text(WORKER.format(check_app=CHECK_APP, wait=wait), encoding="utf-8")
    config = factory_board(repo, workers={"default": f"{PY} {worker}"})
    for ticket in ("TST-001", "TST-002"):
        n = ticket[-3:]  # disjoint radii: the dispatcher only hands out tickets whose radius is free
        check = f"{PY} tests/check_{n}.py"
        write_ticket(config.board_path, "1-refining", ticket, "fix", acceptance=(f"- [ ] f() returns 2 (test: `{check}`)",),
                     blast_radius=(f"src/app_{n}.py", f"tests/check_{n}.py"), validation=check)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")
    for ticket in ("TST-001", "TST-002"):
        core.ready(config, ticket)
    return config


def test_two_coders_run_at_once_and_both_tickets_are_verified(repo: Path, tmp_path: Path) -> None:
    config = two_ready_tickets(repo, tmp_path, wait=20)

    result = runner.run(config, max_steps=6, jobs=2, echo=lambda line: None)

    # Neither coder could finish without seeing the other's marker, so they overlapped.
    assert sorted(step.ticket_id for step in result.steps if "verified" in step.outcome) == ["TST-001", "TST-002"], [
        step.outcome for step in result.steps
    ]
    assert {core.find_ticket(config, t).column for t in ("TST-001", "TST-002")} == {"4-verifying"}


def test_one_job_stays_sequential(repo: Path, tmp_path: Path) -> None:
    config = two_ready_tickets(repo, tmp_path, wait=1)  # the first coder times out waiting for a peer that never starts

    try:
        runner.run(config, max_steps=2, jobs=1, echo=lambda line: None)
    except runner.RunStop:
        pass

    assert not (repo / "started-TST-002").exists()


def _claimed_ticket(config: core.Config, ticket_id: str) -> Path:
    """A ready-made, in-progress ticket (claimed, leased, worktree provisioned)."""
    n = ticket_id[-3:]
    check = f"{PY} tests/check_{n}.py"
    write_ticket(
        config.board_path,
        "1-refining",
        ticket_id,
        "fix",
        acceptance=(f"- [ ] f() returns 2 (test: `{check}`)",),
        blast_radius=(f"src/app_{n}.py", f"tests/check_{n}.py"),
        validation=check,
    )
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", f"refine {ticket_id}")
    core.ready(config, ticket_id)
    core.claim(config, ticket_id, "coder", create_worktree=True)
    return config.project_root / ".worktrees" / ticket_id


def _commit_fix(tree: Path, ticket_id: str) -> None:
    n = ticket_id[-3:]
    (tree / "src").mkdir(exist_ok=True)
    (tree / f"src/app_{n}.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    (tree / "tests").mkdir(exist_ok=True)
    (tree / f"tests/check_{n}.py").write_text(
        CHECK_APP.replace("from app import", f"from app_{n} import"), encoding="utf-8"
    )
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "fix")


def _flight(config: core.Config, tmp_path: Path, jobs: int = 2) -> tuple[runner._Flight, runner.RunResult]:
    result = runner.RunResult(log_path=tmp_path / "run.log")
    return runner._Flight(config, result, lambda line: None, jobs), result


def test_run_stop_logs_a_step(repo: Path, tmp_path: Path) -> None:
    # A coder that exits 1 under --jobs 2: harvest must log a Step for that ticket
    # before the run stops, not just raise.
    config = factory_board(repo)
    flight, result = _flight(config, tmp_path)
    rec = dispatcher.DispatchRecommendation(
        action="claim_and_implement", assigned_role="coder", ticket_id="TST-001", prompt="go"
    )
    future: Future[int] = Future()
    future.set_exception(runner.RunStop("coder worker command exited 1"))
    flight.active[future] = rec

    flight.harvest(1)

    assert flight.stop is not None
    steps = [step for step in result.steps if step.ticket_id == "TST-001"]
    assert len(steps) == 1, result.steps
    assert "exited 1" in steps[0].outcome


def test_submit_failure_drops_the_lease(repo: Path, tmp_path: Path) -> None:
    config = factory_board(repo)
    n = "001"
    check = f"{PY} tests/check_{n}.py"
    write_ticket(
        config.board_path,
        "1-refining",
        "TST-001",
        "fix",
        acceptance=(f"- [ ] f() returns 2 (test: `{check}`)",),
        blast_radius=(f"src/app_{n}.py", f"tests/check_{n}.py"),
        validation=check,
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")
    core.ready(config, "TST-001")

    flight, result = _flight(config, tmp_path)
    assert flight.pool is not None
    flight.pool.submit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pool is broken"))  # type: ignore[method-assign]
    rec = dispatcher.DispatchRecommendation(
        action="claim_and_implement", assigned_role="coder", ticket_id="TST-001", prompt="go"
    )

    with pytest.raises(RuntimeError):
        flight.start(1, rec)

    assert core.live_lease(config, "TST-001") == ""


def test_harvest_survives_one_worker_error(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = factory_board(repo)
    tree1 = _claimed_ticket(config, "TST-001")
    _commit_fix(tree1, "TST-001")
    tree2 = _claimed_ticket(config, "TST-002")
    _commit_fix(tree2, "TST-002")

    real_verify = core.verify

    def flaky_verify(cfg: core.Config, ticket_id: str, **kwargs: object) -> object:
        if ticket_id == "TST-001":
            raise OSError("disk exploded")
        return real_verify(cfg, ticket_id, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(core, "verify", flaky_verify)

    flight, result = _flight(config, tmp_path)
    rec1 = dispatcher.DispatchRecommendation(
        action="claim_and_implement", assigned_role="coder", ticket_id="TST-001", prompt="go"
    )
    rec2 = dispatcher.DispatchRecommendation(
        action="claim_and_implement", assigned_role="coder", ticket_id="TST-002", prompt="go"
    )
    f1: Future[int] = Future()
    f2: Future[int] = Future()
    f1.set_result(0)
    f2.set_result(0)
    flight.active[f1] = rec1
    flight.active[f2] = rec2

    flight.harvest(1)

    assert core.live_lease(config, "TST-001") == ""
    assert core.live_lease(config, "TST-002") == ""
    outcomes = {step.ticket_id: step.outcome for step in result.steps}
    assert "refused:" in outcomes["TST-001"], outcomes
    assert "verified" in outcomes["TST-002"], outcomes


# Both coders sleep well past the 2-step budget it takes to merely start them, so
# neither can be harvested before 'max_steps' is spent (no race with a fast coder).
DELAYED_WORKER = """\
import os, subprocess, sys, time
sys.stdin.read()
if os.environ["KAHNBAN_ROLE"] != "coder":
    sys.exit(0)
time.sleep(0.5)
ticket = os.environ["KAHNBAN_TICKET"]
n = ticket[-3:]
with open("src/app_" + n + ".py", "w") as handle:
    handle.write("def f():\\n    return 2\\n")
os.makedirs("tests", exist_ok=True)
with open("tests/check_" + n + ".py", "w") as handle:
    handle.write({check_app!r}.replace("from app import", "from app_" + n + " import"))
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "commit", "-qm", "fix f"], check=True)
"""


def test_max_steps_leaves_workers_unverified(repo: Path, tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(DELAYED_WORKER.format(check_app=CHECK_APP), encoding="utf-8")
    config = factory_board(repo, workers={"default": f"{PY} {worker}"})
    for ticket in ("TST-001", "TST-002"):
        n = ticket[-3:]
        check = f"{PY} tests/check_{n}.py"
        write_ticket(
            config.board_path,
            "1-refining",
            ticket,
            "fix",
            acceptance=(f"- [ ] f() returns 2 (test: `{check}`)",),
            blast_radius=(f"src/app_{n}.py", f"tests/check_{n}.py"),
            validation=check,
        )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")
    for ticket in ("TST-001", "TST-002"):
        core.ready(config, ticket)

    # The 2-step budget is only enough to start both coders; neither can finish in
    # time (each sleeps 0.5s), so the run must stop without verifying either.
    result = runner.run(config, max_steps=2, jobs=2, echo=lambda line: None)

    assert "unverified" in result.stopped
    for ticket in ("TST-001", "TST-002"):
        assert ticket in result.stopped
        assert core.find_ticket(config, ticket).column == config.in_progress_column
        assert core.live_lease(config, ticket) == ""


def test_jobs_rejects_non_positive() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli_main(["run", "--jobs", "0"])

    assert exit_info.value.code != 0
