# Simulation plan: confirm the workflow, then improve it with a safety net

Companion to [self-test-plan.md](self-test-plan.md). The unit suite checks that each gate behaves. This plan checks that the whole workflow behaves, with agents that do honest work, sloppy work and dishonest work, and it turns the result into numbers you can compare before and after any change.

## Goals

1. **Confirm everything that exists.** One command runs scripted agents through every stage and failure path on throwaway repos, and reports pass or fail for each rule the workflow promises.
2. **Make improvements measurable.** The same command produces a scorecard. After a change you compare scorecards and get three lists: rules broken, metrics that got worse, metrics that got better.
3. **Make the loop routine.** An improvement has a written hypothesis, a scenario that exposes the problem, a change, a comparison, and a baseline update only when the result is better or equal.

## What the simulation is

A simulated run is: a fresh repo, a board with N tickets, a set of scripted worker "agents" with known behaviours, and the real `kahnban run` driving them. Nothing in the engine is mocked. Only the agents are fake, so the same scenario gives the same result every time.

```
scenario (repo + tickets + agent mix + seed + optional fault)
   -> kahnban run (real engine, real git, real gates)
   -> check invariants after every step and at the end
   -> scorecard.json (rules, metrics)
   -> compare with baseline (or with another git ref)
```

It lives in `tests/sim/` and is not part of the default `pytest` run, because it is slower than a unit test.

## Rules the simulation must confirm (invariants)

Each is pass or fail. They are checked after every engine step, not just at the end.

| # | Invariant | Source of truth |
|---|---|---|
| I1 | `kahnban lint` is clean after every step | linter BL01-BL16 |
| I2 | Each ticket file exists in exactly one column, and `status` matches the column | BL03, BL04 |
| I3 | Every column move is one commit on the default branch | README, "How It Works" |
| I4 | A ticket in `5-done` has its branch merged into the default branch | `done` gate |
| I5 | The merged tip equals the tip that was verified and approved | `approve` and `merge` gates |
| I6 | The default branch passes the validation command at every commit the run made | merge queue |
| I7 | No worker reached `done` by a forbidden route (see the cheat list below) | guard and trust |
| I8 | The reviewer never equals the owner | `approve` gate |
| I9 | No two in-progress tickets have overlapping blast radii | `claim` gate |
| I10 | After `cleanup`, no worktree, branch, junction or lock remains for the ticket | `cleanup` |
| I11 | A second `kahnban run` on an idle board makes no commits | idempotence |
| I12 | After a crash at any point, the next run recovers without a human editing files | lease and recovery |
| I13 | The honest agent is never blocked by the guard (false-block rate is zero) | guard |
| I14 | Every cheat attempt is refused (cheat catch rate is 100%) | guard, gates, trust |

I6 is the strongest: it replays the validation command over each commit the run added to the default branch. Do it on a copy of the repo, once per scenario, after the run.

## Scripted agents

Each agent is a small Python script like the `WORKER` in `tests/test_factory_run.py`, driven by a policy name and a seed in its environment. One file, `tests/sim/agents.py`, holds every policy.

| Policy | Role | Behaviour |
|---|---|---|
| `honest` | coder | Writes the fix and its test, commits, stops |
| `sloppy` | coder | First attempt fails verify; fixes it after the rejection text |
| `slow` | coder | Does the work but needs `k` attempts (parameter) |
| `idle` | any | Reads stdin, does nothing (tests escalation) |
| `crashy` | any | Exits non-zero or hangs past the timeout at step `k` |
| `cheat-radius` | coder | Edits a file outside the declared blast radius |
| `cheat-noop-test` | coder | Makes the test command pass without testing (`true`) |
| `cheat-tamper` | coder | Edits the frozen acceptance criteria or the test after the contract froze |
| `cheat-self-approve` | reviewer | Approves its own work, or forges an approval record |
| `cheat-role` | any | Clears or changes `KAHNBAN_ROLE` before calling `kahnban` |
| `cheat-force` | coder | Uses `--force` or `move` without a reason |
| `reviewer-honest` | qa | Approves good work, rejects bad work with reasons |
| `reviewer-rubber` | qa | Approves everything (measures what the later gates still catch) |
| `reviewer-strict` | qa | Rejects the first submission every time (measures cost of rejection loops) |
| `human` | human | Answers escalations and runs `confirm` and `unblock` on a script |

