# Kahnban Implementation Status

**Date:** 2026-08-18
**Current Phase:** Phase 1 (Engine Implementation) — code complete
**Status:** All 176 tests passing; engine version `1.0.0`; only the `v1.0.0` git tag remains

---

## What's Implemented

| Module | Lines | Tests | Notes |
| :--- | ---: | ---: | :--- |
| `frontmatter.py` | 195 | 7 | Parse/serialize/mutate/append_log over the documented YAML subset |
| `gitops.py` | 204 | 9 | List-form subprocess wrappers; every failure raises `GitError` with stderr |
| `core.py` | 1,526 | 61 | Config, lookup, ID allocation, board lock, `transition()`, all gates |
| `linter.py` | 422 | 32 | BL01–BL16, ASCII output, `--json`, exemptions |
| `status.py` | 149 | 8 | STATUS.md + status.json projections |
| `worktree.py` | 193 | 13 | Worktree provisioning, NTFS junctions, junction-safe teardown |
| `mcp_server.py` | 520 | 24 | Stdio JSON-RPC 2.0, 10 tools, protocol conformance |
| `cli.py` | 323 | 17 | 11 subcommands, exit codes 0/1/2 |
| lifecycle (e2e) | — | 2 | init → new → ready → claim → verify → done → cleanup |

Run the suite with `py -3 -m pytest -q` (~3 minutes; it drives real git repos).

### Engine surface

```
kahnban new <title> [--problem TEXT | --problem-file FILE] [--owner NAME]
kahnban ready <ID>
kahnban claim <ID> --owner NAME [--worktree|--no-worktree] [--force]
                   [--force-overlap] [--strict-wip] [--reason TEXT]
kahnban verify <ID> [--manual-evidence FILE] [--force-scope] [--reason TEXT]
kahnban done <ID> [--merge-commit SHA]
kahnban move <ID> <column> --reason TEXT
kahnban cleanup <ID> [--abandon] [--reason TEXT]
kahnban lint [--json] [--strict]
kahnban sync | kahnban status
kahnban init --prefix PREFIX [--wip-limit N] [--validation-command CMD] [--no-worktrees]
```

MCP tools: `kanban_board_status`, `kanban_ticket_get`, `kanban_ticket_new`,
`kanban_ticket_ready`, `kanban_ticket_claim`, `kanban_ticket_verify`,
`kanban_ticket_done`, `kanban_ticket_move`, `kanban_cleanup`, `kanban_sync`.

### How the invariants are enforced

- **Folders are the only status (Principle 1).** `transition()` is the single
  writer: mutate frontmatter → append `## Log` → `git mv` → regenerate both
  projections → one commit containing all of it.
- **Board plane on the default branch (D2).** `transition()` refuses to run when
  a non-default branch is checked out, and `load_config` hops from a linked
  worktree to the main worktree so an agent working inside `.worktrees/<ID>`
  still writes board state in the right place.
- **Machine verification (D4).** `verify` executes the ticket's fenced
  `## Validation` command with the configured timeout, writes full output to
  `plans/tickets/.artifacts/<ID>-<timestamp>.log`, records a head+tail truncated
  copy in `## Log`, and only advances on exit code 0. Failed attempts are
  committed too — the audit trail keeps them. Captured output is indented four
  spaces so no line can forge a markdown heading.
- **Domain isolation (D7).** Claim refuses on blast-radius overlap with any
  in-progress ticket; verify refuses when `git diff --name-only` on the ticket
  branch touches undeclared paths. Both overrides demand `--reason` and log it.
- **Concurrency (§3.3).** `plans/tickets/.claim.lock` (`O_CREAT|O_EXCL`, PID +
  timestamp, 5-minute staleness break) covers gate-check through commit. Across
  clones, the default-branch push arbitrates: a rejected push rolls back exactly
  the commit just created, tears down the worktree, and retries once after
  `pull --ff-only`.
- **Long text never on argv (§4.2).** `--problem-file` (with `-` for stdin) and
  `--manual-evidence FILE`; MCP passes evidence by path.

### Lint fixtures

`tests/fixtures/` holds 18 boards: `clean-board/`, `clean-board-crlf/`, and
`violations/BL01 … BL16/`. `tests/fixtures/generate.py` is the authoring tool —
run it to regenerate after a rule change. Git-dependent rules (BL15) get their
repository state built in the test that uses the fixture.

---

## What's Left

1. **`v1.0.0` git tag** — the work is uncommitted in the working tree; tagging
   and committing are the repository owner's call.
2. **Phase 2 — `heirs_ancients` adoption:** `pip install -e C:\Github\Kahnban`,
   `kahnban init --prefix HOA`, apply the §6.1 config (WIP limit 3,
   `shared_caches: [".godot"]`, the two extension fields), copy
   `adapters/AGENTS.md` into `AGENTS.md`/`CLAUDE.md`/`.cursorrules`, register the
   MCP server from `adapters/MCP.md`, and add the lint gate to
   `tools/run_all_tests.ps1` (§6.2) keeping DI-06 green.
3. **Phase 3 — backlog migration:** generate 25–40 tickets with `kahnban new`,
   archive `plans/IMPLEMENTATION_PLAN.md` as superseded, fix inbound references.
4. **Phase 4 — `citadel` portability smoke test:** `kahnban init --prefix CIT`,
   run one ticket through the full lifecycle; acceptance is zero engine changes.
5. **CI matrix (§8):** GitHub Actions on `windows-latest` + `ubuntu-latest`,
   Python 3.10 and 3.12. The suite is platform-agnostic (junction assertions are
   `skipif(os.name != "nt")`) but has only been run on Windows so far.

### Deliberate deviations from the plan's estimates

- `core.py` is 1,526 lines rather than the estimated ~200: it carries the board
  helpers the linter shares (`section`, `checkboxes`, `parse_blast_radius`,
  `extension_problems`) so `linter.py` can depend on `core` without a cycle,
  plus every gate body.
- A `status` subcommand was added (counts + lint summary) because agents ask for
  a board overview constantly and it costs nothing.
- `verify` runs the validation command through a shell, as §4.8 requires for the
  documented PowerShell wrapper form. The command comes from the ticket or
  `board.config.json`, never from CLI input.

---

## Decision Log & Constraints

See [plan.md](plan.md) §0 (D1–D9). The constraints that shaped this code:

- **D2:** board transitions commit to the default branch, never ticket branches.
- **D4:** `verify` runs the tests itself; pasted evidence is only accepted for
  `validation_class: visual-deferred`, and the Log entry is marked
  `MANUAL-EVIDENCE (unverified)`.
- **D7 / BL16:** blast radius doubles as the isolation contract, enforced at
  claim time, verify time, and by lint afterwards.
- **D8:** `STATUS.md` and `status.json` are regenerated projections; the folders
  stay the ground truth.
