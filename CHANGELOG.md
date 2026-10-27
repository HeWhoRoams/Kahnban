# Changelog

## Unreleased

### Contract seal and metrics
- `ready` (and the freeze at `claim`) store `contract_sig`, an HMAC of the ticket id and contract hash made with the approval key. Editing the criteria and the hash together now fails verification; with `require_signed_approvals`, a frozen contract with no signature is refused. A ticket frozen before this change needs `ready` again.
- `status.json` metrics add `by_owner` and `by_reviewer` (failed verifies and rejections per owner, rejections per reviewer), read from the ticket Log.
- The bundled `blast-radius` skill is now `change-impact`, so it no longer shares a name with the ticket field.
- `python tests/run_sim.py stability --runs N` lists the metrics that move on an unchanged tree; `--accept` records them so `compare` skips them. `tests/sim` counts as source for the proof gate on this board.

### Headless workers
- `kahnban skills install --harness claude --allow-worker-commands` writes `workers.default` into `plans/board.config.json` when the board has no workers: `claude -p --agent kahnban-{role} --permission-mode acceptEdits --allowedTools ...`, allowing `kahnban`, the git verbs a worker needs (never `git push`) and the board's test commands. Without the flag, install changes nothing, and an existing `workers` entry is never overwritten. The rules go in the command because a headless `claude -p` ignores `permissions.allow` in project settings. Live proof: a Haiku agent took a toy ticket to done in 4 steps.

### Crash recovery
- A lock file (`.claim.lock`, and the attempts and stop-nudge locks) records `pid`, `host` and time. A waiter that finds the lock of a process on this machine that no longer exists breaks it at once instead of waiting out the 300-second age limit; anything it cannot judge still falls back to the age rule. Only one waiter wins a break, and a lock made in the meantime is left alone. A release now retries when a waiter has the file open, which on Windows had made the holder's delete fail silently.
- A ticket that reached `5-done` but was killed before `cleanup` is finished by the next run (`finish_cleanup`), and `kahnban lint` warns about it (BL20). `kahnban next` says when the board is idle only because a live lease is still held.
- The merge queue's refusals are counted for the life of a ticket (`integration_refusals`). `confirm` resets the retry counts, so a human who kept confirming a ticket that cannot land looped for ever; after `max_attempts` refusals the run escalates instead of pausing, and `kahnban confirm --reason <what changed>` allows exactly one more try.
- Before and after, from the simulation's crash sweep (S8): 2 of 10 crash points recovered; now 12 of 12 (adding a crash while a worker runs). S5 with a human confirming every pause: 39 steps and no end; now 19 and an escalation.

### Self-test and simulation
- `tests/run_sim.py` drives the real engine with scripted honest, sloppy and cheating agents, checks fourteen rules after every step, and compares a scorecard against a committed baseline or another git ref ([docs/simulation-plan.md](docs/simulation-plan.md)). CI runs the fast set on pull requests and everything, plus deliberate-breakage canaries, nightly.
- `KAHNBAN_FAULT=before:K` or `after:K` ends the process hard at the K-th engine commit. It exists for the crash scenarios and does nothing unless set.
- Contract tests fail when a CLI command or MCP tool has no test, and `adapters/skills` must match the shipped templates.

### Roles, handoffs and harnesses
- `roles.json` defines each factory role once. The guard's tables, the prompts `run` and `next` hand out, the handoff baton and the native agent files for Claude Code, Gemini CLI and Cursor are rendered from it. `kahnban skills check` fails when skills, roles, generated files, installed hooks or the lock disagree.
- Every board move refreshes the ticket's baton and runs the `pre-transition` and `post-transition` hooks; every refusal runs `on-refusal`. `claim` asks the veto before it creates a worktree. A worker is not started on a baton the engine cannot write.
- The Stop hook pushes back up to `max_stop_nudges` times, per worker. Every worker role has an exit check, including the curator.
- Most bundled skills lost `disable-model-invocation`, which blocked agents and subagents from calling or preloading them; only `factory-mode` keeps it. Hooks now receive the event as JSON on stdin.

### Attended and unattended runs
- `"autonomy": "attended"` parks a ticket before the `merge` gate (and `ready`, via `human_gates`) until a person runs `kahnban confirm`. The merge confirmation is tied to the branch tip and is spent by a reject, a re-verify or the merge; the ready confirmation is tied to the ticket's contract.
- Retry counts are saved in `.artifacts/attempts.json`, locked against concurrent runners, and restart when a ticket makes progress. `confirm` also clears `blocked_on`, and counts reset on `unblock`, `confirm` and escalation.

### Trust
- `kahnban skills lock` pins every skill and hook by SHA-256. `skills install` leaves an existing pin alone unless given `--relock`. Hooks that no longer match the pin are not run under `strict_hooks`, and `kahnban run` will not start on a drifted lock.
- `require_signed_approvals` signs approvals with an HMAC. Workers never sign: the runner countersigns. The key lives in a per-user directory outside the repository.
- New boards from `kahnban init` turn on `require_signed_approvals` and `strict_hooks`.

### Guard
- The guard reads shell commands the way a shell does (quotes inside words, here-documents, `$(...)`, `cd`, expansions), refuses attempts to clear or change `KAHNBAN_*`, holds shell writes to the blast radius, and sees every tool call. `KAHNBAN_GUARD_LOG` records what it refused.
- It is a tripwire, not a sandbox: `python -c` and a worker running as the same OS user still get through.

### Internal
- New modules: `attempts`, `config` (split out of `core`, which re-exports it), `exit_checks`, `fsutil`, `guard_shell`, `harnesses`, `scaffold` (`init_board` moved here from `core`), `skills_check`, `trust`. `core._relative` is now `core.relative_path`. `trust.collect` is now `fingerprints`, `handoff.refresh(event=)` is `reason=`, and `skills.check` is `skills_check.audit`.
