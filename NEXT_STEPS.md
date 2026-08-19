# NEXT STEPS FOR THE NEXT AGENT

**Current date:** 2026-08-18
**Status:** Phase 1 engine complete — 176 tests passing, version `1.0.0`

Phase 1 of [plan.md](plan.md) §7 is code complete. Every module listed in the
Layer 1 tree exists with tests, all BL01–BL16 rules have negative fixtures, and
the full lifecycle runs end to end on a scratch repository.

---

## 1. Commit and tag (repository owner)

The work sits uncommitted in the working tree on `main`. Review it, then:

```powershell
git checkout -b engine-v1
git add -A
git commit -m "feat: complete Kahnban v1.0.0 engine (gitops, core, linter, worktree, status, MCP, CLI)"
git tag v1.0.0
```

Nothing was committed automatically, and no tag was created.

---

## 2. Phase 2 — adopt in `heirs_ancients`

```powershell
py -3 -m pip install -e C:\Github\Kahnban
cd C:\github\heirs_ancients
kahnban init --prefix HOA
```

Then:
1. Replace `plans/board.config.json` with the §6.1 config (WIP limit 3,
   `shared_caches: [".godot"]`, `validation_command` pointing at
   `tools\run_all_tests.ps1`, and the `validation_class` / `balance_risk`
   extension fields).
2. Copy `adapters/AGENTS.md` into `AGENTS.md`, `CLAUDE.md`, and `.cursorrules`.
3. Register the MCP server with the `.vscode/mcp.json` snippet from
   `adapters/MCP.md`.
4. Insert the lint gate at the top of `tools/run_all_tests.ps1` (§6.2) and
   confirm `tests/data_integrity_test.gd` DI-06 stays green — the gate is a
   runner step, not a new `.gd` test, precisely so the headless test count does
   not change.
5. Run `kahnban lint` and one full ticket lifecycle before migrating the backlog.

## 3. Phase 3 — backlog migration

Audit the open items in `plans/IMPLEMENTATION_PLAN.md` (reconcile Programs B and
E against the code), generate 25–40 tickets with `kahnban new`, then move
`plans/IMPLEMENTATION_PLAN.md` to `plans/archive/IMPLEMENTATION_PLAN_2026-08-18.md`
marked `SUPERSEDED` and fix inbound references in `AGENTS.md`, `README.md`, and
the design docs.

## 4. Phase 4 — `citadel` portability smoke test

`kahnban init --prefix CIT`, run one ticket through claim → verify → done.
Acceptance: zero code changes required in the engine.

## 5. CI (plan §8)

Add a GitHub Actions matrix on `windows-latest` + `ubuntu-latest`, Python 3.10
and 3.12, running `py -3 -m pytest -q`. The suite is platform-agnostic —
junction-specific assertions are `skipif(os.name != "nt")` and POSIX gets
directory symlinks — but it has only been executed on Windows so far, so expect
to shake out one or two path assumptions on the first Linux run.

---

## Working on the engine itself

- **Dependency order:** `gitops` → `core` → `linter`/`status`/`worktree` →
  `cli`/`mcp_server`. `core` deliberately owns the body helpers the linter shares
  (`section`, `checkboxes`, `parse_blast_radius`, `extension_problems`) so the
  linter can import `core` without a cycle.
- **Every board write goes through `core.transition()`.** Do not add a second
  writer; gates call it with `fm_updates` and a log entry.
- **Regenerate lint fixtures** with `py -3 tests/fixtures/generate.py` after
  changing a rule, then re-run `tests/test_linter.py`.
- **Tests are slow because they are honest** — they create real git repos,
  worktrees, and subprocesses in `tmp_path`. Run one file at a time while
  iterating (`py -3 -m pytest tests/test_core.py -q`).
- **No silent exceptions.** Failures raise; `cli.py` maps them to stderr plus
  exit 1 (refusal) or 2 (config/IO).

## Known rough edges

- `core.py` is large (1,526 lines). If it grows further, the natural split is
  gates (`ready`/`claim`/`verify`/`done`/`move`/`cleanup`) into a `gates.py` that
  imports the primitives from `core`.
- The cross-clone claim race is covered by two tests: the common path (the loser
  pulls first and refuses without committing) and the narrow window where the
  remote moves between pull and push, which is exercised by patching
  `pull_ff_only` to a no-op. A true wall-clock race across clones is not
  deterministically reproducible in a test.
- `board.config.json` is not schema-validated beyond the keys the engine reads;
  an unknown key is silently ignored.
