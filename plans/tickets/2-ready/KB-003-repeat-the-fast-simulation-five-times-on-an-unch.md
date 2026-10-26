---
id: KB-003
title: Repeat the fast simulation five times on an unchanged tree and gate only the metrics that never move
status: ready
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-25
updated: 2026-10-26
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 73553383573b7909
confirmed: ""
---

## Problem
The simulation baseline was made in one run and compared in one later run (docs/gap-fix-plan.md, G6). Two matching runs do not show that a
metric never moves, and the tolerances in `tests/sim/compare.py` are guesses. A metric that moves on an unchanged tree would block
every pull request. `python tests/run_sim.py stability` should run the chosen scenarios N times (default 5) on the same tree, report
which metrics moved, and let `compare` skip those, so only metrics that never move are gated.

## Acceptance criteria
- [ ] `stability_report(cards)` takes the scorecards of several runs and returns the `scenario metric` names whose value differs between runs (wall_seconds ignored) (test: `python -m pytest tests/test_sim_compare.py -q -k stability_report`)
- [ ] a baseline with an `unstable` list makes `compare` ignore those metrics, still gating every other metric and every invariant (test: `python -m pytest tests/test_sim_compare.py -q -k unstable_metrics`)
- [ ] `run_sim.py stability --runs N` runs the chosen scenarios N times, prints the unstable metrics, and with `--accept` writes them as `unstable` into the baseline (test: `python -m pytest tests/test_sim_compare.py -q -k stability_command`)

## Blast radius
- `tests/sim/compare.py`
- `tests/sim/__main__.py`
- `tests/test_sim_compare.py`

## Implementation notes
- `stability_report` goes in compare.py; `normalize` must carry the baseline's `unstable` list through, and `compare` skips `f"{ident} {name}"` found in it.
- The command reuses `run_scenarios` in a loop; the test calls `main` with a tiny scenario and `--runs 2`.
- After merge, outside the ticket: run `stability --runs 5 --accept` once and commit the baseline.

## Validation
```
python -m pytest tests/test_sim_compare.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 19:19 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 19:19 - ready gate passed -> 2-ready | contract 73553383573b7909