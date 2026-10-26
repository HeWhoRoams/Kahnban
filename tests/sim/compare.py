"""Compare two scorecards: what broke, what got worse, what got better."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# name -> (direction, tolerance). Tolerance is absolute, except worker_prompt_bytes (a fraction).
METRICS: dict[str, tuple[str, float]] = {
    "done": ("higher", 0),
    "first_pass_yield": ("higher", 0),
    "rejections_per_ticket": ("lower", 0),
    "verify_attempts_per_ticket": ("lower", 0),
    "steps_to_done": ("lower", 0),
    "escalation_rate": ("lower", 0),
    "engine_commits_per_ticket": ("lower", 0),
    "worker_prompt_bytes": ("lower", 0.03),
    "false_blocks": ("lower", 0),
    "recovery_rate": ("higher", 0),
    "crashes_injected": ("exact", 0),
    "cheats_stopped": ("higher", 0),
    "guard_refusals": ("exact", 0),
    "cheats_attempted": ("exact", 0),
}
IGNORED = {"wall_seconds"}


@dataclass
class Comparison:
    broken: list[str] = field(default_factory=list)
    worse: list[str] = field(default_factory=list)
    better: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.broken and not self.worse


def normalize(scorecard: dict[str, Any]) -> dict[str, Any]:
    """What a baseline keeps: results, not paths, timings or outcome text."""
    scenarios = {}
    for ident, card in scorecard["scenarios"].items():
        if all(isinstance(item, bool) for item in card["invariants"].values()):
            scenarios[ident] = card  # already a baseline
            continue
        scenarios[ident] = {
            "title": card["title"],
            "ok": card["ok"],
            "known_gap": card.get("known_gap", ""),
            "invariants": {key: item["pass"] for key, item in card["invariants"].items()},
            "expectations": {key: item["pass"] for key, item in card.get("expectations", {}).items()},
            "metrics": {key: value for key, value in card["metrics"].items() if key not in IGNORED},
        }
    return {"engine": scorecard.get("engine"), "scenarios": scenarios, "unstable": sorted(scorecard.get("unstable", []))}


def stability_report(cards: list[dict[str, Any]]) -> list[str]:
    """'S3 steps_to_done' for every metric whose value differs between runs of one unchanged tree."""
    moved = set()
    for ident in cards[0]["scenarios"]:
        for name in cards[0]["scenarios"][ident]["metrics"]:
            if name in IGNORED:
                continue
            if len({repr(card["scenarios"][ident]["metrics"].get(name)) for card in cards}) > 1:
                moved.add(f"{ident} {name}")
    return sorted(moved)


def _moved(name: str, old: Any, new: Any) -> str | None:
    """'worse', 'better' or None for one metric."""
    if old == new or old is None or new is None:
        return None
    direction, tolerance = METRICS.get(name, ("exact", 0))
    slack = abs(old) * tolerance if name == "worker_prompt_bytes" else tolerance
    if abs(new - old) <= slack:
        return None
    if direction == "exact":
        return "worse"
    improved = new > old if direction == "higher" else new < old
    return "better" if improved else "worse"


def compare(old: dict[str, Any], new: dict[str, Any]) -> Comparison:
    result = Comparison()
    unstable = set(old.get("unstable", []))
    for ident, before in old["scenarios"].items():
        after = new["scenarios"].get(ident)
        if after is None:
            result.broken.append(f"{ident}: no longer run")
            continue
        if before["ok"] and not after["ok"]:
            result.broken.append(f"{ident}: held every rule before and no longer does")
        for key, passed in before["invariants"].items():
            if passed and not after["invariants"].get(key, False):
                result.broken.append(f"{ident} {key}: passed before, fails now")
            if not passed and after["invariants"].get(key, False):
                result.better.append(f"{ident} {key}: failed before, passes now")
        for key, passed in before["expectations"].items():
            if passed and not after["expectations"].get(key, False):
                result.broken.append(f"{ident} expectation '{key}': met before, not now")
        for name, value in after["metrics"].items():
            if f"{ident} {name}" in unstable:
                continue
            verdict = _moved(name, before["metrics"].get(name), value)
            if verdict:
                line = f"{ident} {name}: {before['metrics'].get(name)} -> {value}"
                (result.worse if verdict == "worse" else result.better).append(line)
    return result


def report(result: Comparison) -> str:
    sections = [("BROKEN (blocks)", result.broken), ("WORSE (blocks unless intended)", result.worse), ("BETTER", result.better)]
    lines = []
    for title, items in sections:
        lines.append(f"{title}: {len(items)}")
        lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)
