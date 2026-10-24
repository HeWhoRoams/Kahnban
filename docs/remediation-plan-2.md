# Remediation plan 2: findings from the second review

Source: the two-axis review of `3b9f965...HEAD` run after the first remediation round (Standards `T*`, Spec `A*` missing or partial, `B*` beyond the plan, `C*` implemented but wrong). `X*` items are things I found while checking the reviewers' claims.

I re-ran the shell parser on the reviewer's cases and read the code behind each claim. Everything marked **Confirmed** was reproduced or read in the source; **Reported** means I take the reviewer's word. The Standards reviewer read only part of the diff, so step 0 below finishes that review before the structural work starts.

## Ground rules (carried over)

- Write the failing test first; each item names it.
- A rule that has now failed twice gets a structural barrier, not another sentence. The guard's argument-reading and the `KAHNBAN_ROLE` check are in that position (see C1 and C2).
- New behaviour that could stop an existing board's workflow sits behind config, and new boards get the strict default.
- The guard stays a tripwire. Where a finding hits its ceiling (`python -c`, same OS user), the plan hardens the obvious paths and says so in the README instead of claiming more.

## Status of each finding

| ID | Finding | Status | Decision |
|---|---|---|---|
| C1 | `KAHNBAN_ROLE` can be cleared (`VAR=`, `env -u`) so worker gates open | Confirmed | Fix |
| C2 | Parser bypasses: split quotes, `$x`, `cd` then write, backticks, `--no-verify` false positive | Confirmed | Fix |
| X1 | Other history-changing git commands pass (`branch -f main`, `cherry-pick`, `worktree`, `tag -f`) | Confirmed | Fix |
| X2 | The `PowerShell` tool is not routed to the guard | Likely (Claude Code on Windows exposes it); not tested | Fix |
| C3 | Secret-read check never runs under Claude and Gemini (matchers exclude Read/Grep/Glob) | Confirmed from the matcher strings | Fix, and migrate installed hooks |
| A1 | `confirmed: merge:<tip>` survives reject and re-verify at the same tip | Confirmed (only `ready()` clears it) | Fix |
| C4 | `strict_hooks` can block `escalate`, `unblock`, `confirm` | Confirmed (`_check_veto` runs on every transition) | Fix |
| C5 | `_refusals_reported` only catches `GateError`; `countersign` unreported | Confirmed | Fix |
| A2 | Unbalanced quotes judged by `split()` for every role | Confirmed | Fix |
| A3 | No `KAHNBAN_GUARD_LOG` | Confirmed | Fix |
| A4 | `core.path_within` not changed for Windows case | Reported; `normalize_path_entry` may already fold case | Prove with a test, change only if it fails |
| A5 | `lock_problems` runs after the copy, not before | Confirmed | Fix |
| A6 | Lock never read by `run` or `run_hook`; `plans/hooks` unpinned | Confirmed | Fix |
| A7 | `kanban.mdc` content not compared; hook check only where agents exist | Confirmed; the second half is by design | Fix the first, add a stale-hook check for the second |
| A8 | Cursor `loop_limit` fixed at 2 | Confirmed | Fix |
| A9 | No `CHANGELOG.md` | Confirmed | Fix |
| B1–B3 | `confirm` clears `blocked_on`; `attempts.clear` calls; constants not enums; `refresh` returns `None` | Confirmed, all deliberate | Accept and document |
| C6 | `attempts.py`: duplicate lock code; stale = wait = 10s; `spend_nudge` unlocked | Confirmed | Fix |
| C7 | `how-it-works.md:209` still says the Stop hook pushes back once | Confirmed | Fix |
| T1–T11 | Standards smells | Mostly confirmed; T9 is large | See PR D |

## Delivery order

0. **Finish the Standards review** of the files the reviewer did not read (`core.py`, `guard.py`, `guard_shell.py`, `handoff.py`, `skills_check.py`, the tests). Fold anything new into PR D.
1. **PR A: guard and trust boundary** (C1, C2, X1, X2, C3, A2, A3, A4).
2. **PR B: gates and hooks** (A1, C4, C5, A5, A6, A7, A8).
3. **PR C: concurrency** (C6, T1).
4. **PR D: structure** (T2–T11).
5. **PR E: docs** (C7, A9, B-notes, prose pass).

One commit per item on `main`, as before.

---

## PR A: guard and trust boundary

