# Remediation plan for the Phase 1–5 review findings

Source: the two-axis review of `3b9f965...HEAD` (Standards `S*`, Spec `P*` for gaps and `W*` for wrong behaviour, `B*` for scope notes). The Spec reviewer read the diff but did not run it, so each item below says whether I confirmed it in the code.

## Ground rules for every change

- **Test first.** Each item names the failing test that proves the defect, written before the fix.
- **No new behaviour without a switch** where an adopter's existing board could change (marked *config*).
- **The guard is a tripwire, not a sandbox.** Where a finding is a limit of that model (W4, W5), the plan hardens what can be hardened, documents the ceiling, and names the real boundary (a container or a separate OS user).
- Keep `kahnban skills check` green and add the new invariants to it where they can be checked statically.

## Status of each finding

| ID | Finding | Confirmed? | Decision |
|---|---|---|---|
| W1 | `confirmed: ready` not bound to the contract, never cleared | Yes: `needs_human` compares to the literal `"ready"` | Fix |
| W2 | Runner's own `ready` call bypasses the attended check | By design | Document |
| W3 | `attempts.json` unlocked, never reset on progress, silent reset on corruption | Yes (read-modify-write in `core`, no lock) | Fix |
| W4 | Signing key readable by a worker | Yes, admitted in `trust.py` | Mitigate, document ceiling |
| W5 | Guard bypasses (quoted flags, `git -c`, redirection) | Yes: `_bash_problem` splits on whitespace | Harden, document ceiling |
| W6 | Case-sensitive `relative_to` on Windows | Plausible, not reproduced | Fix with a Windows-only test |
| W7 | Escalated ticket's baton has no prompt; curator never a baton role | Yes for escalated; curator is not per-ticket | Fix the first, drop the second |
| P1 | Stale baton on refresh failure | Yes (`_refresh_baton` downgrades to `[WARN]`) | Fix at the point of use |
| P2 | `on-refusal` not fired for every refusal | Yes (decorator on 7 gates only) | Fix |
| P3 | Veto runs after `claim` made the worktree and lease | Yes (`worktree.provision` precedes `transition`) | Fix; also fail-closed option |
| P4 | Stop hook nudges once; curator has no exit check | Yes | Fix |
| P5 | No test that Gemini/Cursor files match the manifest | Partly: drift is tested, content is not | Add golden tests |
| P6 | `.cursor` missing from `skills check` | `.cursor` has no skill copies, so no. But `check` does not verify any hook is installed | Reframe and fix |
| B1 | `install` silently re-pins edited files | Yes | Fix |
| B2–B5 | ~30 skill edits, `human_gates`, hook rewrites, other files | Intended in earlier phases | Accept, note in changelog |
| S1–S9 | Standards smells | Yes | Fix in the cleanup PR |

## Delivery order

Five pull requests, in this order so refactors do not collide with behaviour fixes.

1. **PR 1: attended and counting correctness** (W1, W3, B1, W6). Small, self-contained.
2. **PR 2: guard and signing hardening** (W5, W4).
3. **PR 3: declarative exit checks** (S1, S2, S3, P4). One change to how a role's exit condition is defined, which also gives the curator one.
4. **PR 4: handoff and hook integrity** (P1, P2, P3, P5, P6, W7).
5. **PR 5: structure and naming cleanup** (S4–S9). Pure refactor, no behaviour change, last so the earlier tests protect it.

---

## PR 1: attended and counting correctness

### W1. Bind the `ready` confirmation to the contract
- **Defect:** `confirm` on a refining ticket writes `confirmed: ready`. `needs_human` accepts that literal forever. A ticket edited after confirmation, or sent back to refining, skips the human.
- **Change** (`core.confirm`, `core.needs_human`, `core.ready`):
  - Store `confirmed: ready:<contract_hash(body)>`.
  - `needs_human` recomputes `contract_hash` and compares.
  - `ready()` clears `confirmed` on success; `reject`, `verify` and `claim` already rewrite frontmatter, so add `"confirmed": ""` to those updates so a returning ticket asks again.
