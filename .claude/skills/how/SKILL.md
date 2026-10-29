---
name: how
description: "Use for 'how does X work', code walkthroughs before changing something, and placement / ownership / layering questions ('where should this live', 'which package owns this', 'is this the right layer'). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
---

# How

Explore the codebase to answer "how does X work?" questions. Produce architectural explanations at the level of a senior engineer onboarding onto a subsystem, enough to build a working mental model, not so much that it reads like annotated source code.

## 1. Assess Complexity

If the scope is ambiguous, state your interpretation and explore. The user can redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how does function X work"): Explore and explain in a single pass.
- **Complex** (a subsystem spanning multiple files or services, a cross-cutting feature, a full architectural overview): Decompose into 2 to 4 angles (e.g. data flow, API interface, state lifecycle, error handling) and explore concurrently.

When in doubt, take the simple path.

## 2. Exploration Protocol

When exploring the subsystem:
1. Locate the entry points and public interfaces.
2. Trace the data flow through key transformations and state transitions.
3. Identify ownership boundaries and persistence models.
4. Note critical invariants, failure recovery, and concurrency assumptions.

## 3. Explanation Structure

Structure the explanation into clear sections, omitting any that do not apply:

### Overview
A concise 2-3 sentence summary of what the subsystem does and its primary role in the codebase.

### Key Concepts & Data Structures
The core entities, data models, and domain terminology necessary to understand the subsystem.

### Runtime Flow & Lifecycle
Step-by-step walkthrough of the execution sequence during a standard operation, including entry points, transformations, and exit points.

### Placement & Ownership
Where components live in the filesystem, why they belong in those packages, and what layer they occupy.

### Gotchas & Edge Cases
Non-obvious behaviors, subtle invariants, concurrency/re-entrancy concerns, or common pitfalls when modifying this code.