### C1. Make the role check hard to clear
- **Defect:** `ready()`, the unsigned worker `approve` and `needs_human` trust `KAHNBAN_ROLE`. `KAHNBAN_ROLE= kahnban ready T` and `env -u KAHNBAN_ROLE kahnban approve T` pass the guard (it strips `VAR=` and `env` wrappers) and then run as a human.
- **Why a barrier, not a rule:** this is a second pass at the same hole (the first review found `--force` spelled around the guard), so the fix is structural.
- **Change** (`guard_shell.py`, `guard.py`, `core.py`):
  1. In `_simple` keep the wrapper words and the `VAR=value` prefixes in a separate `Simple.env` list instead of discarding them. The guard refuses any command whose assignments or `env` options name a `KAHNBAN_*` variable (`env -u`, `-i`, `--ignore-environment`, `export`, `unset`, `set`, PowerShell `$env:KAHNBAN_ROLE`), for every role.
  2. Add `core.worker_role()` as the one reader of `KAHNBAN_ROLE`, used by `ready`, `approve`, `needs_human` and the CLI's own role check, so the trust decision lives in one place.
  3. Defence in depth: the runner also exports `KAHNBAN_RUN_ID` (a random value) and records it in `.artifacts/run-<id>`. `worker_role()` only honours `KAHNBAN_ROLE` together with a matching live run id, so a command that clears one variable but cannot read the other cannot pass. The ceiling is still a worker that reads its own environment from outside the shell.
- **Tests:** a table of about 12 clearing attempts, each refused; a human shell (no role) still runs `ready` and `approve`; a role set without a run id is ignored by the engine with a warning.
- **Risk:** medium. A manually launched worker (no runner) has no run id, so the interactive path must stay allowed: honour a bare role only when `KAHNBAN_INTERACTIVE_ROLE` is set deliberately. Needs a decision (below).

### C2. Parse words the way a shell builds them
- **Defect (all reproduced):** `git m""erge` and `--no-ver""ify` keep the quotes inside one token; `git --no-pager "mer"ge` splits into `mer`, `ge`; `x=merge; git $x` and `git$IFS merge` are not expanded; `cd .. && echo > f` resolves against the original directory; a backtick inside quotes is rewritten to ` ; `; `git commit -m "--no-verify"` is refused although the flag is only message text.
- **Change** (`guard_shell.py`):
  1. **Word assembly.** Replace `unquote` with `word(token)`: walk the characters, drop `'...'` and `"..."` delimiters, and join the pieces, leaving backslashes alone (Windows paths). `m""erge` becomes `merge`; `"mer"ge` stays one word.
  2. **Unknown expansions.** If a word in command position, in a git or `kahnban` subcommand position, or in a write target contains `$`, `%VAR%`, a backtick or `~`, return it as `Simple.opaque`. The guard refuses opaque command and subcommand positions for every role ("cannot tell what this runs"). Opaque arguments elsewhere stay allowed.
  3. **Working directory.** `parse` returns each command with the directory it runs in: it tracks `cd`, `pushd`, `Set-Location` and a `(`…`)` stack. An unresolvable `cd` (a variable, `cd -`) makes later writes opaque.
  4. **Backticks.** Treat a backtick as a command-substitution delimiter only outside quotes; inside quotes leave the text as written.
  5. **Message values.** Skip the value after `-m`, `--message`, `-F`, `--file`, `--reason`, `-C`, `--author`, `--date` when checking override flags, so message text is not read as a flag. A flag directly after one of these still counts (`-m --no-verify` is a message, `--no-verify` alone is a flag).
- **Tests:** extend `tests/test_guard_shell.py` with the six reproduced cases as refused or allowed, plus the existing tables unchanged.
- **Risk:** medium: false positives block honest coders. Mitigation: the allow table, plus A3's log so a blocked command is visible.

### X1. More git commands that rewrite shared state
- **Defect:** `git branch -f main HEAD`, `git cherry-pick`, `git worktree add|remove|prune`, `git tag -f|-d`, `git symbolic-ref`, `git replace` all pass. `git branch -f main HEAD` moves `main` without a merge.
- **Change** (`guard.py`): add `cherry-pick`, `worktree`, `symbolic-ref`, `replace` and `gc` to `GIT_FORBIDDEN`, and refuse `branch` and `tag` when they carry `-f`, `--force`, `-d`, `-D`, `-m`, `-M` or `--delete`. Keep `checkout -- <path>`, `restore`, `stash` and `commit --amend` allowed because they only touch the worker's own branch and files.
- **Tests:** extend `HISTORY` and `ALLOWED` in `test_guard_shell.py`.

