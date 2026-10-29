---
id: KB-013
title: "Simulation stability_report handles scenarios missing from a run, and --accept without a baseline says what to do"
status: backlog
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

## Blast radius

## Implementation notes

## Validation
```
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog