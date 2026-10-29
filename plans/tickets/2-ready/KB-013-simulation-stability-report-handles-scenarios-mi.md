---
id: KB-013
title: "Simulation stability_report handles scenarios missing from a run, and --accept without a baseline says what to do"
status: ready
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: d2e146a4bf5fea9f
contract_sig: 8828727a23b708c82b2dd47a4d2dbc799bf294f0639a93d9bf071fe9785cb2d6
confirmed: ""
---

## Problem
## R3: Simulation stability hardening (finding 7)

Files: `tests/sim/compare.py`, `tests/sim/__main__.py`, `tests/test_sim_compare.py`.

- `stability_report` takes the union of scenario ids and metric names across all cards; a scenario or
  metric missing from some run counts as unstable.
- `stability --accept` with no baseline file writes a baseline containing only `unstable`, or says "run
  `compare --accept` first" (pick the second: one clear message).
- Tests: a card missing a scenario is reported, not a `KeyError`; `--accept` without a baseline gives the message.


Full context: docs/remediation-plan-3.md (code-review findings, 2026-10-29). Keep the blast radius to the files named above and write the tests first.

## Acceptance criteria
- [ ] `stability_report` takes the union of scenario ids and metric names across all cards, instead of only `cards[0]`'s (test: `python -m pytest tests/test_sim_compare.py -q -k stability_report_covers_the_union`)
- [ ] a scenario or metric present in some runs but missing from another is reported as moved/unstable, not a `KeyError` (test: `python -m pytest tests/test_sim_compare.py -q -k stability_report_handles_a_missing_scenario`)
- [ ] `stability --accept` with no baseline file prints "run `compare --accept` first" and exits non-zero instead of raising `FileNotFoundError` (test: `python -m pytest tests/test_sim_compare.py -q -k stability_accept_without_baseline`)

## Blast radius
- `tests/sim/compare.py`
- `tests/sim/__main__.py`
- `tests/test_sim_compare.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_sim_compare.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:37 - ready gate passed -> 2-ready | contract d2e146a4bf5fea9f