### X2. Route the PowerShell tool through the guard
- **Defect:** Claude Code on Windows has a `PowerShell` tool. `SHELL_TOOLS` and the Claude matcher name `Bash` only, so a Windows worker using PowerShell is unguarded.
- **Change:** add `PowerShell` to `SHELL_TOOLS` and the Claude matcher. `guard_shell` already knows `powershell`/`pwsh -Command`; add PowerShell syntax that differs from POSIX: `;` as separator (already), `-and`/`-or`, backtick as the escape character (so do not treat it as a delimiter when the tool is PowerShell), `$env:NAME`, `Remove-Item`, `Set-Content` (already listed). `decide` passes the tool name to `_bash_problem` so it can choose the dialect.
- **Tests:** the Bash tables run again with `tool_name: "PowerShell"` and PowerShell spellings. **Verify first** that the tool is actually named `PowerShell` in the hook payload, by logging one real payload.

### C3. Make the secret-read check reachable
- **Defect:** `READ_TOOLS` is tested inside `decide`, but the Claude matcher (`Edit|Write|MultiEdit|NotebookEdit|Bash`) and Gemini's never call the hook for `Read`, `Grep` or `Glob`.
- **Change** (`harnesses.py`):
  1. Drop the matcher for Claude and Gemini guard entries (`matcher=""`), so the guard sees every tool call; unknown tools are already allowed. Cost: one Python start per tool call, about the same as today's Bash and Edit calls.
  2. Add Gemini's file tools to `READ_TOOLS` (`read_file`, `read_many_files`, `glob`, `search_file_content`, `grep_search`, `list_directory`) and `NotebookRead` for Claude.
  3. **Migration:** `merge_hooks` only adds a missing command. Change it to replace an existing guard entry whose matcher differs from the table, so `skills install` upgrades installed projects, and `skills check` reports an old matcher as stale.
- **Tests:** a Read of the key path is refused through the `PreToolUse` payload shape; install over an old settings file rewrites the matcher and keeps other hooks; check flags the old matcher.

### A2. Unbalanced quotes
- **Change:** `_bash_problem` refuses an unparsable line for roles with no edit scope (reviewer, curator when it has no write scope) and logs a note for the coder, who keeps the split-words fallback. Add the key/override checks to the fallback so it is not weaker than the parser on those.
- **Test:** a reviewer with `echo "oops` is refused; a coder is not blocked but `--force` in the same line still is.

### A3. Guard log
- **Change:** when `KAHNBAN_GUARD_LOG` is set, `guard.main` appends one JSON line per refusal (`time`, `role`, `tool`, `reason`, first 200 characters of the command). `kahnban run` sets it to `<run log>.guard` next to the existing run log and prints the count at the end of the run.
- **Test:** a blocked command appears in the log; an allowed one does not.

### A4. Windows case in `path_within`
- Write the test first: `path_within("SRC/App.py", ("src/app.py",))` on Windows. If `normalize_path_entry` already folds case, close the item with the test and no change; otherwise fold in `normalize_path_entry`. Skip on Linux.

---

## PR B: gates and hooks

### A1. Spend merge confirmations
- **Defect:** only `ready()` clears `confirmed`. After a reject and a re-verify at the same tip the old `merge:<tip>` mark is still valid and the human gate is skipped.
- **Change** (`core.reject`, `core.verify`, `core.merge`): add `"confirmed": ""` to the frontmatter updates of `reject` and of a passing `verify`, and clear it on a successful `merge` (the confirmation has been used).
- **Tests:** confirm, reject, re-verify at the same tip: `needs_human` is `merge` again; confirm then merge: the mark is gone.

### C4. Escape hatches are never vetoed
- **Defect:** `_check_veto` runs for every `transition`, including the same-column ones `escalate`, `unblock` and `confirm` use, so a crashing hook under `strict_hooks` traps a ticket.
- **Change:** `_check_veto` returns immediately when `ticket.column == target_column` (the move changes no column, so there is nothing to veto). Document that `pre-transition` hooks see column changes only. The failed-verify commit also stays in its column and so is unaffected.
- **Tests:** a failing hook with `strict_hooks` still lets `escalate`, `unblock` and `confirm` through, and still refuses `ready`. Update `test_strict_hooks_refuse_a_move_when_the_veto_hook_itself_fails` to use a column move.

### C5. Report every refusal
- **Change:** `_refusals_reported` catches `KahnbanError` (gate refusals, config errors, git errors surfaced as `KahnbanError`), still re-raises. Decorate `countersign`. `_report_refusal` passes `type(error).__name__` so a hook can tell a gate from a failure.
- **Test:** a non-`GateError` refusal and a countersign refusal reach `on-refusal`.

