# Plan: close every known gap, one verified fix at a time

Companion to [self-test-plan.md](self-test-plan.md) and [simulation-plan.md](simulation-plan.md). Those plans found the gaps; this one fixes them, using the simulation as the safety net: every fix is a hypothesis, a before/after scorecard and a baseline update.

## Status (2026-10-25)

| ID | Result |
|---|---|
| G1 stale lock | **Fixed.** Lock files record pid and host; a waiter breaks the lock of a dead local process at once, one waiter wins the break (exclusive-create guard), and a release retries while a waiter has the file open. |
| G2 leftovers after a crash at done | **Fixed.** `finish_cleanup` action, lint rule BL20. |
| G3 confirm loop | **Fixed** with option 1: `integration_refusals` counted for the life of the ticket, escalation after `max_attempts`, `confirm --reason` for one more try. |
| G4 unknown crash points | The sweep now has 12 points (before and after each engine commit, and at each worker start). One new finding: after a crash with a worker still running, the board waits out the worker's lease (30 minutes by default) and called itself idle. `kahnban next` now says it is waiting on a live lease. The wait itself is by design. All 12 points recover. |
| G5 Linux and GitHub | **Not done.** WSL on this machine is broken (its disk image path is missing) and Docker would need an image or packages downloaded, which I did not do without asking. `sim.yml` and the new CI jobs parse as valid YAML and have never run. |
| G6 determinism | **Partly done.** The 14 fast scenarios were baselined in one run and compared in a separate, later run: every gated metric matched (wall time aside). That is two runs, not the five on an unchanged tree the plan asked for; my own edits contaminated the repeat runs I started, so they were discarded. |
| G7 S9, S10 | **Built and passing** (two runners at once; a hung worker killed by the timeout). |
| G8 coverage | **Done.** 91% to 93%; every module is at least 85%, and `skills.py` went from 69% to 99%, `worktree.py` 79% to 95%, `frontmatter.py` 88% to 99%, `learnings.py` 88% to 97%, `runner.py` 86% to 94%, `trust.py` 85% to 93%. CI floor is 90%. |
| G9 child-process coverage | **Done.** `tests/run_coverage.py` puts a `sitecustomize` on PYTHONPATH; `cli.py` 85% to 90% and `mcp_server.py` 85% to 93% once the processes the tests start were counted. |
| G10 wheel | **Done.** `tests/test_installed.py` builds a wheel from a copy of the source, installs it into a fresh virtual environment and checks every template file and a scaffold-and-lint run. Removing the `templates/skills` glob from `package-data` makes it fail. CI job added. |
| G11 gate matrix | **Done.** `tests/test_gate_matrix.py`: 19 rows, one dishonest input per gate. Breaking three of the gates in a copy of the source (escalate's reason, approve's owner check, the `--force` reason) turns the matching row red; the `--force` break was first missed, which is why the two `claim --force` rows exist. |
| G12 speed | **Done another way.** Building the repo per test is only 0.2 s of about 1 s per test, so a template repository would save little. `tests/run_parallel.py` deals the 700 tests to worker processes: 153 s with 12 workers, against 9 minutes in one process. No new dependency. |
| G13 live agents | **Written, not run.** `tests/live/test_live_factory.py` preflights the CLI and one call, runs the toy ticket, and prints medians over `KAHNBAN_LIVE_RUNS`. It skips without `KAHNBAN_LIVE=1`; running it spends model usage and needs the login. |
| G14 dogfood | **Not done.** `kahnban init --agentic` adds `plans/`, `.agents/` and agent and hook files to this repository, which is your call. |
| G15 `python -c` | Unchanged, as planned. |

Things found on the way, all fixed or noted: concurrent `rename` calls on one file all reported success on this machine, so the lock break uses an exclusive-create guard instead; reading a lock file made the holder's delete fail on Windows, which the first version of the new break had turned into a permanent lock; the baseline file had never been committed because `.gitignore` matched it; and a `SKILL.md` without frontmatter lists with no description.

## How every fix runs (the loop)

1. **Reproduce.** Run the scenario that shows the gap with `--keep` and read what the engine did. No fix is written from a guess; two of the three findings below are still guesses about the mechanism.
2. **Test first.** A unit test (or a new simulation scenario) that fails for the stated reason.
3. **Fix** at the shared place, not at the one caller that showed it.
4. **Compare.** `python tests/run_sim.py compare` against the committed baseline, then `compare --set all` before merging. The change must list the expected lines under BETTER and nothing under BROKEN or WORSE.
5. **Move the baseline** with `--accept` in its own commit, and add the before and after numbers to `CHANGELOG.md`.
6. **Remove the `known_gap`** from the scenario in the same commit as the fix that closes it.

## Inventory

