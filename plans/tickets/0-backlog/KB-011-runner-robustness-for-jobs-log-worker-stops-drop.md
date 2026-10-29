---
id: KB-011
title: "Runner robustness for --jobs: log worker stops, drop leaked leases, no verify past max_steps"
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
## R1: Runner robustness for `--jobs` (findings 1, 2, 3, 4, 9)

Files: `src/kahnban/runner.py`, `tests/test_runner_parallel.py`.

| Finding | Fix | Test (fails before) |
|---|---|---|
| Worker `RunStop` leaves no Step | In `harvest`, call `_note` with the worker's message before storing `self.stop`. | A coder that exits 1 under `--jobs 2`: the `RunStop` still raises, and the run log has a line for that ticket. |
| Lease leaks if start fails after claim | In `start`, wrap claim/submit so any failure after the claim calls `core.drop_lease`. | Make `pool.submit` raise: the ticket has no live lease afterwards. |
| Other exceptions abort harvest | Catch `Exception` per future in `harvest`, record it as a `refused:` outcome (re-raise only `RunStop`), so every finished future is processed and its lease dropped. | Two finished workers where verify raises `OSError` for the first: both leases are dropped. |
| `drain` verifies past `max_steps` | On the max_steps exit, wait for workers but do not verify them; leave the tickets in-progress with the lease dropped, and say so in `result.stopped` ("N worker(s) finished unverified; run again"). | `max_steps=3, jobs=2`: no verify runs after the budget and the message names the tickets. |
| Duplicated exception tuple and lease-drop | Name `_REFUSALS = (core.KahnbanError, gitops.GitError, worktree.WorktreeError)`; give `_implement` and `harvest` one shared `_finish(config, ticket, code)` that drops the lease and calls `_verified`. | Existing tests still pass (no behaviour change). |

Also in this ticket: reject `--jobs 0` and below with a usage error instead of clamping (cli.py is already
touched by KB-008; this is a one-line `type=` check, so a third file only if the check goes there).


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