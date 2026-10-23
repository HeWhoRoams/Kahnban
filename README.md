# Kahnban — Portable Agentic Kanban Workflow Engine & Software Factory

**Status:** Engine `1.3.0` — Full agentic Kanban pipeline, dual-tier QA gates, autonomous stage dispatcher (`kahnban next`), and multi-harness relay protocol. 296 tests passing.

Kahnban is a zero-dependency, model-agnostic Kanban system and software factory conductor for AI coding workflows. It provides machine-enforced gates, strict transparency into in-flight agent tasks, prevents workspace collisions across concurrent LLM sessions, and maintains a single source of truth backed by Git storage.

## Quick Start

```powershell
py -3 -m pip install -e .        # install the engine (editable)
py -3 -m pytest -q               # 296 tests (drives real git repos, ~5 min)
kahnban --version
```

Adopt it in a repository with agentic scaffolding and skills:

```powershell
cd C:\github\<your-repo>
kahnban init --prefix KB --agentic    # scaffolds board, .agents/, and ./learnings/
kahnban skills install                # distributes skills to detected harnesses (.claude, .gemini, .cursor, .vscode, .hermes)
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
kahnban ready KB-001                     # gates requirements, acceptance checkboxes, blast radius
kahnban next                             # situational dispatcher: prints exact role, worktree, prompt

kahnban claim KB-001 --owner agent-a --worktree
# ... execute in isolated worktree .worktrees\KB-001 on branch ticket/KB-001 ...

kahnban verify KB-001                    # executes Dual-Tier QA: Tier 1 Feature Tests && Tier 2 Regression Tests
kahnban approve KB-001 --reviewer qa-b   # a reviewer other than the owner signs off the verified tip
# or: kahnban reject KB-001 --reviewer qa-b -m "..."   (back to in-progress, boxes unticked)
kahnban merge KB-001                     # merge queue: test main+branch, land only if green

kahnban done KB-001                      # marks done and triggers learnings reflection prompt
# ... capture friction or mistakes into self-improving queue ...
kahnban learnings capture --title "Race condition in cache" --ticket KB-001 --location "cache.py:42"
kahnban cleanup KB-001                   # prunes worktree & local ticket branch
```

`kahnban lint` exits 0 clean, 1 on violations, 2 on a config or I/O error — wire it into your CI or pre-commit hook as a gate.

---

## Autonomous Factory Mode (`/factory-mode`) & `kahnban next`

For autonomous agents operating across **Claude Code**, **ChatGPT**, **Antigravity**, **VSCode**, and **Hermes**, Kahnban provides situational dispatching:

```powershell
kahnban next            # human-readable briefing with exact commands & prompts
kahnban next --json     # machine-readable HandoffBaton for autonomous subagents
```

When invoked, the agent systematically drives work through 5 strict stages:
1. **Intake & Refinement**: `/grill-with-docs` $\rightarrow$ `/to-spec` $\rightarrow$ `/to-tickets` $\rightarrow$ `kahnban ready` $\rightarrow$ triggers `post-ready` hook
2. **Claim & Worktree Isolation**: `kahnban claim <ID> --worktree` $\rightarrow$ emits `.agents/HANDOFF.json` into worktree $\rightarrow$ triggers `post-claim` hook
3. **Execution Rigor**: Coder Agent reads `HANDOFF.json`, adheres strictly to declared blast radius, and applies PSTACK principles + `/tdd`
4. **Dual-Tier QA & Verification**:
   - **Tier 1 (Feature Tests)**, then each acceptance criterion's own test, then **Tier 2 (Regression Tests)**.
   - With `require_proof`, the feature tests are re-run against the base version of the changed source and must fail there.
   - `kahnban verify <ID>` moves to `4-verifying` only if all of that holds, and ticks only the boxes whose test passed.
5. **Review Gate & Closure**:
   - QA Reviewer Agent audits tests and diff. If defective: `kahnban reject <ID> --reviewer <name> -m "..."` moves it back to `3-in-progress` with the reasons in its Log.
   - If sound: `kahnban approve <ID> --reviewer <name>` (never the owner) $\rightarrow$ integrator runs `kahnban merge <ID>` $\rightarrow$ `kahnban done` $\rightarrow$ triggers `post-done` hook $\rightarrow$ `/reflect` $\rightarrow$ `kahnban cleanup`

---

## Dual-Tier QA Testing Syntax

Tickets can declare separate feature and regression test commands in `## Validation`:

