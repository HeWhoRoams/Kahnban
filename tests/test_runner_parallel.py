"""``kahnban run --jobs N``: coder workers overlap; every board transition stays on the main thread."""

from __future__ import annotations

from pathlib import Path

from kahnban import core, runner
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
