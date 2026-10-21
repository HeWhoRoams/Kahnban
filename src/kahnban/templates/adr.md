# ADR-0001: Record Architecture Decisions

**Date:** 1970-01-01  
**Status:** Accepted  
**Deciders:** Architecture Team  
**Consulted Skills:** `/grill-with-docs`

---

## 1. Context & Problem Statement
We need a standard way to capture architectural decisions, domain models, and technical trade-offs so they are visible to both human engineers and AI agents across sessions.

## 2. Decision Drivers
- Long-term codebase integrity.
- Frictionless handoffs between agents and harnesses.
- Machine-verifiable invariant enforcement.

## 3. Decision Outcome
We will record significant architectural decisions as numbered markdown files in `ADR/` following this template, keeping domain vocabulary synchronized in `GLOSSARY.md`.

### Consequences
- **Positive:** Context survives across agent sessions.
- **Negative:** Engineers and agents must maintain records when architecture changes.
