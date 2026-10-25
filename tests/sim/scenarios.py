"""The scenario catalogue. Each one sets up a World; ``execute`` runs it and builds the scorecard."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kahnban import __version__

from .world import Outcome, World


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    set: str  # "fast" runs on every pull request, "full" nightly
    tickets: int
    build: Callable[[World], None]
    expect_refusals: int = 0  # cheat attempts the guard or a gate must refuse


def s1(world: World) -> None:
    """One bare backlog idea: refine, implement, review, merge, close."""
    world.add_ticket(1, column="0-backlog")


SCENARIOS: list[Scenario] = [
    Scenario("S1", "One idea from the backlog to done, honest agents", "fast", 1, s1),
]


def scorecard(scenario: Scenario, world: World, outcome: Outcome) -> dict[str, Any]:
    status = json.loads((world.repo / "plans" / "status.json").read_text(encoding="utf-8")).get("metrics", {})
    per_ticket = status.get("tickets", {})
    turns = [entry["prompt_bytes"] for entry in outcome.agent_log if entry.get("event") == "turn"]
    refused = [entry for entry in outcome.agent_log if entry.get("event") == "refused"]
    summary = outcome.checker.summary()
    count = max(world.count, 1)
    return {
        "scenario": scenario.id,
        "title": scenario.title,
        "seed": world.seed,
        "ok": all(item["pass"] for item in summary.values()),
        "stopped": outcome.result.stopped,
        "invariants": summary,
        "metrics": {
            "done": status.get("done", 0),
            "first_pass_yield": status.get("first_pass_yield"),
            "rejections_per_ticket": round(sum(m.get("rejections", 0) for m in per_ticket.values()) / count, 2),
            "verify_attempts_per_ticket": round(sum(m.get("verify_attempts", 0) for m in per_ticket.values()) / count, 2),
            "steps_to_done": len(outcome.result.steps),
            "escalation_rate": round(len(outcome.result.parked) / count, 2),
            "engine_commits_per_ticket": round(outcome.commits / count, 2),
            "worker_prompt_bytes": round(sum(turns) / len(turns)) if turns else 0,
            "guard_refusals": outcome.result.guard_refusals,
            "false_blocks": len(refused) if scenario.expect_refusals == 0 else 0,
            "wall_seconds": round(outcome.seconds, 1),
        },
        "steps": [
            {"n": s.number, "action": s.action, "ticket": s.ticket_id, "outcome": s.outcome[:200]}
            for s in outcome.result.steps
        ],
    }


def execute(scenario: Scenario, *, keep: bool = False, seed: int = 0) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix=f"sim-{scenario.id}-"))
    world = World(root, tickets=scenario.tickets, seed=seed)
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
