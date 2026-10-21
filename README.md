# Kahnban — Portable Agentic Kanban Workflow Engine & Software Factory

**Status:** Engine `1.2.0` — Full agentic Kanban pipeline, PSTACK skills suite, and pattern-aggregating learning queue. 287 tests passing.

Kahnban is a zero-dependency, model-agnostic Kanban system and software factory conductor for AI coding workflows. It provides machine-enforced gates, strict transparency into in-flight agent tasks, prevents workspace collisions across concurrent LLM sessions, and maintains a single source of truth backed by Git storage.

## Quick Start

```powershell
py -3 -m pip install -e .        # install the engine (editable)
py -3 -m pytest -q               # 287 tests (drives real git repos, ~5 min)
kahnban --version
```

Adopt it in a repository with agentic scaffolding and skills:

```powershell
cd C:\github\<your-repo>
kahnban init --prefix KB --agentic    # scaffolds board, .agents/, and ./learnings/
kahnban skills install                # distributes skills to detected harnesses (.claude, .gemini, .cursor)
```

Get work onto the board from whatever you have:

```powershell
kahnban capture "Try a warm cache"              # ideation
kahnban ingest plans/PLAN.md --dry-run          # preview an AI-generated plan
kahnban ingest plans/PLAN.md --ready            # ingest it, then attempt the gate
kahnban ingest --per-file specs/*.md            # one ticket per feature spec
kahnban new "Add the targeting panel" --problem-file spec.txt
```

Run a ticket through the 5-stage lifecycle:

```powershell
kahnban ready KB-001
kahnban claim KB-001 --owner agent-a --worktree
# ... execute in isolated worktree .worktrees\KB-001 on branch ticket/KB-001 ...
kahnban verify KB-001                    # runs the ticket's validation command
# ... return to project root, review, merge ticket/KB-001 into main ...
kahnban done KB-001                      # marks done and triggers learnings reflection prompt
# ... capture friction or mistakes into self-improving queue ...
kahnban learnings capture --title "Race condition in cache" --ticket KB-001 --location "cache.py:42"
kahnban cleanup KB-001                   # prunes worktree & local ticket branch
```

`kahnban lint` exits 0 clean, 1 on violations, 2 on a config or I/O error — wire it into your CI or pre-commit hook as a gate.

---

## Autonomous Factory Mode (`/factory-mode`)

For autonomous agents operating across Claude Code, Gemini / Antigravity, Cursor, and Codex, Kahnban bundles a master lifecycle conductor: `/factory-mode`.

When invoked, the agent systematically drives work through 5 strict stages:
1. **Intake & Refinement**: `/grill-with-docs` $\rightarrow$ `/to-spec` $\rightarrow$ `/to-tickets` $\rightarrow$ `kahnban ready`
2. **Claim & Worktree Isolation**: `kahnban claim <ID> --worktree` $\rightarrow$ work inside `.worktrees/<ID>`
3. **Execution Rigor**: PSTACK principles (`subtract-before-you-add`, `laziness-protocol`, `boundary-discipline`) + `/tdd`
4. **Hygiene & Verification**: `/unslop` $\rightarrow$ `/no-comments` $\rightarrow$ `/code-review` $\rightarrow$ `kahnban verify <ID>`
5. **Closure & Learning**: Return to project root $\rightarrow$ `git merge` $\rightarrow$ `kahnban done` $\rightarrow$ `/reflect` $\rightarrow$ `kahnban cleanup`

---

## Continuous Learning Subsystem (`./learnings/`)

Kahnban incorporates a pattern-aggregating self-improvement queue based on continuous learning principles. Instead of logging one-off noise, it clusters environmental recurrences, escalates severity, and tracks affected file locations:

- **Capture & Cluster**:
  ```powershell
  kahnban learnings capture --title "Direct non-atomic file writes" --ticket KB-002 --location "status.py:45"
  ```
  If a matching pattern or file path already exists, Kahnban automatically augments occurrences (`occurrences: 2`), escalates severity, and appends the new occurrence row without creating duplicate files.
- **Inspect**:
  ```powershell
  kahnban learnings list                 # view pending patterns
  kahnban learnings show LRN-0001        # view detailed history and evidence table
  ```
- **Promote & Institutionalize**:
  Drain learnings into structural defenses via the 4-tier escalation ladder:
  - **Level 1 — Architecture**: Make the mistake physically impossible (boundaries, deprecations, SSOT).
  - **Level 2 — Linters & Types**: Static analysis, type invariants, or AST rules rejecting the pattern.
  - **Level 3 — Automated Tests**: Regression test fixtures in `tests/` asserting correct behavior.
  - **Level 4 — Documentation & Rules**: Update `AGENTS.md` / rules when static barriers are impossible.

  ```powershell
  kahnban learnings promote LRN-0001 --level 2 --notes "Added AST rule rejecting non-atomic writes"
  ```
  Promoted records are archived cleanly to `learnings/archive/`.

---

## Documentation

- **[adapters/AGENTS.md](adapters/AGENTS.md)** — the universal agent working agreement to copy into adopter repos
- **[adapters/README.md](adapters/README.md)** — adopting Kahnban in an existing repository
- **[adapters/MCP.md](adapters/MCP.md)** — MCP client registration per IDE (Cursor, Claude, VS Code)
- **[adapters/PLAN-INGESTION.md](adapters/PLAN-INGESTION.md)** — entry points: ideation, plan documents, or feature specs
- **[plan.md](plan.md)** — complete engine specification (architecture, contracts, roadmap)
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** — implementation details and invariant guarantees

---

## Key Principles

0. **One Conduit, Many Entry Points** — ideation, AI-generated plans, feature specs, or single tickets all converge on identical drafts and gates; ingestion is idempotent and never fabricates readiness.
1. **Folders Are Status** — columns are physical directories (`0-backlog` … `5-done`); board state commits to the default branch immediately.
2. **Universal Client** — agents use MCP or the CLI; both call the same in-process core, so there is exactly one implementation of every transition.
3. **Worktree Isolation** — code changes live in `.worktrees/<ID>` on `ticket/<ID>`; board state never lands on a ticket branch (Rule D2).
4. **Enforced Gates** — the tooling refuses invalid transitions; refinement is enforced at `2-ready`.
5. **Machine Verification** — `kahnban verify` executes the tests in a subprocess and blocks on a non-zero exit code (Rule D4).
6. **Domain Isolation** — claim-time blast-radius overlap refusal plus verify-time diff containment prevent merge conflicts (Rules D7, BL16).
7. **Pattern-Aggregating Feedback** — friction and mistakes are captured into `./learnings/`, clustered into recurrence records, and promoted into structural defenses.

---

## Implementation Snapshot

| Component | Status | Tests | Lines |
| :--- | :---: | ---: | ---: |
| frontmatter | done | 10 | 196 |
| gitops | done | 9 | 215 |
| core | done | 61 | 1,908 |
| ingest | done | 48 | 1,013 |
| linter | done | 32 | 476 |
| status | done | 8 | 239 |
| worktree | done | 13 | 191 |
| mcp_server | done | 24 | 787 |
| cli | done | 34 | 762 |
| learnings | done | 4 | 472 |
| skills | done | 6 | 328 |
| lifecycle (e2e) | done | 2 | — |

**Total:** 287 tests passing; ~6,587 lines of engine code, zero runtime dependencies.