### A5. Say what the installer overwrote
- **Change:** `install_skills` records `lock_problems` before copying and again after. Files that were off-lock before and match again report "restored `<file>` to the bundled version"; files still off-lock are warned about as now.
- **Test:** tamper a bundled skill, install without `--relock`: the message names the restored file, and the lock is unchanged.

### A6. Enforce the pin where code runs
- **Defect:** hooks and skills are only checked when someone runs `skills check` or `install`.
- **Change** (`trust.py`, `hooks.py`, `runner.py`):
  1. Add `plans/hooks` to `LOCKED_DIRS` (it is where `find_hook_script` falls back to).
  2. `trust.verify_file(root, relative)` compares one file with the lock; `run_hook` calls it before executing a script when a lock exists. A mismatch is a refused move under `strict_hooks` and a `[WARN]` otherwise.
  3. `kahnban run` calls `trust.lock_problems` once at start. With `strict_hooks` it stops with the list ("review the change, then `kahnban skills lock`"); otherwise it prints them.
- **Tests:** tamper a hook, run `ready`: refused under `strict_hooks`, warned without; `run` refuses to start on a drifted lock.
- **Risk:** medium. A project with no lock is unaffected. A project that edits hooks routinely must re-lock each time; that is the point.

### A7. Check what a harness is really wired to
- **Change** (`skills_check.py`):
  1. `kanban.mdc` must contain the managed heading `# Kahnban Engineering Protocols`. Existence alone is not enough, but a byte-for-byte match would punish a user's edits.
  2. Add the stale-hook direction: a harness whose settings file carries a guard command but has no generated agents is reported ("guard hook installed without agents").
- **Tests:** replace the rule file with unrelated text, and install hooks without agents; both are reported.

### A8. Cursor stop cap follows the config
- **Change:** `HookEvent.options` for Cursor's stop hook is built at install time from `max_stop_nudges` (read through `core.load_config` when a board exists, otherwise 2). `merge_hooks` updates an existing `loop_limit` when it differs.
- **Test:** `max_stop_nudges: 4` installs `loop_limit: 4`; changing it and reinstalling updates the file.

---

## PR C: concurrency

### C6 + T1. One lock, one atomic write
- **Defect:** `attempts.py` carries its own O_EXCL lock with `LOCK_STALE_SEC == LOCK_WAIT_SEC`, so a waiter can judge a lock stale at the moment its holder takes it; `spend_nudge` is an unlocked read-modify-write; `_write` uses a fixed temp name; `trust.write_lock` writes in place.
- **Change:**
  1. Move the acquisition loop into `fsutil.exclusive(path, *, wait, stale)`; `attempts` and the nudge counter use it. Set `stale` well above the longest hold (30s against holds of milliseconds) and let a holder refresh the file's mtime before releasing. `board_lock` keeps its own `hold_seconds` semantics but calls the same primitive for acquisition.
  2. `attempts._write` and `trust.write_lock` call `fsutil.write_text_atomic`.
  3. `spend_nudge` and `reset_nudges` take `exclusive` on the counter file.
- **Tests:** two processes spend 50 nudges each and the total never exceeds `max_stop_nudges`; a lock file older than `stale` is broken exactly once (simulate with `os.utime`); the 90-bump thread test still passes.
- **Risk:** low to medium. Test on Windows and Linux; mtime resolution differs, which is the failure that bit CI earlier.

---

## PR D: structure

Do these after step 0 so smells in the unread files are included.

| ID | Change |
|---|---|
| T2 | `core.project_root_from_env(env)` replaces the repeated `Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve()` in `exit_checks` (twice) and `guard`. Also name the env variables once (`ENV_ROLE`, `ENV_TICKET`, `ENV_PROJECT_ROOT`, `ENV_WORKTREE`) in `core` and use them in `runner`, `guard` and `exit_checks`. |
| T3 | An `ExitContext` dataclass (`config`, `ticket`, `fields`, `body`, `env`) replaces the five-argument signature. A `@needs_ticket` decorator returns `None` when the context has no ticket, which removes the repeated guard and makes the curator's no-ticket check the one exception. |
| T4 | `attempts.py` imports `Config` under `TYPE_CHECKING` instead of `config: Any`; exit checks type `fields` as `Mapping[str, object]`. |
| T5 | A frozen `Role` dataclass built from `roles.json` replaces the raw dict (`spec["intro"]`, `.get("exit", "")`). Golden agent files and `skills check` guard the change; unknown keys in the manifest become an error at load time, which also covers T7. |
| T6 | `HARNESS_LAYOUT` (or a `flat` field on the hook table) replaces the three `harness == "cursor"` branches; the gemini and cursor blocks of `install_skills` become one loop over a `Harness` record (name, skills directory or none, rules file or none). |
| T7 | `exit_checks.problem` raises `KahnbanError` for an unknown `exit` name instead of returning no check; `skills check` already catches it statically, so this closes the runtime gap. |
| T8 | Keep `roles.HUMAN` and `roles.NOBODY` (the dispatcher uses `"none"` too) and make `dispatcher.py` use them; the `Check` type now matches every check via T3. |
| T9 | **Split `core.py` (3,219 lines).** `config.py` (Config, load, validation), `leases.py`, `scaffold.py` (`init_board`, `.gitkeep`). `core` re-exports the moved names for one release. Mechanical, big diff, high value for review; see the decision below. |
| T10 | `roles.SPEC_ANALYST`, `CODER`, `QA_REVIEWER`, `INTEGRATOR`, `CURATOR` constants replace bare role strings in `cli.py` and `dispatcher.py`. |
| T11 | Delete or fold the four restating comments: rename `HookEvent.options` to `extra_keys`, `matcher` to `tool_matcher`; drop the `HUMAN` and `NOBODY` trailing comments and keep the names. |