```markdown
## Validation
### Feature Tests
```bash
pytest tests/features/test_token_revocation.py -v
```

### Regression Tests
```bash
pytest tests/ -q
```
```

If the regression block is omitted, Kahnban automatically falls back to `validation_command` / `regression_command` in `plans/board.config.json`.

Each line of a block is one command, run on its own; the first non-zero exit fails the block (a trailing `\` or backtick continues a line). Shell state such as `cd` does not carry between lines.

Each acceptance criterion names the test that proves it, and `verify` ticks the box only when that test exits 0:

```markdown
## Acceptance criteria
- [ ] Revoked tokens are rejected (test: `pytest tests/features/test_token_revocation.py::test_rejects_revoked`)
- [ ] Error copy matches the design
```

A criterion without a test is left for a reviewer to tick. Under `require_proof` the ready gate refuses one unless the ticket is `validation_class: visual-deferred`.

### What `verify` refuses

| Gate | Refuses when |
| :--- | :--- |
| Frozen contract | `## Acceptance criteria`, `## Blast radius` or `## Validation` changed after `ready` (stored as `contract_hash`; ticking boxes does not count) |
| Clean tip | the worktree has uncommitted or untracked changes, or is not at the tip of `ticket/<ID>` |
| Scope | the branch changes any path outside `## Blast radius`, tests and `.github/` included |
| Fail fast | any line of a validation block, or any criterion test, exits non-zero |
| Proof (`require_proof`) | the branch changes no source files, a criterion names no test, or the feature tests still pass with the source reverted to the merge-base |

### What `approve`, `merge` and `done` refuse

| Gate | Refuses when |
| :--- | :--- |
| Review (`require_review`) | `approve` by the ticket's owner, or after the branch moved since verify; `merge` and `done` without an approval of the current branch tip |
| Rejection | `reject` always moves the ticket back to `3-in-progress`, unticks every box, and clears the verify, approval and integration records |
| Merge queue (`require_integration`) | `merge` lands nothing if the branch conflicts with the default branch, or if the feature or regression tests fail on the merged result; `done` refuses a ticket that did not land through `kahnban merge` |

`merge` holds the board lock while its tests run, so merges happen one at a time and each is tested against everything merged before it. A fresh `verify` clears any earlier approval.

`kahnban init` writes `"require_proof"`, `"require_review"` and `"require_integration"` as `true`; boards without those keys keep the old behaviour. Files matching `test_patterns` (defaults: `tests/`, `test_*`, `*_test.*`, `*.spec.*`, …) count as tests, everything else as source.

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

- **[adapters/AGENTS.md](adapters/AGENTS.md)** — universal agent working agreement to copy into adopter repos
- **[adapters/README.md](adapters/README.md)** — adopting Kahnban in an existing repository
- **[adapters/MCP.md](adapters/MCP.md)** — MCP client registration per IDE (Cursor, Claude, VS Code, Hermes)
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
5. **Proven Verification** — `kahnban verify` runs the committed tip's feature, criterion and regression tests line by line, and under `require_proof` shows the feature tests fail without the change (Rule D4).
6. **Domain Isolation** — claim-time blast-radius overlap refusal plus verify-time diff containment prevent merge conflicts (Rules D7, BL16).
7. **Pattern-Aggregating Feedback** — friction and mistakes are captured into `./learnings/`, clustered into recurrence records, and promoted into structural defenses.
8. **Relay Baton Handoffs** — transitions emit `.agents/HANDOFF.json` and invoke lifecycle hooks (`post-ready`, `post-claim`, `post-verify`, `post-done`) for autonomous cross-agent dispatch.

---

## Implementation Snapshot

| Component | Status | Tests | Lines |
| :--- | :---: | ---: | ---: |
| frontmatter | done | 10 | 196 |
| gitops | done | 9 | 215 |
| core | done | 61 | 2,023 |
| ingest | done | 48 | 1,013 |
| linter | done | 32 | 476 |
| status | done | 8 | 239 |
| worktree | done | 13 | 191 |
| mcp_server | done | 26 | 846 |
| cli | done | 36 | 827 |
| learnings | done | 4 | 472 |
| skills | done | 6 | 360 |
| hooks | done | 3 | 142 |
| handoff | done | 2 | 255 |
| dispatcher | done | 3 | 184 |
| lifecycle (e2e) | done | 2 | — |

**Total:** 296 tests passing; ~7,439 lines of engine code, zero runtime dependencies.