- **Tests:** confirm, edit the acceptance criteria, expect `needs_human == "ready"`; confirm, pass ready, bounce to refining, expect a new human gate.
- **Risk:** low. Existing confirmed tickets (`confirmed: ready`) simply ask once more.

### W2. Document the runner bypass
- Add a short note to the README Autonomy row and `docs/how-it-works.md`: in attended mode the *runner* takes the gate once a human has confirmed, and `KAHNBAN_ROLE` is what stops a worker taking it. A human running `kahnban merge` or `kahnban done` directly is trusted by design.

### W3. Make attempt counting trustworthy
- **Defect:** unlocked read-modify-write; counts only reset on escalate, unblock, confirm and merge; a corrupt file silently becomes `{}`.
- **Change** (`core.load_attempts` / `save_attempts` / `clear_attempts`, `runner.run`):
  - Replace the nested dict with a small dataclass `Attempt(count, last, fingerprint)` and one `attempts.py` helper that does load-modify-save under a file lock (reuse the lock primitive `board_lock` uses; keep it separate so a long gate does not block counting).
  - Key by `action|ticket` but store a **fingerprint** of the ticket's progress state (column, branch tip, `verified_sha`). When the fingerprint changes, the count restarts: a legitimate reject-and-reclaim cycle is progress, a stuck one is not.
  - On a corrupt file, move it to `attempts.json.corrupt`, log a `[WARN]`, and start fresh rather than overwriting silently.
  - In `runner.run`, load once per step and save once (removes the three reloads and the three `# type: ignore` lines).
- **Tests:** two concurrent processes incrementing 50 times each end at 100; a rework cycle with new commits does not escalate at `max_attempts`; a corrupt file is preserved and warned about.
- **Risk:** medium. The fingerprint must not change on a no-op step, or a stuck ticket never escalates. Test with the existing idle-worker case.

### B1. Install must not silently re-pin
- **Defect:** `install_skills` always rewrites `skills.lock.json`, so a tampered skill is re-pinned by the next install.
- **Change** (`skills.install_skills`, `cli`):
  - Write the lock only when none exists, or with a new `--relock` flag.
  - When a lock exists, run `trust.lock_problems` before copying and print them; after the copy, report which pinned files the install changed and tell the user to review them and run `kahnban skills lock`.
- **Tests:** tamper, reinstall without `--relock`, lock still reports the tampered file; with `--relock` it is re-pinned.
- **Risk:** low. A bundled-skill upgrade now needs one extra command, which is the point.

### W6. Case-insensitive paths on Windows
- **Change** (`guard._edit_problem`, `core.path_within`): compare `os.path.normcase(str(path))` on both sides before `relative_to`, and `resolve()` both to fold 8.3 short names.
- **Tests:** a `skipif(os.name != "nt")` test where the worktree is spelled `C:\Foo` and the edit path `c:\foo\src\app.py`.

---

## PR 2: guard and signing hardening

### W5. Make the Bash check parse commands instead of splitting words
- **Defect:** `_bash_problem` does `command.split()`, so `"--force"`, `--force=1` joined forms and `git -c x=y merge` slip past, and `sed -i`, `>` and `tee` write files with no edit check.
- **Change** (`guard.py`, new `guard_shell.py` if it grows):
  1. Split the line into simple commands on `;`, `&&`, `||`, `|` and newlines using `shlex` with `punctuation_chars=True`; recurse into `$(...)`, backticks and `bash -c '...'` / `sh -c` / `powershell -Command` arguments.
  2. Tokenise each simple command with quotes removed, then check override flags on the *unquoted* tokens.
  3. Parse `git` properly: skip global options (`-c k=v`, `-C path`, `--git-dir=`, `--work-tree=`, `--no-pager`) and test the real subcommand against the forbidden set.
  4. Detect writes: redirection targets (`>`, `>>`), `tee`, `sed -i`, `Set-Content`, `Out-File`, `cp`, `mv`, `rm`, `del`. Resolve each target path and run it through `_edit_problem`, so a bash write is held to the same blast radius as an edit tool.
  5. Anything the parser cannot read (unbalanced quotes, dynamic `eval`) is refused for roles that do not edit, and allowed with a stderr note for the coder, as today.
