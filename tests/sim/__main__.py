"""``python tests/run_sim.py run|compare|list``. See docs/simulation-plan.md."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from kahnban import __version__

from .compare import compare, normalize, report, stability_report
from .scenarios import SCENARIOS, execute

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline" / "scorecard.json"
LAUNCHER = HERE.parent / "run_sim.py"


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
    mark = "PASS" if card["ok"] else ("KNOWN GAP" if card.get("known_gap") else "FAIL")
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


def run_scenarios(args: argparse.Namespace) -> dict:
    cards = {}
    for scenario in chosen(args):
        card = execute(scenario, keep=getattr(args, "keep", False), seed=args.seed)
        cards[scenario.id] = card
        show(card)
    return {"engine": __version__, "scenarios": cards}


def run_against(ref: str, args: argparse.Namespace) -> dict:
    """The same scenarios, run with another git ref's engine (this checkout's simulation code)."""
    repo = HERE.parents[1]
    scratch = Path(tempfile.mkdtemp(prefix="sim-ref-"))
    tree = scratch / "ref"
    out = scratch / "scorecard.json"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(tree), ref], check=True, capture_output=True)
    try:
        env = {**os.environ, "KAHNBAN_SIM_SRC": str(tree / "src")}
        command = [sys.executable, str(LAUNCHER), "run", *args.ids, "--set", args.set, "--seed", str(args.seed), "--out", str(out)]
        print(f"-- running the scenarios against {ref} ({tree / 'src'})")
        subprocess.run(command, env=env, check=False)
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(tree)], capture_output=True)
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python tests/run_sim.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("run", "run scenarios and write a scorecard"), ("compare", "run scenarios and compare with a baseline or a git ref")):
        item = sub.add_parser(name, help=text)
        item.add_argument("ids", nargs="*", help="scenario ids (default: the chosen set)")
        item.add_argument("--set", choices=["fast", "full", "all"], default="fast")
        item.add_argument("--seed", type=int, default=0)
        item.add_argument("--out", default="scorecard.json")
        if name == "run":
            item.add_argument("--keep", action="store_true", help="keep each scenario's repo for inspection")
        else:
            item.add_argument("--against", metavar="REF", help="compare with this git ref instead of the committed baseline")
            item.add_argument("--new", metavar="FILE", help="use this scorecard instead of running the scenarios")
            item.add_argument("--accept", action="store_true", help="write the result as the new baseline (only if clean)")
    sub.add_parser("list", help="list scenarios")
    stable = sub.add_parser("stability", help="run the scenarios several times on this tree and list the metrics that moved")
    stable.add_argument("ids", nargs="*", help="scenario ids (default: the chosen set)")
    stable.add_argument("--set", choices=["fast", "full", "all"], default="fast")
    stable.add_argument("--seed", type=int, default=0)
    stable.add_argument("--runs", type=int, default=5)
    stable.add_argument("--accept", action="store_true", help="record the moving metrics as 'unstable' in the baseline, so compare skips them")
    canary = sub.add_parser("canaries", help="break the engine on purpose; every break must turn the simulation red")
    canary.add_argument("names", nargs="*", help="only canaries whose name contains this text")
    args = parser.parse_args(argv)

    if args.command == "canaries":
        from .canaries import main as canaries_main

        return canaries_main(args.names)

    if args.command == "list":
        for scenario in SCENARIOS:
            print(f"{scenario.id:4} {scenario.set:5} {scenario.title}")
        return 0

    if args.command == "stability":
        if args.accept and not BASELINE.exists():
            sys.exit(f"no baseline at {BASELINE}; run `compare --accept` first")
        runs = [run_scenarios(args) for _ in range(args.runs)]
        moved = stability_report(runs)
        print(f"{len(moved)} metric(s) moved over {args.runs} runs: {', '.join(moved) or 'none'}")
        if args.accept:
            kept = json.loads(BASELINE.read_text(encoding="utf-8"))
            BASELINE.write_text(json.dumps({**kept, "unstable": moved}, indent=2) + "\n", encoding="utf-8")
            print(f"recorded in {BASELINE}")
        return 0

    if args.command == "run":
        card = run_scenarios(args)
        Path(args.out).write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        failed = [key for key, item in card["scenarios"].items() if not item["ok"] and not item.get("known_gap")]
        total = len(card["scenarios"])
        print(f"{total - len(failed)}/{total} scenarios hold every invariant -> {args.out}")
        return 1 if failed else 0

    new = json.loads(Path(args.new).read_text(encoding="utf-8")) if args.new else run_scenarios(args)
    Path(args.out).write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    if args.against:
        old = run_against(args.against, args)
    elif BASELINE.exists():
        old = json.loads(BASELINE.read_text(encoding="utf-8"))
    elif args.accept:
        old = {"scenarios": {}}
    else:
        sys.exit(f"no baseline at {BASELINE}; run 'compare --accept' once to create it")
    ran = {s.id.upper() for s in chosen(args)}  # the baseline also holds scenarios of the other set
    old = {**old, "scenarios": {k: v for k, v in old["scenarios"].items() if k.upper() in ran}}
    result = compare(normalize(old), normalize(new))
    print(report(result))
    if args.accept:
        if not result.clean or any(not item["ok"] and not item.get("known_gap") for item in new["scenarios"].values()):
            print("not accepted: something is broken or worse")
            return 1
        BASELINE.parent.mkdir(exist_ok=True)
        merged = normalize(new)
        if BASELINE.exists():
            kept = json.loads(BASELINE.read_text(encoding="utf-8"))
            merged = {**merged, "unstable": kept.get("unstable", [])}  # accepting a run must not forget what stability found
            if args.ids:
                merged = {**merged, "scenarios": {**kept["scenarios"], **merged["scenarios"]}}
        BASELINE.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written to {BASELINE}")
        return 0
    return 0 if result.clean else 1


if __name__ == "__main__":
    sys.exit(main())
