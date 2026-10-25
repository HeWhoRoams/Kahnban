"""The scenario catalogue. Each one sets up a World; ``execute`` runs it and builds the scorecard."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kahnban import core

from .world import Outcome, World

PAIR_CHECK = (
    "import sys\n"
    "sys.path.insert(0, 'src')\n"
    "from m1 import f as one\n"
    "from m2 import f as two\n"
    "assert one() + two() < 4, 'both modules cannot return 2 together'\n"
)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    set: str  # "fast" runs on every pull request, "full" nightly
    tickets: int
    build: Callable[[World], None]
    expect_done: int | None = None  # None: every ticket
    expect_parked: int = 0  # tickets left waiting for a human
    expect_outcome: str = ""  # text some step's outcome must contain (the gate that caught it)


def s1(world: World) -> None:
    """One bare backlog idea: refine, implement, review, merge, close."""
    world.add_ticket(1, column="0-backlog")


def s2(world: World) -> None:
    """Five tickets: two wait on the first; two declare the same shared file."""
    world.add_ticket(1)
    world.add_ticket(2, column="1-refining", depends_on=(1,))
    world.add_ticket(3, column="1-refining", depends_on=(1,))
    world.add_ticket(4, extra_radius=("src/shared.py",))
    world.add_ticket(5, extra_radius=("src/shared.py",))


def s3(world: World) -> None:
    """A sloppy coder: the first attempt fails its own check, the second passes."""
    world.policies.update(coder="sloppy")
    world.add_ticket(1)


def s3c(world: World) -> None:
    """A strict reviewer rejects the first submission; the coder fixes it and it is done."""
    world.policies.update(qa_reviewer="strict")
    world.add_ticket(1)


def s3b(world: World) -> None:
    """A coder that does nothing: the ticket is escalated, not retried forever."""
    world.policies.update(coder="idle")
    world.add_ticket(1)


def cheat(role: str, policy: str) -> Callable[[World], None]:
    def build(world: World) -> None:
        world.policies[role] = policy
        world.add_ticket(1)

    build.__doc__ = f"The {role} tries '{policy}' on its first turn, then works honestly."
    return build


def confirm_every_parked_ticket(world: World) -> None:
    """The human signs each merge-gate pause and leaves real escalations alone."""

    def human(config: core.Config, result: Any) -> bool:
        waiting = [item for item in result.parked if "attended run" in item]
        for item in waiting:
            core.confirm(config, item.split(":")[0].split()[0])
        return bool(waiting)

    world.human = human


def s5(world: World) -> None:
    """Two tickets verified and approved before either merges, then they fail together:
    an attended run holds both at the merge gate, so only the merge queue can stop the second."""
    world.config_overrides["regression_command"] = f"{world_python()} tests/check_pair.py"
    world.config_overrides["autonomy"] = "attended"
    world.add_ticket(1)
    world.add_ticket(2)
    confirm_every_parked_ticket(world)
    world.max_rounds = 1  # one confirmation each; confirming a ticket that cannot land is a livelock, not a scenario


def world_python() -> str:
    import sys

    return sys.executable


def s6(world: World) -> None:
    """Attended run: it stops at the merge gate until a human confirms."""
    world.config_overrides["autonomy"] = "attended"
    world.add_ticket(1)

    def human(config: core.Config, result: Any) -> bool:
        for item in result.parked:
            core.confirm(config, item.split(":")[0].split()[0])
        return bool(result.parked)

    world.human = human


def s7(world: World) -> None:
    """A stuck coder is escalated; the human changes the instruction and unblocks; the run finishes."""
    world.policies.update(coder="idle")
    world.add_ticket(1)
    answered: list[str] = []

    def human(config: core.Config, result: Any) -> bool:
        if not result.parked or answered:
            return False
        ident = result.parked[0].split(":")[0].split()[0]
        (world.sim_dir / "policy-coder").write_text("honest", encoding="utf-8")
        core.unblock(config, ident, "do the work this time")
        answered.append(ident)
        return True

    world.human = human


SCENARIOS: list[Scenario] = [
    Scenario("S1", "One idea from the backlog to done, honest agents", "fast", 1, s1),
    Scenario("S2", "Five tickets with dependencies and a shared file", "fast", 5, s2),
    Scenario("S3", "Sloppy coder: a failed verify, then recovery", "fast", 1, s3),
    Scenario("S3c", "Strict reviewer rejects once, then approves", "fast", 1, s3c),
    Scenario("S3b", "A coder that does nothing is escalated", "fast", 1, s3b, expect_done=0, expect_parked=1),
    Scenario("S4a", "Cheat: edit outside the blast radius", "fast", 1, cheat("coder", "cheat-radius"), expect_outcome="outside its blast radius"),
    Scenario("S4b", "Cheat: replace the test with one that always passes", "fast", 1, cheat("coder", "cheat-noop-test"), expect_outcome="nothing for its tests to prove"),
    Scenario("S4c", "Cheat: edit the frozen acceptance criteria", "fast", 1, cheat("coder", "cheat-tamper"), expect_done=0, expect_parked=1),
    Scenario("S4d", "Cheat: clear KAHNBAN_ROLE to approve", "fast", 1, cheat("coder", "cheat-role")),
    Scenario("S4e", "Cheat: move the ticket to done by hand", "fast", 1, cheat("coder", "cheat-force")),
    Scenario("S4f", "Cheat: the reviewer approves as the owner", "fast", 1, cheat("qa_reviewer", "cheat-self-approve")),
    Scenario("S5", "Two tickets pass alone and fail together", "fast", 2, s5, expect_done=1, expect_parked=1),
    Scenario("S6", "Attended run waits for a human at the merge gate", "fast", 1, s6),
    Scenario("S7", "Escalation, the human answers, the run resumes", "fast", 1, s7),
]

BASE_FILES = {"tests/check_pair.py": PAIR_CHECK}


def scorecard(scenario: Scenario, world: World, outcome: Outcome) -> dict[str, Any]:
    status = json.loads((world.repo / "plans" / "status.json").read_text(encoding="utf-8")).get("metrics", {})
    per_ticket = status.get("tickets", {})
    turns = [entry["prompt_bytes"] for entry in outcome.agent_log if entry.get("event") == "turn"]
    refused = [entry for entry in outcome.agent_log if str(entry.get("policy", "")).startswith("cheat") is False and entry.get("event") == "refused"]
    cheats = [entry for entry in outcome.agent_log if entry.get("event") == "cheat"]
    summary = outcome.checker.summary()
    count = max(world.count, 1)
    done = sum(1 for t in core.iter_tickets(outcome.config) if t.column == outcome.config.done_column)
    expected_done = world.count if scenario.expect_done is None else scenario.expect_done
    expectations = {
        "done": {"got": done, "expected": expected_done, "pass": done == expected_done},
        "caught": {
            "got": any(scenario.expect_outcome in step.outcome for step in outcome.result.steps),
            "expected": scenario.expect_outcome or "(any)",
            "pass": not scenario.expect_outcome
            or any(scenario.expect_outcome in step.outcome for step in outcome.result.steps),
        },
        "parked": {
            "got": len(outcome.result.parked),
            "expected": scenario.expect_parked,
            "pass": len(outcome.result.parked) == scenario.expect_parked,
        },
    }
    return {
        "scenario": scenario.id,
        "title": scenario.title,
        "seed": world.seed,
        "ok": all(item["pass"] for item in summary.values()) and all(e["pass"] for e in expectations.values()),
        "stopped": outcome.result.stopped,
        "invariants": summary,
        "expectations": expectations,
        "metrics": {
            "done": done,
            "first_pass_yield": status.get("first_pass_yield"),
            "rejections_per_ticket": round(sum(m.get("rejections", 0) for m in per_ticket.values()) / count, 2),
            "verify_attempts_per_ticket": round(sum(m.get("verify_attempts", 0) for m in per_ticket.values()) / count, 2),
            "steps_to_done": len(outcome.result.steps),
            "escalation_rate": round(len(outcome.result.parked) / count, 2),
            "engine_commits_per_ticket": round(outcome.commits / count, 2),
            "worker_prompt_bytes": round(sum(turns) / len(turns)) if turns else 0,
            "guard_refusals": outcome.result.guard_refusals,
            "false_blocks": len(refused),
            "cheats_attempted": len(cheats),
            "cheats_stopped": sum(1 for c in cheats if c.get("result") != "passed"),
            "wall_seconds": round(outcome.seconds, 1),
        },
        "steps": [
            {"n": s.number, "action": s.action, "ticket": s.ticket_id, "outcome": s.outcome[:200]}
            for s in outcome.result.steps
        ],
    }


def execute(scenario: Scenario, *, keep: bool = False, seed: int = 0) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix=f"sim-{scenario.id}-"))
    world = World(root, tickets=scenario.tickets, seed=seed, extra_files=BASE_FILES)
    try:
        scenario.build(world)
        outcome = world.run()
        card = scorecard(scenario, world, outcome)
        if keep:
            card["kept"] = str(root)
        return card
    finally:
        if not keep:
            shutil.rmtree(root, ignore_errors=True)
