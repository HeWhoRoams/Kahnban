# Changelog

## Unreleased

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