| ID | Gap | Evidence | Severity |
|---|---|---|---|
| G1 | A crashed run leaves a board lock that blocks the next run for 5 minutes | S8 `before:1-3`, `after:1-3`: 6 of 6 recoveries fail with `LockError` | High: any killed cron job or closed terminal stops the board |
| G2 | A crash at the merge step leaves the worktree and branch of a done ticket behind, and nothing ever cleans them | S8 `before:4`, `after:4`: I10 | Medium: disk and branch clutter, and `git worktree` errors later |
| G3 | In an attended run a ticket the integrator keeps refusing never escalates while a human keeps confirming | S5 with 8 confirmation rounds | Low: by design today (`confirm` resets the counts) |
| G4 | Unknown: other crash points hide behind G1 (a crash after a worktree is created but before the claim commit, during verify, during approve) | S8 never got past the lock at points 1-3 | Unknown until G1 is fixed |
| G5 | The simulation has never run on Linux or on GitHub | Built and run on Windows only; `sim.yml` untested | High: the safety net is unproven where CI runs |
| G6 | Scorecard determinism is unverified, and tolerances are guesses | Two identical runs observed, never measured | Medium: a flaky metric blocks every pull request |
| G7 | Scenarios not built: two runners at once (S9), a hung worker (S10) | Plan, not code | Medium: G1's fix changes locking, which only S9 exercises |
| G8 | Line coverage gaps: `skills.py` 69%, `worktree.py` 79%, `fsutil.py` 80%, `hooks.py` 81%, `cli.py` 85%, `mcp_server.py` 85%, `trust.py` 85%, `runner.py` 86% | Baseline coverage run | Medium |
| G9 | Code that runs in child processes is not measured (`__main__.py` 0%, the MCP stdio loop, workers) | Coverage run | Medium: the real entry points are unmeasured |
| G10 | No test installs the built wheel | self-test-plan step 4 | Medium: a template missing from `package-data` ships unnoticed |
| G11 | No table of gate attacks (no-op test command, edits after the contract froze, stale approval tip, reused merge confirmation) in one place | self-test-plan step 5 | Medium: partly covered by S4, partly by scattered unit tests |
| G12 | The unit suite takes 9 minutes, README says 5 | Measured: about 1 second per test, from per-test git repo setup | Low, but it taxes every change |
| G13 | No real-agent test; the live runs were manual | self-test-plan step 7, simulation step 9 | Medium: only this shows whether real models get through the gates |
| G14 | This repository does not run on its own board | self-test-plan step 8 | Low |
| G15 | `python -c` can write files past the guard (the tamper cheat ran; the gate caught it) | S4c: the guard did not refuse it | Known ceiling, documented in the README; no fix planned |

