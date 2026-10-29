---
id: KB-011
title: "Runner robustness for --jobs: log worker stops, drop leaked leases, no verify past max_steps"
status: ready
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: [docs/remediation-plan-3.md]
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 620f208e460cac0b
contract_sig: eea9ba7ecd5de8fe51b1f3f4898df497cbc0dd9a69d36bf6b714b99711242326
confirmed: ""
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
- [ ] A worker's `RunStop` still logs a `Step` for its ticket before the run stops (a coder that exits 1 under `--jobs 2`) (test: `python -m pytest tests/test_runner_parallel.py -q -k run_stop_logs_a_step`)
- [ ] If `pool.submit` raises after a ticket is claimed/leased, the lease is dropped before `start` returns (test: `python -m pytest tests/test_runner_parallel.py -q -k submit_failure_drops_the_lease`)
- [ ] Harvesting two finished workers where `core.verify` raises for the first still drops both leases and records the first as a `refused:` outcome (only `RunStop` is re-raised) (test: `python -m pytest tests/test_runner_parallel.py -q -k harvest_survives_one_worker_error`)
- [ ] With `max_steps=3, jobs=2`, a worker that finishes after the budget is not verified: its lease is dropped, its ticket stays in-progress, and `result.stopped` names it (test: `python -m pytest tests/test_runner_parallel.py -q -k max_steps_leaves_workers_unverified`)
- [ ] `_implement` and `harvest` share one `_finish(config, ticket, code)` (drop lease, then `_verified`) built on one `_REFUSALS` tuple, with no behaviour change (test: `python -m pytest tests/test_runner_parallel.py -q`)
- [ ] `kahnban run --jobs 0` (and any value below 1) fails with a usage error instead of silently clamping to 1 job (test: `python -m pytest tests/test_runner_parallel.py -q -k jobs_rejects_non_positive`)

## Blast radius
- `src/kahnban/runner.py`
- `src/kahnban/cli.py`
- `tests/test_runner_parallel.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_runner_parallel.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:31 - ready gate passed -> 2-ready | contract 620f208e460cac0b