Each is a pure refactor: the suite plus the golden agent files and the guard tables must pass unchanged.

---

## PR E: docs

- **C7:** fix `how-it-works.md:209` ("pushes back once" → up to `max_stop_nudges`), then reread the gate diagrams for anything else the first remediation round changed (the veto now runs before `claim` creates the worktree; attended mode adds a human gate). Re-render the Mermaid blocks with the scratchpad harness and check them on GitHub.
- **A9:** add `CHANGELOG.md` with an Unreleased section: phases 1–5, the first remediation round, this round; list the skill edits (flag fix) and the hook rewrites that the first review called scope creep.
- **B1–B3:** note in the README that `confirm` also clears `blocked_on`, that counts reset on `unblock`/`confirm`/escalation, and that `refresh` returning `None` means "baton feature off".
- **Prose pass:** run the `unslop` rules over the README rows and docs written in the last two rounds, which the Standards reviewer did not check.
- Update `docs/remediation-plan.md`'s outcome table to point here.

## Verification

| Check | How |
|---|---|
| Behaviour | Full suite on Windows locally; Linux through CI, checked once after each PR's last push (CI failed on the earlier rounds for a Linux-only reason, so do not skip this) |
| Guard | The refused and allowed tables in `test_guard_shell.py` grow by the cases above; add the PowerShell variants once the tool name is confirmed |
| Concurrency | Two-process tests for attempts and nudges on both platforms |
| Live harness | One real `claude -p --agent` coder run in a scratch repo to confirm the Stop hook nudges, the guard log fills, and a Read of the key is refused; Gemini and Cursor still need a manual check |
| Docs | Mermaid re-render, README tables read against the code |

## Decisions

1. **C1:** guard-level refusal only. The run-id token is deferred: it needs an opt-in for hand-started workers, and the guard refusal already closes every spelling found.
2. **C3:** every tool call goes through the guard (no matcher), so a renamed tool cannot slip past.
3. **A6:** a drifted lock stops `kahnban run` when `strict_hooks` is on, and only warns otherwise.
4. **C4:** same-column moves are exempt from the veto.
5. **T5 and T9:** `Role` dataclass in PR D; the `core.py` split (T9) waits for a later round.

## Progress

| Step | State |
|---|---|
| 0: Standards pass over unread files | Done as a function-length scan only: `skills.install_skills` (156 lines; T6 shortens it), `handoff.build_handoff_baton` (97), `runner._work` (80), `skills_check.audit` (71). `core.py` itself is still unread for smells; its size is T9 |
| PR A: C1, C2, X1, X2, C3, A2, A3, A4 | Done |
| PR C: C6, T1 | Done early because CI on Windows 3.10 failed `test_concurrent_runners_do_not_lose_counts`: Windows raises `PermissionError`, not `FileExistsError`, while a lock file is being deleted. `fsutil.exclusive` now covers attempts and stop nudges |
| PR B, PR D, PR E | Not started |

Changes from the plan as written, made while implementing PR A:

- C1 landed as `core.worker_role()` plus a guard check; the run-id token is dropped (decision 1).
- C2: the tokenizer is hand-written instead of `shlex`, because `shlex` splits `"mer"ge` into two words.
- X1: `checkout`, `restore`, `stash` and `commit --amend` stay allowed; `reset` is refused only with `--hard`.
- A4: `normalize_path_entry` already folds case on Windows, so the item closed with a test and no code change.
- X2: the `PowerShell` tool is in `SHELL_TOOLS` and the Claude entry now has no matcher, so it is guarded; its real payload name is still unverified.
