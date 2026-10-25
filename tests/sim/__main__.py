"""``python tests/run_sim.py run [IDS...] [--set fast|full|all] [--out FILE] [--keep]`` and ``list``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kahnban import __version__

from .scenarios import SCENARIOS, execute


def chosen(args: argparse.Namespace) -> list:
    if args.ids:
        wanted = {item.upper() for item in args.ids}
        picked = [s for s in SCENARIOS if s.id.upper() in wanted]
        missing = wanted - {s.id.upper() for s in picked}
        if missing:
            sys.exit(f"unknown scenario(s): {', '.join(sorted(missing))}")
        return picked
    return [s for s in SCENARIOS if args.set in ("all", s.set)]


def show(card: dict) -> None:
    mark = "PASS" if card["ok"] else "FAIL"
    metrics = card["metrics"]
    print(
        f"[{mark}] {card['scenario']} {card['title']} | steps {metrics['steps_to_done']}, "
        f"first-pass {metrics['first_pass_yield']}, prompts {metrics['worker_prompt_bytes']}B, "
        f"{metrics['wall_seconds']}s"
    )
    for key, item in card["expectations"].items():
        if not item["pass"]:
            print(f"       expected {key} {item['expected']}, got {item['got']}")
    for key, item in card["invariants"].items():
        for violation in item["violations"]:
            print(f"       {key} {item['title']}: {violation}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python tests/run_sim.py")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run scenarios and write a scorecard")
    run.add_argument("ids", nargs="*", help="scenario ids (default: the chosen set)")
    run.add_argument("--set", choices=["fast", "full", "all"], default="fast")
    run.add_argument("--out", default="scorecard.json")
    run.add_argument("--keep", action="store_true", help="keep each scenario's repo for inspection")
    run.add_argument("--seed", type=int, default=0)
    sub.add_parser("list", help="list scenarios")
    args = parser.parse_args(argv)

    if args.command == "list":
        for scenario in SCENARIOS:
            print(f"{scenario.id:4} {scenario.set:5} {scenario.title}")
        return 0

    cards = {}
    for scenario in chosen(args):
        card = execute(scenario, keep=args.keep, seed=args.seed)
        cards[scenario.id] = card
        show(card)
    Path(args.out).write_text(
        json.dumps({"engine": __version__, "scenarios": cards}, indent=2) + "\n", encoding="utf-8"
    )
    failed = [key for key, card in cards.items() if not card["ok"]]
    print(f"{len(cards) - len(failed)}/{len(cards)} scenarios hold every invariant -> {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
