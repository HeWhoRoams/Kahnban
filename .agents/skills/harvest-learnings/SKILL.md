---
name: harvest-learnings
description: "Investigate and drain the ./learnings/ queue, escalating recurring patterns up the 4-tier structural ladder (Architecture -> Linter/Types -> Tests -> Rules) into repo defenses."
---

# Harvest Learnings: Structural Defect Elimination

You drain the `./learnings/` staging queue, find mistake classes with `occurrences >= 2`, and eliminate them mechanically across the codebase.

## The 4-Tier Escalation Ladder

Always fix at the highest level that holds:
1. **Level 1 — Eliminate with Architecture:** Make the mistake physically impossible. Create private boundaries, remove ambiguous exports, delete legacy deprecated code an LLM would copy, or enforce single-source-of-truth data models.
2. **Level 2 — Block with Linters & Types:** If bad code still compiles, add a static check whose error message explicitly names the alternative. (e.g. add a check in `kahnban lint` or repo linter).
3. **Level 3 — Catch with Automated Tests:** Add a regression test fixture in `tests/` that fails if the bad pattern is reintroduced.
4. **Level 4 — Document with Enforcement Mapping:** If Levels 1–3 are impossible, update `AGENTS.md` and record the rule in the **Rule Enforcement Mapping Table**.

## Protocol

1. **Scan `./learnings/`:** Read all pending records (exclude `archive/`).
2. **Cluster & Triage:** Sort by `occurrences` descending and `severity`.
   - Items with `occurrences == 1` are kept pending unless flagged `critical`.
   - Items with `occurrences >= 2` **must** be remediated structurally now.
3. **Execute the Fix:**
   - Implement the Level 1, 2, or 3 fix.
   - Run tests to prove the fix blocks the past failure.
4. **Promote & Archive:**
   - Update learning record: `status: promoted`, `resolved: <date>`, `escalation_level: level-X`.
   - Move from `./learnings/` to `./learnings/archive/`.
   - Use `kahnban learnings promote <id> --level <level> --artifact <rule, path, commit or ticket> --notes "<resolution notes>"`.
5. **Report:** Output an executive changelog of defenses added.