A probabilistic mix (for example, 80% honest, 15% sloppy, 5% cheat) draws from `random.Random(seed)`. The seed is part of the scenario name and the scorecard, so a surprising result can be replayed exactly.

## Scenarios

Each scenario is a short Python function that builds the repo, chooses the agents, runs, and returns a result. The fast set runs on every pull request; the full set runs nightly.

| ID | Scenario | Set |
|---|---|---|
| S1 | One ticket, honest agents, idea to done (`kahnban run` from a bare backlog item) | fast |
| S2 | Five tickets with dependencies and two overlapping blast radii; check order and I9 | fast |
| S3 | Rejection loop: strict reviewer, sloppy coder, escalation after `max_attempts` | fast |
| S4 | Each cheat policy alone against an otherwise honest board (one run per cheat) | fast |
| S5 | Merge-queue break: two tickets that pass alone and fail together | fast |
| S6 | Attended mode: the run stops at the confirm gate until the `human` agent signs | fast |
| S7 | Escalation and `unblock`: a ticket parks, the human answers, the run resumes | fast |
| S8 | Fault injection: kill the run after commit `k` for every `k` in one ticket's life (about 15 points), then run again and check I12 | full |
| S9 | Two runners on one board at the same time (leases, claim race) | full |
| S10 | Worker timeout and a hung worker, repeated | full |
| S11 | Upgrade: a board written by an older engine version (committed fixture per past release) opens, lints and runs | full |
| S12 | Windows and Linux paths: CRLF tickets, spaces in the project path, long paths | full (both CI OSes) |
| S13 | A larger board (50 tickets, 5 columns busy) for wall time and step counts | full |
| S14 | Mixed probabilistic agents over 10 seeds; report the distribution, not one number | full |

Fault injection (S8) needs one small hook: an environment variable, `KAHNBAN_FAULT_AFTER_COMMITS=k`, that makes `gitops` exit the process right after the k-th commit of the run. It exists only for the simulation, is off unless the variable is set, and is covered by its own test.

## The scorecard

