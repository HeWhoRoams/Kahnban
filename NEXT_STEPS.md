# NEXT STEPS FOR THE NEXT AGENT

**Current date:** 2026-08-19
**Status:** Phase 1 engine + entry points complete — 248 tests passing, version `1.1.1`

Phase 1 of [plan.md](plan.md) §7 is code complete. Every module listed in the
Layer 1 tree exists with tests, all BL01–BL16 rules have negative fixtures, and
the full lifecycle runs end to end on a scratch repository. The entry-point
layer (§2.6) is in too: `kahnban capture` for ideation, `kahnban ingest` for
plan documents and feature specs, plus the matching MCP tools and BL17.

---

## 1. Merge, tag, and push — DONE

`main` is merged, tagged, and pushed through `v1.1.1` (`ae113d4`), in sync with
`origin/main`. Tags on the remote: `v1.0.0` (engine, `394a0a8`), `v1.1.0`
(entry-point layer), `v1.1.1` (the `--config` position fix below). Nothing
outstanding here.

---

## 2. Phase 2 — `heirs_ancients` adoption — DONE 2026-08-19

Committed on branch **`kahnban-adoption`** in `C:\github\heirs_ancients`
(`6d5212f` board scaffold, `bd04259` configuration and wiring), not merged and
not pushed:

- `plans/board.config.json` — §6.1 config: HOA prefix, WIP limit 3, worktrees
  on, `.godot` shared as a junction, `validation_command` →
  `tools/run_all_tests.ps1`, plus the `validation_class` and `balance_risk`
  extension fields and this repo's `ingest.section_aliases` vocabulary.
- `plans/tickets/` — column tree, archive, and a template carrying both
  extension fields.
- `AGENTS.md` — Kanban protocol section appended (no numeric claims, so DI-06's
  regex anchors are untouched).
- `tools/run_all_tests.ps1` — `kahnban lint` as the first gate; skips itself
  when no board config exists and reports the install command when the engine
  is missing.
- `.vscode/mcp.json` — stdio MCP registration.

Merged to `main` and pushed (`229948c`, `43d52b2`).

**Verified:** `kahnban lint` exits 0 on the empty board, and the gate runs
correctly inside `tools/run_all_tests.ps1`.

**Pre-existing DI-06 failure — found, attributed, and fixed.** DI-06 was failing
on their `main` with five stale-count mismatches (AGENTS.md claimed 30 systems
scripts / 50 UI scenes / 341 test scripts / 18 data files; the repo holds
33 / 51 / 346 / 19). Attribution was checked by running the suite on plain
`origin/main` with no board present: identical 32 passed / 5 failed, so the board
was not the cause — the drift arrived with upstream merge `256db1d`, which
restored older numbers while the files moved on. Corrected in `b78e84b` (counted
independently with DI-06's own `_count_files_in` semantics; the `game/ui`
breakdown went 11 → 12 modals so 33 + 12 + 6 still totals 51). The suite is now
37 passed / 0 failed, `RESULT: PASS`, runner exit 0.

Next for that repo: run one ticket end to end
(`kahnban capture` → refine → `ready` → `claim --worktree` → `verify`).

Adoption also surfaced an engine bug, now fixed: `--config` / `--project-root`
only worked *before* the subcommand, while §6.2's own gate command puts
`--config` after it. Both positions now work, with regression tests.

## 3. Phase 3 — backlog migration — DONE 2026-08-19

Reconciled by hand (the domain work the engine correctly can't do): read
Program B (all 20 items), Program E (the decision table plus the full §6.2
CONQUEST/DIPLOMATIC investigation), and Program F end to end, then verified a
sample of the claimed-implemented items directly against the code (garrison
persistence, save ordering, the Hall of Fame grid, the schema `$ref` walk, the
duplicate-key guard, and others — all matched). Result: **Program B is fully
closed** (every item carries an implementation note the code confirms) and
**Programs E/F are overwhelmingly resolved** — only nine genuinely open threads
remained, written up in the documented ingest shape
(`adapters/PLAN-INGESTION.md`) as `plans/BACKLOG_RECONCILED_2026-08-19.md` and
ingested onto their board as **HOA-001 through HOA-009**, one commit
(`825ce06`).

`plans/IMPLEMENTATION_PLAN.md` is archived to
`plans/archive/IMPLEMENTATION_PLAN_2026-08-19.md`, marked `SUPERSEDED` at the
top rather than deleted (it keeps the measured balance runs and owner-decision
rationale the tickets don't repeat). `AGENTS.md`'s two inbound references and
the four ticket bodies that cite the old filename were repointed to the
archived path.

**One real engine gap found and worked around, not yet fixed upstream:**
`kahnban ingest` has no label that sets a ticket's `blocked_on` field —
`depends_on` is the only frontmatter field ingest populates automatically
(and only from an unresolvable dependency reference), so a "Blocked on: ..."
line in a source plan lands as ordinary prose. One ticket (HOA-005, "retire the
`allocation` model after a release that hasn't shipped yet") genuinely needed
`blocked_on` set so the ready gate would refuse it before its trigger fires.
Fixed by hand-editing the ticket's frontmatter directly (legitimate while it's
still in `0-backlog`/`1-refining` — confirmed `kahnban ready` then refused it
with the correct reason) rather than by an ingest feature, since a `blocked_on:`
label would need its own alias handling and possibly a dedicated `IngestOptions`
field to avoid colliding with `depends_on`-derived blocking. Worth a small
follow-up ticket in Kahnban itself if plan ingestion keeps encountering
gate-style blocks like this one.

Verified: `kahnban lint` is 0 violations on the 9 tickets, and
`tools/run_all_tests.ps1 -Suite data_integrity_test` is still 37/37 through the
board gate after the archive move. Pushed to `heirs_ancients` main (`e80e2f9`).

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

- **Dependency order:** `gitops` → `core` → `ingest`/`linter`/`status`/`worktree`
  → `cli`/`mcp_server`. `core` deliberately owns the body helpers the linter and
  ingest share (`section`, `checkboxes`, `parse_blast_radius`,
  `extension_problems`, `replace_section`) so they can import `core` without a
  cycle.
- **Every new entry point is a `core.TicketDraft` producer.** Parse into drafts,
  then hand them to `core.create_tickets` — never write ticket files directly,
  and never set a checked acceptance box or a blast radius the source did not
  declare.
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

- `core.py` is large (1,754 lines). If it grows further, the natural split is
  gates (`ready`/`claim`/`verify`/`done`/`move`/`cleanup`) into a `gates.py` that
  imports the primitives from `core`.
- The cross-clone claim race is covered by two tests: the common path (the loser
  pulls first and refuses without committing) and the narrow window where the
  remote moves between pull and push, which is exercised by patching
  `pull_ff_only` to a no-op. A true wall-clock race across clones is not
  deterministically reproducible in a test.
- `board.config.json` is not schema-validated beyond the keys the engine reads;
  an unknown key is silently ignored (`ingest.section_aliases` is the exception —
  unknown field names are rejected).
- Ingest parsing is heuristic by design. It is accurate on plans written in the
  documented shape and honest elsewhere: unparseable file lists produce no blast
  radius and leave a note, so the gate refuses the ticket instead of trusting a
  guess. If an adopter's plans use different vocabulary, extend
  `ingest.section_aliases` rather than loosening the parser.
- `kahnban new` now produces empty body sections instead of the template's
  example text, because the examples were enough to pass the refinement gate.
