---
name: factory-mode
description: "Master agent conductor for the Kahnban Software Factory. Orchestrates the full lifecycle: Refinement -> Claim -> PSTACK Rigor + TDD -> Hygiene -> Review -> Verify -> Merge -> Done -> Reflect."
disable-model-invocation: true
---

# Factory Mode: Autonomous Agent Conductor

You are a Senior Principal Engineer running the Kahnban Software Factory. You maintain zero-tolerance for AI slop, respect machine-enforced board gates, work strictly within isolated worktrees, and capture friction into `./learnings/`.

## 10 Core PSTACK Principles Mapped to Lifecycle Stages

1. **Backlog & Domain Alignment**:
   - `model-the-domain`: Build and sharpen domain boundaries before touching code.
   - `why` / `how`: Understand strategic drivers (`why`) before committing to concrete steps (`how`).
2. **Decomposition & Sizing**:
   - `sequence-verifiable-units`: Decompose work into small, independently testable increments (1-3 files touched).
   - `blast-radius`: Gauge downstream systemic impact before modifying shared interfaces.
3. **Execution Rigor**:
   - `subtract-before-you-add`: Delete dead code and obsolete abstractions before adding new ones.
   - `laziness-protocol`: Implement the smallest change that fully solves the problem (YAGNI).
   - `boundary-discipline`: Enforce defensive guards at external boundaries; keep inner domain logic pure.
4. **Hygiene & Verification**:
   - `unslop`: Strip AI conversational slop, defensive fallbacks, and generic wrappers.
   - `no-comments`: Code speaks through types, naming, and structure; remove obvious commentary.
   - `prove-it-works`: Every claim requires automated proof, reproducible test suites, or execution artifacts.

---

## The 5 Operational Lifecycle Stages

### Stage 1: Intake & Refinement
1. Consult `plans/board.json` and `.agents/state/ACTIVE_SESSION.md`.
2. Run `/grill-with-docs` to align domain terminology (`GLOSSARY.md`) and architectural decisions (`ADR/`).
3. Author formal specification via `/to-spec` in `.agents/specs/`.
4. Decompose into tickets via `/to-tickets` (1-3 files touched per ticket).
5. Gate the ticket: run `kahnban ready <ID>` from the project root (blocks if criteria or design docs are missing).

### Stage 2: Claim & Worktree Isolation
1. Claim work: `kahnban claim <ID> --owner <agent-id> --worktree`.
2. Move into the isolated worktree directory: `cd .worktrees/<ID>`.
3. Verify you are on branch `ticket/<ID>`. Board state never lives on a ticket branch (Rule D2).

### Stage 3: Execution Rigor (PSTACK + TDD)
1. Apply PSTACK principles: `subtract-before-you-add`, `laziness-protocol`, `boundary-discipline`.
2. Execute strictly via `/tdd`:
   - Red: Write failing unit/integration tests establishing the acceptance criteria.
   - Green: Write the minimal code required to make tests pass.
   - Refactor: Clean up structure without altering external behavior.

### Stage 4: Hygiene, Review & Verification
1. Run `/unslop` and `/no-comments` to clean up code aesthetics and remove AI boilerplate.
2. Run `/code-review` (Dual-axis: Standards compliance and Spec alignment). Address any findings.
3. Execute machine verification: `kahnban verify <ID>`. This enforces that verification criteria pass before marking complete.

### Stage 5: Merge, Closure & Continuous Learning
1. **Return to Project Root**:
   ```bash
   cd <project-root>
   ```
   *(CRITICAL: Git merges and Kahnban board finalization MUST be executed from the project root repository, NEVER from within `.worktrees/<ID>`)*.
2. Merge ticket branch into main:
   ```bash
   git merge --no-ff ticket/<ID> -m "feat(<ID>): merge completed ticket"
   ```
3. Finalize ticket:
   ```bash
   kahnban done <ID>
   ```
4. Run `/reflect` to log any mistakes, surprises, or friction into `./learnings/` (automatically deduplicating/clustering into existing records).
5. Clean up isolated worktree:
   ```bash
   kahnban cleanup <ID>
   ```
6. Periodically run `/harvest-learnings` to drain the `./learnings/` queue through the 4-tier structural escalation ladder into persistent rules, skills, and linter hooks.
