# Agent Working Agreement & Universal SSOT Protocol

Copy this file into the adopter repository's `AGENTS.md`, `CLAUDE.md`, and `.cursorrules`. It is the binding contract every AI agent and human engineer follows when interacting with this codebase across any model harness (Claude Code, ChatGPT, Antigravity, Cursor).

---

## 1. Startup & Resume Protocol (SSOT)

Before performing ANY action or writing ANY code, you MUST:
1. **Read `board.json`** (or `plans/board.json` / `plans/STATUS.md`): Verify active ticket columns, in-flight work, WIP limits, and dependencies.
2. **Read `.agents/state/ACTIVE_SESSION.md`**: Verify in-flight sub-agent tasks, currently modified files, known blockers, and immediate next commands.
3. **Verify Git & Worktree Status**:
   - Check `git status` and active worktrees (`.worktrees/`).
   - If resuming work on a claimed ticket, ensure you are operating INSIDE that ticket's isolated worktree (`.worktrees/<TICKET-ID>`).
4. **Master Conductor**:
   - For end-to-end autonomous ticket execution, invoke `/factory-mode`.

---

## 2. The 5-Stage Gated Kanban Engineering Lifecycle

All work items must move strictly through these sequential stages:

```
[1. Intake]         -->  [2. Architecture]   -->  [3. Development]  -->  [4. Validation]    -->  [5. Closure & Learning]
0-backlog                1-refining/2-ready       3-in-progress          4-verifying             5-done
/grill-with-docs         /to-spec, /to-tickets    /tdd in worktree       /code-review & verify   PR merge, done & /reflect
```

### Stage 1: Clarification & Enrichment (Intake)
- **Column:** `0-backlog`
- **Skill:** `/grill-with-docs`
- **Rule:** No raw user prompt or feature request may bypass intake. Interrogate intent, clarify jargon in `GLOSSARY.md`, log structural choices in `ADR/`, and capture the ticket using `kahnban capture` or `kahnban new`.

### Stage 2: Refinement & Architecture
- **Columns:** `1-refining` -> `2-ready`
- **Skills:** `/to-spec` -> `/to-tickets`
- **Rule:** Synthesize a formal specification in `.agents/specs/` with explicit type contracts. Decompose the spec into atomic tracer-bullet tickets touching 1-3 files max.
- **Machine Gate:** Run `kahnban ready <ID>` to validate required headings, non-empty blast radius, testable acceptance criteria, and valid dependencies before claiming.

### Stage 3: In Development
- **Column:** `3-in-progress`
- **Skills:** `/tdd`, PSTACK principles (`subtract-before-you-add`, `laziness-protocol`, `boundary-discipline`)
- **Rule:** Always claim before coding:
  ```bash
  kahnban claim <TICKET-ID> --owner <agent-id> --worktree
  ```
  The tool refuses if `## Blast radius` overlaps with any in-flight ticket (Rule BL16).
- All code changes, edits, and test runs execute inside `.worktrees/<TICKET-ID>` on branch `ticket/<TICKET-ID>`. Never edit the main checkout while a ticket is claimed, and never commit board state on a ticket branch.
- Drive implementation strictly using Red-Green-Refactor test loops.

### Stage 4: Testing, Hygiene & Validation
- **Column:** `4-verifying`
- **Skills:** `/unslop`, `/no-comments`, `/code-review` -> `kahnban verify`
- **Rule:** Perform hygiene cleanups and pre-verification review auditing git diff against declared `## Blast radius`.
- Run machine verification:
  ```bash
  kahnban verify <TICKET-ID>
  ```
  Kahnban executes the fenced `## Validation` command in a clean subprocess. Acceptance checkboxes are only ticked by the engine on exit code 0.

