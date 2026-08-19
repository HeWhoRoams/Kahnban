# Kahnban Implementation Status

**Date:** 2026-08-19
**Current Phase:** Phase 1 (Engine) complete, plus the entry-point layer (§2.6)
**Status:** All 253 tests passing; engine version `1.1.2`
**Git:** `main` through `v1.1.1`; `1.1.2` (the `blocked_on` ingest fix) is
committed but not yet tagged/pushed — see below

---

## What's Implemented

| Module | Lines | Tests | Notes |
| :--- | ---: | ---: | :--- |
| `frontmatter.py` | 195 | 10 | Parse/serialize/mutate/append_log over the documented YAML subset |
| `gitops.py` | 204 | 9 | List-form subprocess wrappers; every failure raises `GitError` with stderr |
| `core.py` | 1,754 | 61 | Config, lookup, ID allocation, board lock, `transition()`, all gates, drafts |
| `ingest.py` | 1,013 | 53 | Plan/idea → ticket drafts, idempotency, dependency + `blocked_on` wiring, promotion |
| `linter.py` | 476 | 32 | BL01–BL17, ASCII output, `--json`, exemptions |
| `status.py` | 149 | 8 | STATUS.md + status.json projections |
| `worktree.py` | 193 | 13 | Worktree provisioning, NTFS junctions, junction-safe teardown |
| `mcp_server.py` | 664 | 24 | Stdio JSON-RPC 2.0, 12 tools, protocol conformance |
| `cli.py` | 437 | 34 | 13 subcommands, exit codes 0/1/2 |
| lifecycle (e2e) | — | 2 | init → new → ready → claim → verify → done → cleanup |

Run the suite with `py -3 -m pytest -q` (~5 minutes; it drives real git repos).

### Engine surface

```
# entry points — get work onto the board
kahnban capture <idea> [<idea> ...] [--from-file FILE|-] [--owner NAME] [--dry-run]
kahnban ingest <plan.md|glob> ... [--dry-run] [--json] [--heading-level N]
               [--section NAME] [--per-file] [--chain] [--update] [--ready] [--owner NAME]
kahnban new <title> [--problem TEXT | --problem-file FILE] [--owner NAME]

# pipeline
kahnban ready <ID>
kahnban claim <ID> --owner NAME [--worktree|--no-worktree] [--force]
                   [--force-overlap] [--strict-wip] [--reason TEXT]
kahnban verify <ID> [--manual-evidence FILE] [--force-scope] [--reason TEXT]
kahnban done <ID> [--merge-commit SHA]
kahnban move <ID> <column> --reason TEXT
kahnban cleanup <ID> [--abandon] [--reason TEXT]

# inspection and setup
kahnban lint [--json] [--strict] | kahnban sync | kahnban status
kahnban init --prefix PREFIX [--wip-limit N] [--validation-command CMD] [--no-worktrees]
```

MCP tools: `kanban_board_status`, `kanban_ticket_get`, `kanban_ticket_new`,
`kanban_plan_ingest`, `kanban_capture`, `kanban_ticket_ready`,
`kanban_ticket_claim`, `kanban_ticket_verify`, `kanban_ticket_done`,
`kanban_ticket_move`, `kanban_cleanup`, `kanban_sync`.

### How the invariants are enforced

- **Folders are the only status (Principle 1).** `transition()` is the single
  writer: mutate frontmatter → append `## Log` → `git mv` → regenerate both
  projections → one commit containing all of it. Batch creation
  (`create_tickets`) writes N tickets in **one** commit, so a 40-section plan
  ingest is one revertable commit rather than 40.
- **Board plane on the default branch (D2).** `transition()` refuses when a
  non-default branch is checked out, and `load_config` hops from a linked
  worktree to the main worktree.
- **Machine verification (D4).** `verify` executes the ticket's fenced
  `## Validation` command with the configured timeout, writes full output to
  `plans/tickets/.artifacts/`, records a truncated copy in `## Log`, and only
  advances on exit 0. Captured output is indented four spaces so no line can
  forge a markdown heading.
- **Domain isolation (D7).** Claim refuses on blast-radius overlap; verify
  refuses on out-of-scope diffs; BL16 catches forced states.
- **Concurrency (§3.3).** `.claim.lock` covers gate-check through commit; across
  clones the default-branch push arbitrates with rollback and one retry.
- **No fabricated readiness (§2.6).** Draft-managed sections are always
  rewritten, blank included — a ticket never inherits the template's example
  checkbox or example path, so an under-specified section cannot satisfy the
  refinement gate on boilerplate. `--ready` runs the *real* gate and reports
  what stayed behind.
- **Idempotent ingest (§2.6).** `source_doc` + `source_anchor` + `source_hash`
  on every ingested ticket; unchanged sections are skipped, new ones created,
  changed ones reported as drift (exit 1) rather than duplicated. `--update`
  re-renders only backlog/refining tickets and preserves the `## Log`. BL17
  fails the board if two tickets claim the same section.
- **Long text never on argv (§4.2).** `--problem-file`, `--from-file` (both
  accept `-` for stdin), `--manual-evidence FILE`.

