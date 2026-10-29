# Remediation plan 3: code-review findings on KB-003 to KB-008

Source: the `/code-review` run on `30b23f6...HEAD` (2026-10-29), 10 findings. Each group below becomes one
ticket on the board (blast radius at most 3 files, the board's normal limit). Fixes are small and each ships
with the test that fails first. None of this is pushed or verified on Linux/CI yet.

## Order

R1 first (it is the newest and most concurrent code), then R2, R3, R4. They touch different files, so they
can be refined together and implemented one after another.

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

## R2: Reviewer registry robustness (findings 5, 6)

Files: `src/kahnban/trust.py`, `src/kahnban/cli.py`, `tests/test_reviewer_keys.py`.

Decision needed (finding 5): the registry lives in the user key directory, so a checkout on another
machine sees no reviewers and the check silently turns off.

- Recommended: `reviewers add` also writes the reviewer's name (never the key) to a committed
  `plans/reviewers.json`. `reviewer_problem` treats a non-empty file as "reviewers required" and refuses
  with "reviewer 'X' has no key on this machine; run 'kahnban reviewers add X' here" when the key is missing.
  The name list is not secret, and a worker editing it can only make the gate stricter or remove it, which
  is the same tripwire limit as the rest of the trust model (document it).
- Alternative: a board setting `require_registered_reviewers`. Simpler, but one more flag to forget.

Corrupt reviewer file: `registered_reviewers` skips and reports an unreadable file as a `GateError` naming the
path, instead of a traceback.

Tests: a repo with `plans/reviewers.json` and an empty key dir refuses merge with the new message; a corrupt
json file gives a one-line refusal; the existing five tests keep passing.

## R3: Simulation stability hardening (finding 7)

Files: `tests/sim/compare.py`, `tests/sim/__main__.py`, `tests/test_sim_compare.py`.

- `stability_report` takes the union of scenario ids and metric names across all cards; a scenario or
  metric missing from some run counts as unstable.
- `stability --accept` with no baseline file writes a baseline containing only `unstable`, or says "run
  `compare --accept` first" (pick the second: one clear message).
- Tests: a card missing a scenario is reported, not a `KeyError`; `--accept` without a baseline gives the message.

## R4: Core clean-ups (findings 8, 10)

Files: `src/kahnban/core.py`, `tests/test_reviewer_keys.py` (name use only).

- One module-level `_APPROVAL_FIELDS` mapping of the fields to blank, used by `verify` and `reject`.
- Rename `_signature_problem` to `_approval_problem` and update its docstring to say it checks both the
  engine HMAC and the reviewer seal.
- No behaviour change, so no new test; the full suite is the check.

## Left alone on purpose

- Spec reviewer's reviewer-name case claim (KB-007): signing and the owner check both lower-case, so no fix.
- KB-006 non-strict mode lets a worker strip `contract_sig`: that is the ticket's stated behaviour (strict
  boards refuse it). Add one README sentence recommending `require_signed_approvals` for unattended runs.
- Trust.py duplicated HMAC shape, Data Clumps and the `by_owner` dict shape: judgement-call smells, not
  worth a ticket until a fourth signature kind appears.

## Verification for every group

`kahnban verify` (Tier 1 feature tests, red check, Tier 2 `python tests/run_parallel.py -j 8`), then your
approval, then merge with the full regression. Count of tests should rise by the new tests only.