`python -m tests.sim run` writes `scorecard.json`: one record per scenario with the invariants (pass or fail, with the first violation's step and message) and these metrics.

| Metric | Better is | How measured |
|---|---|---|
| `first_pass_yield` | higher | from `status.json` (exists today) |
| `rejections_per_ticket` | lower | ticket metrics (exists today) |
| `verify_attempts_per_ticket` | lower | ticket metrics (exists today) |
| `steps_to_done` | lower | `RunResult.steps` (exists today) |
| `escalation_rate` | lower | parked tickets over total |
| `engine_commits_per_ticket` | lower | board-branch commits by the engine |
| `worker_prompt_bytes` | lower | size of what each role is handed (the handoff baton) |
| `guard_refusals` | exact | `RunResult.guard_refusals`; must equal the cheats attempted |
| `false_blocks` | zero | honest-agent refusals in the guard log |
| `recovery_rate` | 100% | S8 |
| `wall_seconds` | lower | reported, never gated (machines differ) |

Wall time is informational only. Everything else is a count or a ratio, so it is stable across machines and can be gated.

## Comparing: the loop

`python -m tests.sim compare` takes two scorecards and prints three lists.

1. **Broken:** an invariant that passed before and fails now. Always blocks.
2. **Worse:** a metric that moved the wrong way by more than its tolerance. Blocks unless the change's hypothesis said it would, and the commit message says so.
3. **Better:** a metric that moved the right way. Reported, and the baseline can be updated.

Two ways to get the "before" scorecard:

- **Committed baseline** (`tests/sim/baseline/*.json`): fast, used in CI.
- **Against a git ref** (`compare --against main`): builds the ref in a temporary worktree and runs the same scenarios and seeds there. No stale baseline, and the right tool for a pull request: "what changed compared with main".

`compare --accept` rewrites the baseline, and refuses if anything is broken or worse. Baselines only move forward, and each update is its own commit that quotes the before and after table.

### How to land an improvement

1. **Hypothesis, in one paragraph** (in the commit or ticket): the change, the metric that should improve, the metrics that must not move.
2. **Expose the problem first.** Add or tune a scenario so today's scorecard shows the weakness (for example, reviewers rejecting for something the coder was never told). The baseline records it.
3. **Make the change.**
4. **Run:** unit suite, then `sim run`, then `sim compare --against main`.
5. **Read the three lists.** Broken or unexplained worse: fix or revert. Better as predicted: continue.
6. **Accept the baseline**, add the before and after table to `CHANGELOG.md`.
7. **Run the nightly full set** before a release.

Typical improvements this serves: a leaner handoff baton (watch `worker_prompt_bytes` and `first_pass_yield`), clearer rejection messages (watch `verify_attempts_per_ticket`), a smarter dispatcher (watch `steps_to_done`), a tighter guard (watch `cheat catch` and `false_blocks` together, so a tighter guard cannot buy safety by blocking honest agents).

## Does the simulation itself work (canaries)

A simulation that cannot fail proves nothing. `tests/sim/canaries.py` lists deliberate engine breakages, each applied as a patch in a temporary copy: make `approve` skip the owner check, make `verify` accept any exit code, let `merge` skip the combined test, drop the lock in `claim`, ignore `KAHNBAN_ROLE`. `python -m tests.sim canaries` runs the fast set against each patched copy and must see at least one invariant fail for every canary. If one passes, add the scenario or invariant that catches it. Run it when the simulation changes and nightly.

## Live tier (optional, noisy)

The same scenarios S1, S3 and S7 with the real worker command (`claude -p`, cheap model), run `R` times (start with 5). Compare medians and the spread, never single runs. Preflight `claude auth status` and one trivial call first. Gate nothing in CI; use it to judge a workflow improvement that only a real model can show, such as a clearer prompt.

## Steps

One commit per step. Each ends in something you can run.

1. **Skeleton and one scenario.** `tests/sim/` with `agents.py` (`honest`, `reviewer-honest`), `scenarios.py` (S1), the invariant checker (I1-I5, I10, I11) and `scorecard.json` output. Done when `python -m tests.sim run S1` prints a scorecard and I1-I11 as they apply.
2. **Core scenarios and the other agents.** S2-S7, all cheat policies, I6-I9, I13, I14. Done when every cheat is refused and the honest agent is never blocked.
3. **Compare and baseline.** `compare`, tolerances, `--accept`, `--against <ref>`. Done when changing a gate's wording changes nothing, and weakening a gate shows under "Broken".
4. **Canaries.** The five breakages above. Done when each turns the simulation red.
5. **Fault injection and recovery (S8-S10).** The `KAHNBAN_FAULT_AFTER_COMMITS` hook, I12. Done when every kill point recovers, or the first one that does not is a filed ticket.
6. **Upgrade and platform scenarios (S11, S12).** Old-engine board fixtures from tags, CRLF and path cases on both CI OSes.
7. **Scale and mix (S13, S14).** Distributions over seeds.
8. **CI.** `sim-fast` on every pull request with `compare --against main`; `sim-full` and canaries nightly; scorecards uploaded as artifacts.
9. **Live tier.** The repeated-run wrapper and median comparison.
10. **First improvement through the loop.** Pick one item from NEXT_STEPS.md (for example the per-role rejection breakdown, or a smaller baton), and carry it through the seven-step protocol above, as the proof that the loop works.

## What this does not claim

- It confirms the engine and guard against the cheats listed. A cheat nobody wrote a policy for is untested, so every new bypass found in review becomes a new policy and a canary.
- Scripted agents show how the engine reacts, not how a language model behaves. Only the live tier says anything about real agents, and only statistically.
- The guard remains a tripwire against a worker with the same OS user, as the README already says. The simulation measures the tripwire; it does not turn it into a sandbox.
