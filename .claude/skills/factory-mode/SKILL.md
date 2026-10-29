---
name: factory-mode
description: "Master agent conductor for the Kahnban Software Factory. Orchestrates the full lifecycle: Refinement -> Claim -> PSTACK Rigor + TDD -> Hygiene -> Review -> Verify -> Merge -> Done -> Reflect."
disable-model-invocation: true
---

# Factory Mode: Autonomous Agent Conductor

To run the factory unattended, use `kahnban run`: it drives this whole lifecycle itself, runs every gate, and starts the `kahnban-*` agents only for refinement, implementation and review. Use this skill when you are the conductor in an interactive session.

You are a Senior Principal Engineer running the Kahnban Software Factory. You maintain zero-tolerance for AI slop, respect machine-enforced board gates, work strictly within isolated worktrees, and capture friction into `./learnings/`.

## 10 Core PSTACK Principles Mapped to Lifecycle Stages

1. **Backlog & Domain Alignment**:
   - `/principle-model-the-domain`: Build and sharpen domain boundaries before touching code.
   - `/why` / `/how`: Understand strategic drivers (`why`) before committing to concrete steps (`how`).
2. **Decomposition & Sizing**:
   - `/principle-sequence-verifiable-units`: Decompose work into small, independently testable increments (1-3 files touched).
   - `/change-impact`: Gauge downstream systemic impact before modifying shared interfaces.
3. **Execution Rigor**:
   - `/principle-subtract-before-you-add`: Delete dead code and obsolete abstractions before adding new ones.
   - `/principle-laziness-protocol`: Implement the smallest change that fully solves the problem (YAGNI).
   - `/principle-boundary-discipline`: Enforce defensive guards at external boundaries; keep inner domain logic pure.
4. **Hygiene & Verification**:
   - `/unslop`: Strip AI conversational slop, defensive fallbacks, and generic wrappers.
   - `/no-comments`: Code speaks through types, naming, and structure; remove obvious commentary.
   - `/principle-prove-it-works`: Every claim requires automated proof, reproducible test suites, or execution artifacts.

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
1. Apply PSTACK principles: `/principle-subtract-before-you-add`, `/principle-laziness-protocol`, `/principle-boundary-discipline`.
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
2. Hand review to a different agent (`/qa-reviewer-agent`): it runs `kahnban approve <ID> --reviewer <its-id>` or `kahnban reject <ID> --reviewer <its-id> -m "..."`. You cannot approve your own ticket.
3. Land an approved ticket through the merge queue, never with `git merge`:
   ```bash
   kahnban merge <ID>
   ```
   It merges onto the current main in a scratch worktree, runs the tests on the result, and fast-forwards main only if they pass. On refusal, reject the ticket with the failure.
4. Finalize ticket:
   ```bash
   kahnban done <ID>
   ```
5. Run `/reflect` to log any mistakes, surprises, or friction into `./learnings/` (automatically deduplicating/clustering into existing records).
6. Clean up isolated worktree:
   ```bash
   kahnban cleanup <ID>
   ```
7. Periodically run `/harvest-learnings` to drain the `./learnings/` queue through the 4-tier structural escalation ladder into persistent rules, skills, and linter hooks.
