---
name: reflect
description: "Mine the completed ticket or active session for friction, mistakes, and architectural insights, then capture or augment deduplicated patterns in ./learnings/."
---

# Reflect: Closed-Loop Session Learning

You mine the active session, git commit log, and review comments for durable learnings, then stage them into `./learnings/` using the **Pattern Aggregator Protocol**.

## The Lauren Tan Clustering Invariant
**Never create duplicative one-off entries for recurring mistakes.**
Before creating a new file, search `./learnings/` for an existing pending record matching the problem shape or target paths:
- If a match is found: **Augment it.** Increment `occurrences`, escalate `severity` if warranted, append a row to the occurrences table with location and environmental trigger, and refine the systemic diagnosis.
- If no match: Mint `LRN-xxxx-<slug>.md` with `occurrences: 1`.

## Protocol

### 1. Analyze Friction Points
Review the current session or completed ticket:
- Did an agent attempt an invalid transition or violate a board invariant?
- Did a test fail multiple times during `/tdd` before passing?
- Did `/code-review` find recurring hygiene, typing, or blast-radius issues?
- Did the operator intervene with a correction?

### 2. Formulate the Learning
Capture:
- **Title:** Dense, descriptive summary of the failure shape (e.g., `Direct non-atomic file writes bypass safety locks`).
- **Category:** `architecture` | `typing-lint` | `testing` | `convention`
- **Severity:** `low` | `medium` | `high` | `critical`
- **Target Paths:** Relative repo paths involved.
- **Problem:** What failed, how it manifested, and what broke.
- **Occurrence Details:** Ticket ID (`HOA-xxx`), line/function location, and immediate trigger.
- **Systemic Environmental Diagnosis:** Why did the environment allow this mistake? What missing constraint, confusing export, or architectural ambiguity encouraged it?
- **Proposed Structural Remediation:** How can this be eliminated using the 4-Tier Ladder (Architecture, Linter, Test, or Rule)?

### 3. Commit to `./learnings/`
Use `kahnban learnings capture`:
```powershell
kahnban learnings capture --title "<title>" --problem "<desc>" --ticket "<ID>" --location "<file:line>" --trigger "<trigger>" --category "<cat>" --severity "<sev>" --path "<path>"
```
Or edit/create `./learnings/LRN-xxxx-<slug>.md` directly following the schema.