### Stage 5: In Production & Continuous Learning
- **Column:** `5-done`
- **Rule:**
  1. Return to project root (`cd <project-root>`). Never merge from within `.worktrees/`.
  2. Merge `ticket/<TICKET-ID>` into the default branch (`main`).
  3. Finalize: `kahnban done <TICKET-ID>`.
  4. Run `/reflect` to log friction, mistakes, or environmental traps to `./learnings/`.
  5. Clean up: `kahnban cleanup <TICKET-ID>`.

---

## 3. Continuous Learning Subsystem (`./learnings/`)

To prevent recurrence of mistakes and institutionalize knowledge, the workspace maintains a pattern-aggregating feedback queue in `./learnings/`:
- **Capture Friction**: Run `kahnban learnings capture --title "<pattern>" --problem "<desc>" --ticket <ID>`. If a similar issue was previously recorded, Kahnban clusters the occurrence, increments `occurrences`, escalates `severity`, and logs file locations without creating duplicate files.
- **Escalation Ladder**:
  - Level 1 — Architecture: Make the mistake physically impossible (boundaries, deprecations, SSOT).
  - Level 2 — Linters & Types: Static analysis, type invariants, or AST rules rejecting the pattern.
  - Level 3 — Automated Tests: Regression test fixtures in `tests/` asserting the correct behavior.
  - Level 4 — Documentation & Rules: Update `AGENTS.md` / rules when static barriers are impossible.
- **Drain & Institutionalize**: Run `/harvest-learnings` periodically to review accumulated learnings, promote resolved items to `learnings/archive/`, and encode safeguards into structural code or tests.

---

## 4. Sub-Agent Orchestration & Isolated Worktrees

When spawning parallel sub-agents for concurrent tasks:
1. **Safety Scan:** Verify `candidate.blast_radius` shares no files or directories with any ticket currently in `3-in-progress`.
2. **Worktree Isolation:** Dispatch each sub-agent into its dedicated worktree (`.worktrees/<TICKET-ID>`).
3. **Synchronization:** Update `ACTIVE_SESSION.md` with active sub-agent assignments so parallel work remains visible.
4. **Integration:** Verify and merge sub-agent branches sequentially into `main`.

---

## 5. Cross-Harness Hand-Off Protocol (Claude <-> ChatGPT <-> Antigravity <-> Cursor)

When switching AI harnesses or running low on context/credits:
1. **Flush State:**
   ```bash
   kahnban session --flush --ticket <TICKET-ID> --note "Summary of current progress" --next-cmd "pytest tests/..."
   ```
2. **Commit Worktree:** Commit in-progress code to branch `ticket/<TICKET-ID>`.
3. **Resume Prompt in New Harness:**
   > *"Read `.agents/state/ACTIVE_SESSION.md` and `board.json`. Acknowledge current state and resume work on <TICKET-ID> inside its worktree."*

---

## 6. Command Quick Reference

```powershell
kahnban lint                                   # board rules BL01-BL17
kahnban status                                 # counts + lint summary
kahnban session                                # inspect cross-harness state
kahnban session --flush --ticket <ID>          # update ACTIVE_SESSION.md
kahnban capture "<idea>" ["<idea>" ...]        # ideation -> backlog, one commit
kahnban ingest <spec.md> [--dry-run] [--ready] # spec -> backlog/ready, idempotent
kahnban new "<title>" --problem-file spec.txt  # single ticket creation
kahnban ready <ID>                             # refinement gate -> 2-ready
kahnban claim <ID> --owner <name> --worktree   # claim & spawn isolated worktree
kahnban verify <ID>                            # execute validation command -> 4-verifying
kahnban done <ID> [--merge-commit <sha>]       # production gate -> 5-done + learnings advisory
kahnban cleanup <ID>                           # prune worktree & local branch
kahnban learnings list                         # view active learning records
kahnban learnings capture --title "<t>"        # cluster/log pattern in ./learnings/
kahnban learnings promote <id> --level 1..4    # graduate learning to archive
kahnban move <ID> <column> --reason "<why>"    # escape hatch; always logged
```
