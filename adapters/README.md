# Adapters — Adopting Kahnban & The Software Factory Workflow

Layer 1 (this engine) is installed once per machine. Layer 0 (the board) and
Layer 2 (client configs and agent guidelines) are committed per repository. Nothing in this directory
is engine code — these are the files, templates, and skills you copy or scaffold into an adopter repo.

---

## 1. Install the Engine

```powershell
py -3 -m pip install -e C:\github\kahnban          # local development, editable
py -3 -m pip install git+https://<remote>/Kahnban  # pinned by tag in CI
```

Adopter repositories contain **no copied engine code**. `board.config.json`
carries `engine_min_version`; every entry point refuses to run against an older
engine and prints the upgrade command.

---

## 2. Scaffold the Board & Agentic Harness

You can scaffold the classic board or the full **Agentic Software Factory**:

### Option A: Complete Agentic Software Factory (Recommended)

```powershell
cd C:\github\<adopter>
kahnban init --prefix HOA --agentic
```

This scaffolds:
1. **The Board Contract:** `plans/board.config.json`, the column tree (`0-backlog` through `5-done`), and projections (`plans/STATUS.md`, `plans/status.json`, and `plans/board.json`).
2. **The Universal Agent Harness:** `.agents/AGENTS.md` and `.agents/state/ACTIVE_SESSION.md`.
3. **Specifications & Templates:** `.agents/specs/` and `.agents/templates/` (`spec-template.md`, `ticket-template.md`, `active-session-template.md`, `glossary-template.md`, `adr-template.md`).
4. **Domain & Decision Roots:** Root `GLOSSARY.md` and `ADR/0001-record-architecture-decisions.md`.
5. **Git Isolation:** `.gitignore` configured for `.worktrees/`, `.claim.lock`, and artifacts.

### Option B: Core Kanban Board Only

```powershell
cd C:\github\<adopter>
kahnban init --prefix HOA
```

---

## 3. The 5-Stage Gated Lifecycle & Matt Pocock Skills

This workflow integrates Matt Pocock's engineering skills located in `adapters/skills/`:

| Stage | Column | Skill | Purpose |
| :---: | :--- | :--- | :--- |
| **1** | `0-backlog` | `/grill-with-docs` | Socratic intake interrogation, domain alignment (`GLOSSARY.md`), decisions (`ADR/`). |
| **2** | `1-refining` $\rightarrow$ `2-ready` | `/to-spec`, `/to-tickets` | Formal specification in `.agents/specs/`, decomposition into 1–3 file tickets, `kahnban ready` machine gate. |
| **3** | `3-in-progress` | `/tdd` | Claim with worktree isolation (`kahnban claim --worktree`), Red-Green-Refactor test loops. |
| **4** | `4-verifying` | `/code-review` | Diff vs. blast radius containment audit, acceptance criteria verification, machine test run (`kahnban verify`). |
| **5** | `5-done` | PR Merge | Integration to `main`, `kahnban done`, and worktree pruning (`kahnban cleanup`). |

To make these skills active in your harness, copy or symlink `adapters/skills/*` into your agent configuration directory (e.g. `.claude/skills/`, `.gemini/config/skills/`, or project prompts).

---

## 4. Single Source of Truth & Cross-Harness Continuity

- **Programmatic Board Registry (`board.json`):** Automatically projected on every sync alongside `STATUS.md`. Enriched with ticket descriptions, dependencies (`depends_on`), blockers (`blocked_on`), and blast radii (`blast_radius`) for sub-agent orchestration. If your repository maintains a root `.kanban/` folder, `board.json` is automatically mirrored there as well.
- **Flight Recorder (`ACTIVE_SESSION.md`):** Keeps live context, active worktrees, modified files, blockers, and next shell commands synchronized across AI harnesses:
  ```powershell
  kahnban session                                # inspect current session state
  kahnban session --flush --ticket HOA-001       # flush live worktree status
  kahnban handoff --note "context for next model" # convenient flush alias for harness transitions
  ```

---

## 5. Gate the Test Runner on Board Lint

Insert at the top of your test runner (e.g. `tools/run_all_tests.ps1`) or CI workflow:

```powershell
Write-Host "=== Validating Kahnban Board ===" -ForegroundColor Cyan
& py -3 -m kahnban lint --config plans\board.config.json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Kanban board lint failed. Resolve violations before running test suites."
    exit 1
}
```

Lint exit codes: `0` clean, `1` violations, `2` configuration or I/O error.
