# Adapters — Adopting Kahnban & The Software Factory Workflow

Layer 1 (the Kahnban engine) is installed once per machine or CI environment. Layer 0 (the board contract) and Layer 2 (client configs, agent guidelines, and skills) are committed directly per repository. Adopter repositories contain **zero copied engine code**.

---

## 1. 2-Minute Quickstart for Existing Repositories

Adopting Kahnban in an existing repository takes under 2 minutes and is **100% non-destructive**:
- Leaves all existing application code, git history, and existing commits intact.
- Safely appends only `.worktrees/`, `.claim.lock`, and `.artifacts/` to your existing `.gitignore`.
- Creates a clean, isolated commit: `kanban: initialize board (<PREFIX>)`.

### Step A: Install the Engine (Machine-wide / CI)
```powershell
# Local development (editable):
py -3 -m pip install -e C:\github\kahnban

# Production / CI / Docker:
py -3 -m pip install git+https://github.com/org/kahnban.git@v1.1.2
```

### Step B: Initialize into Your Repository
```powershell
cd C:\github\your-existing-app
kahnban init --prefix APP --agentic
```

This immediately scaffolds:
1. **The Board Contract:** `plans/board.config.json`, the column directories (`0-backlog` through `5-done`), and SSOT projections (`plans/STATUS.md`, `plans/status.json`, and `plans/board.json`).
2. **The Universal Agent Harness:** `.agents/AGENTS.md` and live flight recorder `.agents/state/ACTIVE_SESSION.md`.
3. **Self-Contained Skill Suite:** `.agents/skills/` containing Matt Pocock's 5 core pipeline skills (`grill-with-docs`, `to-spec`, `to-tickets`, `tdd`, `code-review`).
4. **Specifications & Templates:** `.agents/specs/` and `.agents/templates/` (`spec-template.md`, `ticket-template.md`, `active-session-template.md`, `glossary-template.md`, `adr-template.md`).
5. **Domain & Decision Roots:** Root `GLOSSARY.md` and `ADR/0001-record-architecture-decisions.md`.
6. **Git Isolation:** `.gitignore` safely updated for `.worktrees/`, `.claim.lock`, and build artifacts.

### Step C: Configure Test Runner (30 seconds)
Open `plans/board.config.json` and set your validation command:
```json
{
  "id_prefix": "APP",
  "wip_limit": 3,
  "validation_command": "pytest" // or "npm test", "cargo test", "godot --headless"
}
```

---

## 2. Best Practices for Activating & Discovering Skills

The core 5 pipeline skills are automatically copied into `.agents/skills/` during `kahnban init --agentic`. Here is how different AI harnesses discover and activate them:

### A. Claude Code
- **Repository-local skills:** Claude Code automatically discovers skills placed in `.agents/skills/` or `.claude/skills/`.
  To symlink or mirror them into Claude's default folder:
  ```powershell
  New-Item -ItemType SymbolicLink -Path .claude\skills -Target .agents\skills
  ```
- **Official Plugin:** Matt Pocock maintains a packaged Claude plugin:
  ```bash
  claude plugins install mattpocock-skills
  ```

### B. Gemini CLI / Antigravity
- Project-level skills in `.agents/skills/` are indexed per project.
- Global skills live in `~/.gemini/config/skills/`. You can copy or link any skill into this directory for machine-wide availability across all repos:
  ```powershell
  Copy-Item -Recurse .agents\skills\* $HOME\.gemini\config\skills\
  ```

### C. Cursor & Codex / ChatGPT
- **Cursor:** Referenced in `.cursor/rules/kanban.mdc` or directly read from `.agents/AGENTS.md`.
- **Generic Agents:** The generated `.agents/AGENTS.md` contains strict procedural directives that instruct the incoming model to inspect `.agents/skills/<skill>/SKILL.md` before executing each corresponding stage.

---

## 3. Pulling Upstream Skills from Matt Pocock's Repo