### Entry points (§2.6)

| Source | Command | Behavior |
| :--- | :--- | :--- |
| Ideation | `kahnban capture "<idea>" …` | One backlog ticket per idea, one commit |
| AI-generated plan | `kahnban ingest plans/PLAN.md` | One ticket per work section, one commit |
| Untrusted plan | `… --dry-run` | Preview only; nothing written |
| Feature specs | `… --per-file specs/*.md` | One ticket per document |
| Part of a plan | `… --section "Phase 3"` | Only that subtree |
| Sequential plan | `… --chain` | Each ticket depends on the previous |
| Agent-authored ticket | `kanban_ticket_new(acceptance=…, blast_radius=…)` | Complete body in one call |

Parsing recognizes field labels as headings *or* inline `Label:` lines (including
`**Bold:**`), auto-detects the work-item heading level, ignores headings inside
fenced blocks, trims numbered prefixes from titles, preserves unmapped
subsections under `## Implementation notes`, and resolves dependency references
by title/anchor/ID — writing unresolvable ones to `blocked_on` so the gate
refuses until a human fixes them. Vocabulary is extensible per adopter via
`board.config.json → ingest.section_aliases`. Full guide:
[adapters/PLAN-INGESTION.md](adapters/PLAN-INGESTION.md).

### Lint fixtures

`tests/fixtures/` holds 18 boards: `clean-board/`, `clean-board-crlf/`, and
`violations/BL01 … BL16/`. `tests/fixtures/generate.py` is the authoring tool.
BL17 is proved by tests that ingest a plan twice rather than by a static board.

---

## What's Left

1. **Phase 2 — `heirs_ancients` adoption: DONE**, merged to their `main` and
   pushed (`43d52b2`). Board config, column tree, AGENTS.md protocol, MCP
   registration, and the `kahnban lint` gate in `tools/run_all_tests.ps1`. The
   gate passes, and DI-06 is green (37/37): five stale AGENTS.md counts that
   predated the board were found, attributed to upstream merge `256db1d` by
   running the suite with no board present, and corrected in `b78e84b`.
2. **Phase 3 — backlog migration: DONE**, pushed (`e80e2f9`). Programs B, E,
   and F were reconciled against the code by hand — Program B fully closed
   (20/20 spot-checked), Programs E/F overwhelmingly resolved. Nine genuinely
   open items ingested as HOA-001..HOA-009 in one commit; the source plan
   archived and marked SUPERSEDED. This surfaced a real ingest gap — no label
   set `blocked_on`, worked around there by hand-editing one ticket's
   frontmatter — **fixed upstream in 1.1.2**, see below.
3. **Phase 4 — `citadel` portability smoke test.**
4. **CI matrix (§8):** Windows + Linux, Python 3.10 and 3.12. Only Windows has
   been exercised so far.

### Deliberate deviations and known rough edges

- **`blocked_on` is now an ingestible field (1.1.2).** `Blocked on:` /
  `## Blocked on` / `blocker` / `on hold` / `waiting on` set it directly,
  deliberately kept distinct from `depends_on`'s `blocked by` (a ticket
  reference, resolved to an ID) since a blocking *reason* usually isn't itself
  a ticket. An unresolvable `depends_on` reference now combines with an
  explicit `blocked_on` (joined with `|`) instead of overwriting it — found
  because the two paths wrote the same field with no coordination between them.
- `core.py` (1,754 lines) carries the helpers the linter shares plus every gate
  and the draft renderer. If it grows again, split the gates into `gates.py`.
- **A `kahnban new` ticket now has empty body sections** rather than the
  template's example text. This was a deliberate fix: the example checkbox and
  example path were enough to satisfy the refinement gate, which meant a ticket
  nobody had specified could reach `2-ready`. Guidance still lives in
  `plans/tickets/template.md`.
- Ingest parsing is heuristic. It is accurate on plans written in the documented
  shape and honest elsewhere — it reports what it could not interpret instead of
  inventing paths or criteria. A *specification* document (like this repo's own
  `plan.md`) yields prose-only tickets that the gate correctly refuses; scope
  with `--section` or write the plan in the documented shape.
- Report rendering is downgraded to the console's encoding (`console_safe`),
  because plan documents contain emoji and typographic dashes that crash a
  cp1252 console. Ticket files always keep the original UTF-8.
- `board.config.json` is not schema-validated beyond the keys the engine reads,
  except `ingest.section_aliases`, which rejects unknown field names.

---

## Decision Log & Constraints

See [plan.md](plan.md) §0 (D1–D9) and §2.6 for the entry-point layer. The
constraints that shaped this code:

- **D2:** board transitions commit to the default branch, never ticket branches.
- **D4:** `verify` runs the tests itself; pasted evidence only for
  `validation_class: visual-deferred`, logged as `MANUAL-EVIDENCE (unverified)`.
- **D7 / BL16:** blast radius is the isolation contract, enforced at claim,
  verify, and lint.
- **D8:** `STATUS.md` and `status.json` are regenerated projections.
- **§2.6:** ingestion never fabricates readiness and never duplicates on
  re-ingest; the gate decides what is ready, not the source document.
