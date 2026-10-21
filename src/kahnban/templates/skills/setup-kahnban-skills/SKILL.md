---
name: setup-kahnban-skills
description: Sets up and activates Kahnban and Matt Pocock skills across AI harnesses with interactive source and harness selection.
---

# Setup Kahnban Skills

Use this skill once per repository or when switching/adding new AI coding harnesses (Claude Code, Gemini CLI, Cursor, Antigravity, ChatGPT Codex).

---

## What It Does

1. **Discovers Current Harness**:
   - Inspects existing configuration directories (`.claude/`, `.gemini/`, `.cursor/`, `.agents/`).
2. **Presents Installation Options (Default = Bundled)**:
   - **Option 1 (Default - Zero External Network)**: Installs Kahnban's bundled Matt Pocock 5-stage pipeline skills (`/grill-with-docs`, `/to-spec`, `/to-tickets`, `/tdd`, `/code-review`) directly into `.agents/skills/`.
   - **Option 2 (Upstream Extended)**: Pulls Matt Pocock's complete library (`mattpocock/skills`) including `/domain-modeling`, `/codebase-design`, `/diagnosing-bugs`, `/prototype`, `/retro` via `npx skills add mattpocock/skills`.
3. **Configures Harness Links**:
   - **Claude Code**: Links `.claude/skills` to `.agents/skills`.
   - **Gemini CLI / Antigravity**: Populates `.gemini/skills/` or mirrors to `~/.gemini/config/skills/`.
   - **Cursor**: Generates `.cursor/rules/kanban.mdc`.
4. **Verifies Board Readiness**:
   - Checks that `plans/board.config.json` has a valid `validation_command`.
   - Verifies `GLOSSARY.md` and `ADR/` exist.
   - Runs `kahnban lint` and confirms zero board violations.

---

## Execution Protocol

Run the Kahnban CLI skills command:

```powershell
# Default: installs bundled skills and configures detected harnesses
py -3 -m kahnban skills install

# To choose specific target harness:
py -3 -m kahnban skills install --harness claude    # or gemini, cursor, all

# To pull full upstream library from mattpocock/skills:
py -3 -m kahnban skills install --source mattpocock
```

After installation, verify with:
```powershell
py -3 -m kahnban skills list
py -3 -m kahnban lint
```