Matt Pocock actively publishes open-source skills to [`github.com/mattpocock/skills`](https://github.com/mattpocock/skills) ("Skills for Real Engineers"). You can enrich your project with his full extended catalog (`/prototype`, `/domain-modeling`, `/codebase-design`, `/implement-spec`, `/diagnosing-bugs`, `/retro`, `/ask-matt`).

### Option 1: Via the `skills.sh` Package Manager (Recommended)
You can pull editable skill files directly into your repository using npx:
```bash
# Add entire collection into .agents/skills/ or .claude/skills/
npx skills@latest add mattpocock/skills
```

### Option 2: Pulling Specific Individual Skills
```bash
npx skills@latest add mattpocock/skills/domain-modeling
npx skills@latest add mattpocock/skills/codebase-design
npx skills@latest add mattpocock/skills/diagnosing-bugs
```

### Option 3: Git Sparse-Checkout (Air-Gapped / CI)
For locked enterprise networks or CI image baking:
```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/mattpocock/skills.git vendor/matt-skills
cd vendor/matt-skills
git sparse-checkout set skills
cp -r skills/* ../../.agents/skills/
```

---

## 4. The 5-Stage Gated Lifecycle & Matt Pocock Skills

| Stage | Column | Skill | Purpose & Machine Gate |
| :---: | :--- | :--- | :--- |
| **1** | `0-backlog` | `/grill-with-docs` | Socratic intake interrogation, domain alignment (`GLOSSARY.md`), decisions (`ADR/`). Verified by linter rule BL05. |
| **2** | `1-refining` $\rightarrow$ `2-ready` | `/to-spec`, `/to-tickets` | Formal specification in `.agents/specs/`, decomposition into 1–3 file tickets. Gate: `kahnban ready <ID>` verifies blast radius and design docs. |
| **3** | `3-in-progress` | `/tdd` | Claim with worktree isolation (`kahnban claim <ID> --worktree`), Red-Green-Refactor test loops in `.worktrees/<ID>`. |
| **4** | `4-verifying` | `/code-review` | Diff vs. blast radius containment audit, acceptance criteria verification. Gate: `kahnban verify <ID>` runs the fenced validation command in the worktree. |
| **5** | `5-done` | Approve + merge queue | `kahnban approve <ID> --reviewer <name>` (not the owner), then `kahnban merge <ID>` tests the merged result and lands it. Gate: `kahnban done <ID>` blocks until all `[x]` criteria are checked, the approved tip is what landed, and it came through the merge queue. Worktree is pruned via `kahnban cleanup <ID>`. |

---

## 5. Single Source of Truth & Cross-Harness Continuity

- **Programmatic Board Registry (`board.json`):** Automatically projected on every sync alongside `STATUS.md`. Enriched with ticket descriptions, dependencies (`depends_on`), blockers (`blocked_on`), and blast radii (`blast_radius`) for sub-agent orchestration. If your repository maintains a root `.kanban/` folder, `board.json` is automatically mirrored there as well.
- **Flight Recorder (`ACTIVE_SESSION.md`):** Keeps live context, active worktrees, modified files, blockers, and next shell commands synchronized across AI harnesses:
  ```powershell
  kahnban session                                # inspect current session state
  kahnban session --flush --ticket HOA-001       # flush live worktree status
  kahnban handoff --note "context for next model" # convenient flush alias for harness transitions
  ```

  **CLI Session Flags & Agent Overrides:**
  When agents operate in containerized or non-standard environments, auto-detection of branches and worktrees can be explicitly overridden:
  - `--flush`: Force resynchronization of dirty files and in-progress tickets from Git and board.
  - `--ticket <ID>`: Explicit active ticket ID override.
  - `--worktree <PATH>`: Active worktree directory path override.
  - `--branch <NAME>`: Active Git branch name override.
  - `--harness <NAME>`: Agent harness identifier (`claude-code`, `antigravity`, `chatgpt`, `cursor`).
  - `--status <STATUS>`: Session status (`idle`, `in_progress`, `review`, `blocked`).
  - `--note <TEXT>`: Context or hand-off progress note for incoming agents.
  - `--blocker <TEXT>`: Failing test trace or blocker description.
  - `--next-cmd <CMD>`: Immediate shell command queued for next model invocation.

  **MCP Tool Bridge:**
  Equivalent operations are exposed via MCP tools (`kanban_session_get`, `kanban_session_update`), supporting full spec parameter aliases (`ticket_id`/`active_ticket`, `summary`/`context`, `next_command`/`next_commands`).

---

## 6. Gate the Test Runner & CI on Board Lint

Insert at the top of your test runner (e.g. `tools/run_all_tests.ps1`), pre-commit hook, or CI workflow:

```powershell
Write-Host "=== Validating Kahnban Board ===" -ForegroundColor Cyan
& py -3 -m kahnban lint --config plans\board.config.json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Kanban board lint failed. Resolve violations before running test suites."
    exit 1
}
```

Lint exit codes: `0` clean, `1` violations, `2` configuration or I/O error.


---

## 7. The Self-Improving Learning Loop (`./learnings/`)

Kahnban incorporates the **Lauren Tan Pattern Aggregator Protocol**: session friction, repeated agent mistakes, and architectural surprises are captured into `./learnings/` instead of evaporating when worktrees are pruned.

### The Lauren Tan Clustering Invariant
> *"Never create duplicative one-off entries for recurring mistakes. Augment existing records with frequency counts, escalated severity, and systemic environmental diagnosis to fix the forest, not just the trees."*

- **Capture & Cluster:** Run `/reflect` at the end of a ticket or session. If a pattern matches an existing pending entry in `./learnings/`, it increments `occurrences`, updates severity, appends a row to the evidence table, and refines the systemic diagnosis.
- **Harvest & Escalate:** Periodically run `/harvest-learnings` to drain the queue. Patterns with >= 2 occurrences are structurally eliminated using the **4-Tier Escalation Ladder**:
  1. *Level 1 (Architecture):* Restructure boundaries or delete legacy paths so bad code cannot be written.
  2. *Level 2 (Linters & Types):* Add a lint or compiler rule naming the alternative.
  3. *Level 3 (Automated Tests):* Add a regression test fixture in `tests/`.
  4. *Level 4 (Documentation & Rules):* Update `AGENTS.md` and record the rule in the Rule Enforcement Mapping Table.
- **CLI Commands:**
  ```powershell
  kahnban learnings list [--all]
  kahnban learnings capture --title "..." --problem "..." --ticket "HOA-002" --path "src/app.py"
  kahnban learnings show LRN-0001
  kahnban learnings promote LRN-0001 --level level-2 --notes "Added custom lint rule"
  ```

---

## 8. PSTACK Steerable Principles & Execution Rigor

Kahnban bundles 10 core engineering principles from PSTACK ([cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack)) to guide how agents think and code:
- **`subtract-before-you-add`:** Delete obsolete code and dead abstractions before designing additions.
- **`prove-it-works`:** Passing a build is not proof. Run live flows and verify against real artifacts.
- **`fix-root-causes`:** Never patch symptoms or wrap blind try/catches.
- **`guard-the-context-window`:** Delegate bulk reading to subagents; pass only dense summaries to the root thread.
- **`laziness-protocol`:** Bias toward deletion and the smallest change that solves the problem completely.
- **`boundary-discipline`:** Concentrate guards at boundaries (CLI, config, external APIs); keep business logic pure.
- **`sequence-verifiable-units`:** Stack commits and PRs so every unit ends in a verifiable state.
- **`never-block-on-the-human`:** If an answer can be obtained by running code or testing, don't ask the human.
- **`model-the-domain`:** Express business concepts as domain types, avoiding primitive obsession.
- **`encode-lessons-in-structure`:** The structural fix is the cure; the instruction is the symptom.

To pull additional tools from the extended PSTACK catalog (e.g. `swarm`, `arena`, or all 50+):
```powershell
kahnban skills install --source pstack:all
kahnban skills install --source pstack:swarm
```

---

## 9. Master Conductor: `/factory-mode`

For fully autonomous or semi-autonomous development, activate the master conductor:
```powershell
/factory-mode
```
This single skill weaves together the entire software factory:
1. **Intake & Specification:** `/grill-with-docs` -> `/to-spec` -> `kahnban ready`.
2. **Worktree Isolation:** `kahnban claim <ID> --worktree` -> `ACTIVE_SESSION.md`.
3. **Disciplined Build:** PSTACK principles + `/tdd` Red-Green-Refactor test loops.
4. **Hygiene & Proof:** `/unslop` + `/no-comments` -> `kahnban verify <ID>`.
5. **Gated Review & Closure:** `/code-review` -> `kahnban approve` (another agent) -> `kahnban merge` -> `kahnban done <ID>`.
6. **Continuous Adaptation:** `/reflect` logs session friction to `./learnings/` -> `/harvest-learnings` hardens repo defenses.