- **Tests:** a table of about 25 bypass attempts per bullet above, each asserted blocked, plus a table of ordinary commands (`pytest -q`, `git status`, `git commit -m "fix: merge docs"`) asserted allowed. The last one matters: the word "merge" inside a quoted message must not trip it.
- **Ceiling (document):** a determined agent can still obfuscate (`python -c`, encoded payloads). The README and `guard.py` already say so; add the recommendation to run workers in a container or a separate OS user when the repo is not fully trusted.
- **Risk:** medium. False positives block honest coders. Roll out with the table above and a `KAHNBAN_GUARD_LOG` line so blocked commands are visible in the run log.

### W4. Keep the signing key away from workers
- **Defect:** the key lives in `.git/kahnban-signing.key`, readable by any worker, and the reviewer worker itself runs `approve`.
- **Change** (`trust.py`, `runner.py`, `core.approve`):
  1. Move the default key out of the repo to a per-user directory (`%APPDATA%\kahnban\keys\<sha256 of repo path>` on Windows, `$XDG_STATE_HOME/kahnban/keys/…` elsewhere), created with owner-only permissions. `KAHNBAN_SIGNING_KEY` still wins for CI.
  2. **Workers do not sign.** When `KAHNBAN_ROLE` is set, `approve` records `reviewer` and `approved_sha` but no signature. The runner strips `KAHNBAN_SIGNING_KEY` from the worker environment.
  3. After a `qa_reviewer` worker exits, the runner checks that the approval came from that worker's ticket and tip, then countersigns it (`trust.sign`) and commits the signature. A forged `reviewer:` written any other way never gets a signature.
  4. Guard: refuse reads of the key directory by name for every worker role (`cat`, `type`, `Get-Content`) as a tripwire.
  5. `kahnban init` writes `"require_signed_approvals": true` for **new** boards. Existing boards keep `false` until changed.
- **Tests:** a worker-run `approve` yields no signature; the runner countersigns; `merge` refuses an unsigned or altered approval; the key file is not under the project root.
- **Ceiling (document):** the same OS user can still read the key. The guarantee needs workers in a container or under another account.
- **Risk:** medium. Humans running `approve` by hand must still get a signature: sign whenever `KAHNBAN_ROLE` is unset.

---

## PR 3: declarative exit checks (S1, S2, S3, P4)

### S1 + S2. One place for role exit conditions
- **Defect:** `guard.exit_problem` reaches into `core._require_clean_tip` and `core._diff_scope_problems`, hard-codes `("coder", "qa_reviewer", "spec_analyst")`, and the same role names are repeated in `handoff.py`.
- **Change:**
  - Add `"exit": "<check name>"` to each role in `roles.json` (`committed_work`, `decision_recorded`, `ready_gate_passes`, `learnings_processed`, or `none`).
  - New `exit_checks.py` holds one function per check name, a dict mapping names to functions, and `problem(role, env)`. It calls **public** `core.require_clean_tip` and `core.diff_scope_problems` (rename the two helpers and keep thin aliases for one release).
  - `guard.exit_problem` becomes a call to `exit_checks.problem`. `skills check` fails if a role names an unknown check.
  - Replace string sentinels in `handoff.next_role` with a small `Stage` enum, and `autonomy` with a `StrEnum`.
- **Tests:** existing exit tests keep passing unchanged; add one that a role without an `exit` key is rejected by `skills check`.

### S3. Derive baton commands from the manifest
- `handoff.build_handoff_baton`'s per-role `cmd` dict and `handoff._prompt` use `roles.finish` and `roles.role(name)["gate"]` so the role names appear only in `roles.json`.

