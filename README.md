# Kahnban — Portable Agentic Kanban Workflow Engine

**Status:** Engine `1.1.0` — v1.0.0 pipeline plus the entry-point layer, 241 tests passing

Kahnban is a zero-dependency, model-agnostic Kanban system for AI vibe-coding
workflows. It provides machine-enforced gates, strict transparency into in-flight
agent tasks, prevents workspace collisions across concurrent LLM sessions, and
maintains a single source of truth backed by Git storage.

## Quick Start

```powershell
py -3 -m pip install -e .        # install the engine (editable)
py -3 -m pytest -q               # 241 tests (drives real git repos, ~5 min)
kahnban --version
```

Adopt it in a repository:

```powershell
cd C:\github\<adopter>
kahnban init --prefix HOA
```

Get work onto the board from whatever you have:

```powershell
kahnban capture "Try a warm cache"              # ideation
kahnban ingest plans/PLAN.md --dry-run          # preview an AI-generated plan
kahnban ingest plans/PLAN.md --ready            # ingest it, then attempt the gate
kahnban ingest --per-file specs/*.md            # one ticket per feature spec
kahnban new "Add the targeting panel" --problem-file spec.txt
```

Then run a ticket through the pipeline:

```powershell
kahnban ready HOA-001
kahnban claim HOA-001 --owner agent-a --worktree
# ... work inside .worktrees\HOA-001 on branch ticket/HOA-001 ...
kahnban verify HOA-001                    # runs the ticket's validation command
# ... human review, merge ticket/HOA-001 into main ...
kahnban done HOA-001
kahnban cleanup HOA-001
```

`kahnban lint` exits 0 clean, 1 on violations, 2 on a config or I/O error — wire
it into the test runner as a gate.

### Documentation

- **[plan.md](plan.md)** — complete specification (architecture, contracts, roadmap)
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** — what exists, how the
  invariants are enforced, what remains
- **[adapters/README.md](adapters/README.md)** — adopting Kahnban in a repository
- **[adapters/AGENTS.md](adapters/AGENTS.md)** — the agent working agreement to copy
- **[adapters/MCP.md](adapters/MCP.md)** — MCP client registration per IDE
- **[adapters/PLAN-INGESTION.md](adapters/PLAN-INGESTION.md)** — entry points:
  ideation, an AI-generated plan, or a feature spec

## Key Principles

0. **One Conduit, Many Entry Points** — ideation, an AI-generated plan
   document, a feature spec, or a single ticket all converge on the same drafts
   and the same gates; ingestion is idempotent and never fabricates readiness
1. **Folders Are Status** — columns are physical directories (`0-backlog` …
   `5-done`); board state commits to the default branch immediately
2. **Universal Client** — agents use MCP or the CLI; both call the same
   in-process core, so there is exactly one implementation of every transition
3. **Worktree Isolation** — code changes live in `.worktrees/<ID>` on
   `ticket/<ID>`; board state never lands on a ticket branch (D2)
4. **Enforced Gates** — the tooling refuses invalid transitions; refinement is
   enforced at `2-ready`
5. **Machine Verification** — `kahnban verify` executes the tests itself and
   blocks on a non-zero exit (D4)
6. **Domain Isolation** — claim-time blast-radius overlap refusal plus
   verify-time diff containment prevent merge conflicts (D7, BL16)

## Implementation Snapshot

| Component | Status | Tests | Lines |
| :--- | :---: | ---: | ---: |
| frontmatter | done | 10 | 195 |
| gitops | done | 9 | 204 |
| core | done | 61 | 1,754 |
| ingest | done | 48 | 988 |
| linter | done | 32 | 476 |
| status | done | 8 | 149 |
| worktree | done | 13 | 193 |
| mcp_server | done | 24 | 664 |
| cli | done | 34 | 437 |
| lifecycle (e2e) | done | 2 | — |

**Total:** 241 tests passing; ~5,070 lines of engine code, zero runtime
dependencies.

## Board Rules (BL01–BL17)

`kahnban lint` checks frontmatter validity, ID/filename agreement, ID
uniqueness across columns and archive, status/folder agreement, required
headings, acceptance-criteria discipline, ownership, dependency satisfaction,
extension-field rules, design-doc existence, the WIP limit, column tidiness,
branch recording, merge verification for done tickets, blast-radius
disjointness across in-progress tickets, and ingest-provenance uniqueness. Every rule has a negative fixture board
under `tests/fixtures/violations/`.

## Adopter Repos

- **heirs_ancients** (prefix `HOA`) — first adopter; config template in plan §6.1
- **citadel** (prefix `CIT`) — portability smoke test

## License & Attribution

Plan created 2026-08-18 by Tim Niles. Engine implemented against plan v4.
