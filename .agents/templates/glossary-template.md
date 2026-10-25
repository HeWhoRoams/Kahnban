# Domain Model & Technical Glossary

This glossary acts as the single source of truth for domain vocabulary, entities, state boundaries, and technical jargon across all human and agent workflows.

Before adding new terms or features, run `/grill-with-docs` to refine intent and expand this glossary.

---

## 1. Core Domain Entities

### [Entity / Domain Term 1]
- **Definition:** Clear, unambiguous definition of the concept in this codebase.
- **Invariants:** What must always hold true for this entity.
- **Key Files:** `path/to/models/entity1.ext`
- **Related Terms:** [Term 2]

### [Entity / Domain Term 2]
- **Definition:** Clear definition.
- **Invariants:** Constraints and rules.
- **Key Files:** `path/to/systems/entity2.ext`

---

## 2. Technical Contracts & Architectural Invariants

### [Invariant 1]
- **Rule:** Description of rule (e.g., "All game state mutations must flow through ResolutionEngine signals; UI never mutates state directly").
- **Enforcement:** Automated tests in `tests/test_invariants.ext`.

---

## 3. Deprecated Jargon & Antipatterns
- **[Deprecated Term]:** Use **[Preferred Term]** instead. Reason: [Why].