### P4. Stop-hook nudges and the curator exit
- **Change:**
  - Count nudges per `(role, ticket)` in a small file under the run's artifact directory; allow `max_stop_nudges` (default 2, *config*) before letting the worker stop. The runner deletes the counter before starting each worker. Align Cursor's `loop_limit` to the same number.
  - Curator exit check `learnings_processed`: stop is allowed when no recurring learning (the dispatcher's own test) remains unharvested, or the curator escalated.
  - State plainly in the docs that the runner's post-worker check is the authoritative gate and the Stop hook is a nudge.
- **Tests:** a coder is nudged twice then released; the curator is nudged while a recurring learning exists and released after a fix ticket is created.
- **Open point:** I have not yet read how the curator finishes; confirm its definition of done before writing `learnings_processed`.

---

## PR 4: handoff and hook integrity

### P1. Never start a worker on a stale baton
- Keep the `[WARN]` inside `transition()` (a failed baton write must not undo a committed move). Add `core.refresh_baton_strict(config, ticket_id)` that raises, and call it in `runner._work` before each worker starts. If it fails the step is refused with the reason, not run on old instructions. Document that "no `.agents/`" means the baton feature is off, and make `handoff.refresh` return a typed `Skipped` value instead of `None`, so the two cases cannot be confused.
- **Test:** make the handoff directory unwritable; the move succeeds with a warning and the next worker step is refused.

### P2. `on-refusal` for every refusal
- Apply `_refusals_reported` to `escalate`, `unblock`, `confirm`, `cleanup` and `move`.
- Pre-transition vetoes already surface as a `GateError` from a decorated gate; add a test for each gate so the coverage cannot regress.
- Guard refusals: `guard.main` calls the `on-refusal` hook best-effort (project root from `KAHNBAN_PROJECT_ROOT`, gate name `guard`) before exiting 2. Never let the hook failure change the exit code.

### P3. Veto before side effects, and an optional fail-closed mode
- **Change** (`core.claim`, `core.transition`):
  - Extract `_check_veto(config, ticket, target)`. `claim` calls it before `worktree.provision`; `transition(..., vetoed=True)` skips the second run so a hook with side effects runs once.
  - If `transition` fails after `provision`, remove the new worktree and branch and drop the lease (a `try/except` around the existing attempt loop).
  - *Config* `strict_hooks: true`: a `pre-transition` hook that times out, crashes, or exits anything other than 0 or 2 refuses the move. Default `false`, so existing boards behave as today.
- **Tests:** a vetoing hook leaves no `.worktrees/<ID>`, no `ticket/<ID>` branch and no lease; with `strict_hooks`, a hook that exits 1 refuses the move.

### P5. Golden tests for the generated agent files
- Snapshot `agent_markdown(role, harness)` for every worker role and harness under `tests/golden/`, plus a test that regenerates them with an `--update` env flag. Add payload fixtures taken from each harness's documentation for the guard (`BeforeTool`, `beforeShellExecution`, `preToolUse`, Claude `PreToolUse`) and assert the same decision from each.

### P6. `skills check` verifies hooks, not just skill copies
- `.cursor` has no skill copies, so adding it to `HARNESS_SKILL_DIRS` would be wrong. The real gap is that `check` never confirms a harness's hook is installed. Add: for each harness directory present, assert the guard and stop commands appear in `.claude/settings.json`, `.gemini/settings.json` or `.cursor/hooks.json`, and that `.cursor/rules/kanban.mdc` matches `CURSOR_MDC_CONTENT`.

### W7. A prompt for escalated tickets
- `handoff._prompt("human")` returns the escalation reason and the exact commands (`kahnban unblock <ID> --reason …`, or `kahnban confirm <ID>` when the reason starts `attended run:`). Drop the "curator is never a baton role" item: the baton is per ticket and the curator has none.

---

## PR 5: structure and naming cleanup (S4–S9)

Pure refactor; every test must pass unchanged.

| ID | Change |
|---|---|
| S4 | One `merge_hook_config(path, spec)` replaces `_install_guard_hook` and `_install_cursor_hooks`. One `HARNESS_HOOKS` table defines the events, matchers and commands for Claude, Gemini and Cursor. Move `write_text_atomic` to a small `fsutil.py` so the inline `from kahnban.core import …` imports go away. |
| S5 | `Approval` dataclass (`ticket_id`, `tip`, `reviewer`, `signature`) with `from_fields`, used by `trust.sign`, `signature_problem` and `core._signature_problem`. `HookSpec` dataclass for the `(path, messages, hooks)` clump. |
| S6 | Rename `trust.collect` → `fingerprints`, `handoff.refresh(event=…)` → `reason=`, internal `skills.check` → `audit` (the CLI word stays `check`), and replace the `"action|ticket"` string key with `Attempt` keyed by a tuple serialised in one function. |
| S7 | Split `skills.py`: `harnesses.py` (install, hooks, agent files) and `skills_check.py` (lint). Add `cli.command_names()` as a public function so `_cli_commands` stops reading `build_parser()._actions`. |
| S8 | Delete the pointer comment in `guard.py`; trim `skills.check` and `guard.exit_problem` docstrings to what and why in two or three lines. Keep the comments that explain third-party harness limits. |
| S9 | Turn `agent_markdown`'s `harness` string-switch into rows of the `HARNESS_HOOKS` table (front-matter fields, whether skills are preloaded). Leave `roles.finish`, `edits` and `runner_only`: they carry defaults and are not just pass-throughs. |

## Accepted as-is (with a note)

- **B2** (about 30 skill edits) and **B5** (hook rewrites): both were needed for the invocation-flag fix and for hooks to receive stdin JSON. Add a line to a new `CHANGELOG.md` entry.
- **B3** (`mcp_server.py`, docs): the MCP change shares the guard's `command_problem`, which Phase 1 required. I did not change `pyproject.toml` version in Phases 3–5; confirm with `git diff 3b9f965 -- pyproject.toml` that the only change is shipping `templates/*.json`.
- **B4** (`human_gates`): keep; it is documented and tested.

## Verification matrix

| Check | How |
|---|---|
| Behaviour | Full suite on Windows and Linux CI, plus the new tests named above |
| Guard table | The bypass and allow tables in PR 2 must both pass |
| Concurrency | Two-process attempt-count test in PR 1 |
| Live harness | One real `claude -p --agent` coder run in an adopter repo to confirm the Stop hook nudges and releases; Gemini and Cursor still need a manual check against their current releases |
| Docs | README rows for Autonomy, Trust and role manifest updated; `docs/how-it-works.md` flowcharts re-rendered if the gate order changes (P3) |

## Decisions and outcome

| Question | Answer |
|---|---|
| `strict_hooks` default for new boards | Yes: `kahnban init` writes `"strict_hooks": true`; existing boards keep `false` |
| Signing key location | Per user (`%APPDATA%\kahnban\keys`, or `$XDG_STATE_HOME/kahnban/keys`), `KAHNBAN_KEY_DIR` to override |
| Renames | Done without aliases: `trust.collect` → `fingerprints`, `handoff.refresh(event=)` → `reason=`, `skills.check` → `skills_check.audit` (the CLI word `skills check` is unchanged) |
| Delivery | One commit per item on `main` (P1–P3 landed as one commit because they edit the same functions) |

Every item above is implemented. What differs from the plan as written:

- **W6** is verified by a Windows-only test, which is skipped on Linux CI.
- **W4:** the reviewer worker's `approve` records no signature and the runner countersigns; a worker running as the same OS user can still read the key file. The guard refuses the obvious reads only.
- **P4:** the curator's exit check reuses the dispatcher's definition of "recurring" (`learnings.recurring`).
- **B1:** `skills install` leaves an existing lock alone and prints what changed; `--relock` re-pins.
- **S2:** autonomy modes, human gates, handoff stages and the human/nobody roles are plain-string constants in classes, not `StrEnum`, because the package supports Python 3.10.
- **Not done:** a live `claude -p --agent`, Gemini or Cursor worker has not run the hooks; the Gemini and Cursor payload shapes come from their documentation.
