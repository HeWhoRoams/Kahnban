# Domain Model & Technical Glossary

The single source of truth for vocabulary used across specs, tickets, skills and agents. `/kb-grill-with-docs` adds terms here as they come up.

---

## 1. Core Domain Entities

### Localized skill
- **Definition:** A skill Kahnban ships and owns, named with the `kb-` prefix. It may start from an upstream source, but from then on it is edited in this repo and never silently overwritten by upstream.
- **Invariants:** Every skill under `src/kahnban/templates/skills/` is a localized skill. Its provenance is recorded in `.agents/skills.lock.json`.
- **Key Files:** `src/kahnban/templates/skills/`, `src/kahnban/skills.py`, `src/kahnban/skills_check.py`
- **Related Terms:** Provenance

### Provenance
- **Definition:** The upstream origin of a localized skill or agent: its repository, its path, and the commit it was taken from. Skills native to Kahnban record `kahnban` as their source.
- **Invariants:** Pulling in an upstream change is a deliberate edit. Nothing syncs automatically.
- **Key Files:** `.agents/skills.lock.json`, `src/kahnban/trust.py`, `THIRD_PARTY_NOTICES.md`

### Priority
- **Definition:** A ticket's optional `priority:` frontmatter, one of `critical | high | normal | low` (default `normal`). It records the human's intent for ordering.
- **Key Files:** `src/kahnban/dispatcher.py`, `src/kahnban/templates/ticket.md`
- **Related Terms:** Risk, Dispatch order

### Risk
- **Definition:** A ticket's optional `risk:` frontmatter, one of `high | medium | low` (default `medium`). Riskier work goes first, so it fails early.
- **Key Files:** `src/kahnban/dispatcher.py`

### Dispatch order
- **Definition:** The order in which `kahnban next` and `kahnban run` hand out intake and claim work: priority, then risk (highest first), then the number of open tickets transitively waiting on the ticket (most first), then ticket id.
- **Related Terms:** Waiting ticket

### Waiting ticket
- **Definition:** An open ticket in which some `depends_on` entry is not in done, does not exist, or forms a cycle. Dispatch skips it, and an idle report names what it is waiting on.
- **Key Files:** `src/kahnban/dispatcher.py`, `src/kahnban/core.py` (`_dependency_problems`)

---

## 2. Technical Contracts & Architectural Invariants

### Learnings never block the board
- **Rule:** `reject` and `escalate` capture a learning automatically. If the capture fails, the transition still completes and prints a warning.
- **Enforcement:** Tests for SPEC-001 R20–R21.
