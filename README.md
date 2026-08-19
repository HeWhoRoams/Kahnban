# Kahnban — Portable Agentic Kanban Workflow Engine

**Status:** Phase 1 complete — engine `1.0.0`, 176 tests passing

Kahnban is a zero-dependency, model-agnostic Kanban system for AI vibe-coding
workflows. It provides machine-enforced gates, strict transparency into in-flight
agent tasks, prevents workspace collisions across concurrent LLM sessions, and
maintains a single source of truth backed by Git storage.

## Quick Start

```powershell
py -3 -m pip install -e .        # install the engine (editable)
py -3 -m pytest -q               # 176 tests (drives real git repos, ~3 min)
kahnban --version
```

Adopt it in a repository:

```powershell
cd C:\github\<adopter>
kahnban init --prefix HOA
kahnban new "Add the targeting panel" --problem-file spec.txt
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

## Key Principles

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
| frontmatter | done | 7 | 195 |
| gitops | done | 9 | 204 |
| core | done | 61 | 1,526 |
| linter | done | 32 | 422 |
| status | done | 8 | 149 |
| worktree | done | 13 | 193 |
| mcp_server | done | 24 | 520 |
| cli | done | 17 | 323 |
| lifecycle (e2e) | done | 2 | — |

**Total:** 176 tests passing; ~3,530 lines of engine code, zero runtime
dependencies.

## Board Rules (BL01–BL16)

`kahnban lint` checks frontmatter validity, ID/filename agreement, ID
uniqueness across columns and archive, status/folder agreement, required
headings, acceptance-criteria discipline, ownership, dependency satisfaction,
extension-field rules, design-doc existence, the WIP limit, column tidiness,
branch recording, merge verification for done tickets, and blast-radius
disjointness across in-progress tickets. Every rule has a negative fixture board
under `tests/fixtures/violations/`.

## Adopter Repos

- **heirs_ancients** (prefix `HOA`) — first adopter; config template in plan §6.1
- **citadel** (prefix `CIT`) — portability smoke test

## License & Attribution

Plan created 2026-08-18 by Tim Niles. Engine implemented against plan v4.
