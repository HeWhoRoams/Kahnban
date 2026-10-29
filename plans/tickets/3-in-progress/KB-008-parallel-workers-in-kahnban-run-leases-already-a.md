---
id: KB-008
title: Parallel workers in kahnban run (leases already allow it)
status: in-progress
owner: claude-coder
branch: ticket/KB-008
worktree: .worktrees/KB-008
created: 2026-10-25
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
contract_hash: 02f0410cc4b0e1d3
contract_sig: 4c9e69822adfd608b5f87796cbc766339e5ff483aa06e7fc9f20bd5e437cc8d1
confirmed: ""
---

## Problem
`kahnban run` drives one ticket at a time, so a board with several ready tickets waits on each coder in turn. Leases and the
dispatcher's free-blast-radius rule already stop two coders from holding overlapping tickets. Decided with the user (2026-10-29):
parallel implement only. `kahnban run --jobs N` runs up to N coder workers at once, each in its own worktree. Only the worker
subprocess runs off the main thread; claim, verify, review, merge and done stay one at a time, so the merge queue, the board's
commits and signing are unchanged. The default is 1, which behaves exactly as before. Limit: tickets with disjoint declared radii
can still conflict at merge; the merge queue refuses those as it does today.

## Acceptance criteria
- [ ] with `--jobs 2`, two ready tickets with disjoint blast radii have their coders running at the same time and both reach 4-verifying (test: `python -m pytest tests/test_runner_parallel.py -q -k two_coders`)
- [ ] with `--jobs 1` (the default) the run stays sequential (test: `python -m pytest tests/test_runner_parallel.py -q -k one_job`)

## Blast radius
- `src/kahnban/runner.py`
- `src/kahnban/cli.py`
- `tests/test_runner_parallel.py`

## Implementation notes
- runner.py: `run(..., jobs=1)`; a `_Flight` holds the in-flight workers in a ThreadPoolExecutor. A coding action (`claim_and_implement`, `resume_worktree`, `revise_implementation`) claims or leases on the main thread, then submits only `_code` (the worker). Finished workers are harvested on the main thread: the lease is dropped, then `verify` runs. The loop waits for a worker when the board is idle or the pool is full, and drains the pool before it returns. A `RunStop` from a worker ends the run after the others finish.
- `_implement` is split into `_code` and `_verified`; the sequential path is unchanged.
- cli.py: `--jobs` on `run`.
- The test's coders each wait for the other's marker file, so they can only finish if they overlap.

## Validation
```
python -m pytest tests/test_runner_parallel.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-29 08:47 - ready gate passed -> 2-ready | contract 02f0410cc4b0e1d3
- 2026-10-29 08:47 - claimed by claude-coder -> 3-in-progress