---
id: KB-004
title: "Break down status.json metrics per role: which worker caused the rejections"
status: in-progress
owner: claude-coder
branch: ticket/KB-004
worktree: .worktrees/KB-004
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
contract_hash: 74031f925bb25faf
confirmed: ""
---

## Problem
`status.json` metrics count verify attempts and rejections per ticket and give a board-level first-pass yield, but not who caused them.
With several workers, or after changing one worker's prompt, nobody can tell which owner's work fails verify or gets rejected, or which
reviewer rejects. The ticket Log already has what is needed: `claimed by <owner>` (and `taken over by <owner>`), `verify exit=N`,
and `rejected by <reviewer>:`.

## Acceptance criteria
- [ ] `log_metrics` adds `by_owner` ({owner: {failed_verifies, rejections}}, a failed verify or rejection counting against the owner of the most recent claim or take-over) and `rejected_by` ({reviewer: count}), and still returns the existing four keys (test: `python -m pytest tests/test_factory_run.py -q -k log_metrics`)
- [ ] a failed verify or rejection before any claim is counted under `unknown` and never raises (test: `python -m pytest tests/test_factory_run.py -q -k log_metrics_unknown_owner`)
- [ ] `status.json` metrics gain board-level `by_owner` and `by_reviewer`, the sums over every ticket's counts (test: `python -m pytest tests/test_factory_run.py -q -k board_metrics_by_role`)

## Blast radius
- `src/kahnban/core.py`
- `src/kahnban/status.py`
- `tests/test_factory_run.py`

## Implementation notes
- In `core.log_metrics`, walk the entries in order keeping `owner` from `claimed by X ->` and `taken over by X from`; `rejected by R:` takes R up to the first colon.
- Update the exact-equality assertion in `test_log_metrics_count_attempts_rejections_and_cycle_time` for the new keys.
- `status._metrics` sums per-ticket `by_owner` and `rejected_by` into `by_owner` and `by_reviewer`.

## Validation
```
python -m pytest tests/test_factory_run.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 20:04 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 20:04 - ready gate passed -> 2-ready | contract 74031f925bb25faf
- 2026-10-26 20:04 - claimed by claude-coder -> 3-in-progress