Out of scope here because each needs a design, not a fix (from NEXT_STEPS.md): tamper resistance beyond the guard (containers or records outside the agents' write access), reviewer identity that is not self-asserted, parallel workers in `kahnban run`, the `citadel` portability test, per-role metrics, renaming the `blast-radius` skill.

## Order of work

### Phase 0: trust the safety net (G5, G6)
- Push the branch and get `sim.yml` green on Ubuntu and Windows. Fix what Linux shows (shell quoting in `tests/sim/agent.py`, `env -u`, path separators in the invariant checker). Done when both jobs are green on a pull request.
- Run the fast set 5 times on one machine and compare each scorecard against the first. Done when every gated metric is identical across runs; any that is not gets a tolerance, an explanation, or is removed from the gate. Record the finding in `simulation-plan.md`.

### Phase 1: understand G1 and G2 before touching them
- `KAHNBAN_SIM_FAULT=after:4 python tests/run_sim.py run S8 --keep`, then read the recovery run's log and the ticket's Log section: where does the second run go (merge again? done? straight to cleanup?) and why is cleanup skipped.
- Read how `board_lock` (`core.py`, 300 s, age only) and `fsutil.exclusive` (`attempts.py` and `exit_checks.py`, 30 s, age only) decide a lock is stale. Both need the same fix, so it goes in `fsutil`.
- Done when `gap-fix-plan.md` states the mechanism of G1 and G2 in a line each, from evidence.

### Phase 2: G1, the stale lock
**Fix.** A lock file records `pid`, `host` and creation time. A waiter that sees a lock from the same host whose process no longer exists breaks it at once; a lock from another host, or one it cannot judge, falls back to the age rule. One `fsutil.process_alive(pid)`: `os.kill(pid, 0)` on POSIX (a `PermissionError` means alive), `OpenProcess` plus `GetExitCodeProcess` through `ctypes` on Windows. Breaking a lock must be atomic: rename the stale file to a unique name and only the waiter whose rename succeeds proceeds, so two waiters cannot both unlink and then each delete the other's new lock. `board_lock` and `exclusive` share this code.
**Tests first.** Unit tests: a lock whose pid is dead is broken immediately; a live pid's lock is not broken before the age limit; two threads racing to break one stale lock leave exactly one winner; `process_alive` on a finished child process. Scenario S9: two `kahnban run` processes on one board with one ticket, nothing may run twice and the board must end clean.
**Verified by.** S8 `before:1-3`, `after:1-3` move from failing to passing and S9 passes, with nothing else WORSE. Add a canary: the lock ignores the owner's liveness check, and S9 or S8 must turn red.

### Phase 3: G2, then G4 until the sweep is green
**G2 fix.** Two changes. The dispatcher offers a `finish_cleanup` action for a done ticket whose worktree, branch or lease still exists, and the runner handles it with the same cleanup call the merge step uses (idempotent, and clears the attempt counts). And `kahnban lint` gets a new rule that warns about a done ticket with a leftover worktree or branch, so a crash that happens outside `kahnban run` is visible too. Final choice between the two follows Phase 1's finding.
**G4.** With G1 fixed, rerun S8. Each crash point that still fails becomes its own entry (`G4a`, `G4b`, ...) with its mechanism and fix, handled with the same loop. Done when S8 reports `recovery_rate` 1.0 at every point and `known_gap` is removed from it.
**Also:** add S10 (a hung worker: the timeout kills it, the ticket is retried or escalated, no process is left running) and a "crash during a worker's turn" row to S8 (kill the runner while the coder is running, not only at engine commits).

### Phase 4: G3, a decision first
Three options, in my order of preference:
1. **Count refusals for the life of the ticket.** Store the integrator's refusals in the ticket (`integration_refusals`), and after `max_attempts` of them stop pausing for a confirmation: escalate with "the integration test refused this N times; confirming again will not help". `confirm` stays able to force one more try with `--reason`.
2. **Only say it.** The pause message shows how many times this ticket has been sent back, so the human decides with the number in front of them.
3. **Leave it.** By design today; document it in `how-it-works.md`.
Done when the chosen behavior has an S5 variant that proves it and the choice is written in the changelog.

### Phase 5: measure and test the rest (G8, G9, G10, G11, G12)
In this order, each its own commit:
1. **Subprocess coverage (G9).** `COVERAGE_PROCESS_START` plus a `.pth` file in the test environment, so child processes report. Re-measure; the numbers in G8 will change.
2. **Fill G8.** Per module, the missed ranges are in `self-test-plan.md`: `skills.py` first (install and configure paths), then `worktree.py`, `fsutil.py`, `hooks.py`, then the 85-86% modules. Set `--fail-under` to the new measured floor minus 2, and run it in CI.
3. **Installed wheel (G10).** `tests/test_installed.py` from self-test-plan step 4, as a CI job on both OSes.
4. **Gate matrix (G11).** One table-driven file from self-test-plan step 5; rows already covered by S4 or a unit test link to it instead of repeating it. Done when patching any gate to do nothing turns at least one row red (the canaries already prove this for six gates; the matrix covers the rest).
5. **Speed (G12).** One session-scoped template repo copied per test, then `GIT_CONFIG_NOSYSTEM`, then `pytest-xdist` only if still over 5 minutes. Update the README number to the measured one.

### Phase 6: real agents and dogfood (G13, G14)
- Live tier: `tests/live/test_live_factory.py`, opt-in with `KAHNBAN_LIVE=1`, preflight `claude auth status` and one trivial call, repeat 5 times and compare medians.
- Dogfood: `kahnban init` in this repository, ingest this plan and NEXT_STEPS.md as tickets, and land the remaining items through `ready` to `merge`. Friction goes to `kahnban learnings capture`.

## Definition of done for the whole plan

- `python tests/run_sim.py compare --set all` exits 0 with no `known_gap` left in any scenario, on Ubuntu and Windows in CI.
- S8 `recovery_rate` is 1.0, S9 and S10 pass, and each fix in Phases 2 to 4 has a canary or a unit test that fails without it.
- Line coverage is at or above 90% with child processes counted, and the floor is enforced in CI.
- The built wheel installs and runs a ticket from idea to done in a clean environment.
- The unit suite runs in under 5 minutes, or the README states the real number.
- G15 stays listed as a known ceiling, with its README sentence unchanged.

## Risks

- **Process liveness is not identity.** A recycled pid makes a dead holder look alive, so the age rule must stay as the fallback, and the creation time recorded in the lock narrows the window. A wrongly broken lock is worse than a slow one, so the rule errs toward waiting.
- **Fixing locks can create a worse bug than the one fixed.** S9 and the unit race test exist for that reason and come before the fix is merged, not after.
- **A baseline moved by a fix hides the next regression.** `--accept` only runs on a clean comparison, and fixes that move many metrics get their own commit.
- **G4 is open-ended.** The sweep may show more weaknesses than the two found so far; each gets an entry, and the plan is done when the sweep is green, not when this list is.
