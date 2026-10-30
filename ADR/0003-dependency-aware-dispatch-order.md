# ADR-0003: Dependency-aware dispatch ordered by priority, risk and unblocking

**Date:** 2026-10-29
**Status:** Accepted
**Deciders:** Tim Niles
**Consulted Skills:** `/grill-with-docs`

---

## 1. Context & Problem Statement
The dispatcher hands the first backlog or refining ticket to the spec analyst without checking `depends_on`, while `ready` refuses any ticket whose dependencies are not done. On a large spec, dependent tickets fail the ready gate until `max_attempts` escalates them to a human. Ready tickets are taken first-come, so risky work and work that blocks others gets no precedence.

## 2. Options considered
- **Waiting tickets:** refine them early but don't call `ready`, *or* skip them until their dependencies are done (**chosen**: the smallest change, and it cannot burn attempts).
- **Ordering:** a single `priority` field, *or* `priority` plus `risk` plus unblocking count (**chosen**: priority is the human's intent, risk-first catches failures early, and unblocking-first keeps the swarm wide).
- **Idle reporting:** a new dispatch action, *or* the existing idle report naming each waiting ticket and its blocker (**chosen**).

## 3. Decision Outcome
Intake and claim candidates are filtered to tickets with every dependency done, then sorted by priority (`critical > high > normal > low`), then risk (`high > medium > low`), then the number of open tickets transitively depending on the ticket (most first), then id. A missing dependency or a cycle makes the ticket wait, and the idle report names it. Lint gains a cycle rule. An invalid `priority` or `risk` value gets a lint warning and is treated as the default.

### Consequences
- **Positive:** A whole spec's dependency chain runs without escalations. Critical, risky and blocking work goes first.
- **Negative:** Two more optional frontmatter fields. Computing transitive dependents on every dispatch costs O(tickets²) in the worst case, which is fine at board scale.
