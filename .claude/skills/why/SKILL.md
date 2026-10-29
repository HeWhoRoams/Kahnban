---
name: why
description: "Use for 'why does X work this way', 'why we picked Y', design rationale, regressions, postmortems, or data-backed thresholds. Discovers available tools and queries each evidence category (git history, issue tracker, ADRs/docs, commit logs), then returns a cited read on decisions and tradeoffs. Use how for runtime behavior."
---

# Why

Investigate the motivation, history, and intent behind code. The companion `how` skill answers what the code does and how it works. `why` answers what forces led to its shape.

## Operating Posture

Operate as a careful, cautious, and precise investigator. Distinguish clearly between:
- **Direct Facts**: Verifiable from commit messages, pull requests, ADRs, or comments.
- **Inferred Rationale**: Logical deductions based on surrounding code constraints.
- **Unknowns**: Open questions where evidence is missing or ambiguous.

## Step 1. Identify the Target and Question

The **target** is usually a chunk of code, a pattern, a feature, or a named design decision. The **question** is usually a design rationale, a tradeoff, an edge-case mitigation, an external constraint, or history sweep.

If the target is vague, make your best guess from conversation context, state your interpretation briefly, and proceed.

## Step 2. Establish the Code Anchor

Gather concrete historical evidence:
- File paths and line ranges.
- Key symbols (functions, classes, constants).
- Recent git commits touching the target:
  ```bash
  git log -p -n 5 -- <file>
  ```
- Git blame for last-touch rationale:
  ```bash
  git blame -L <start>,<end> <file>
  ```
- Search for corresponding ADRs, PRDs, or specs in `docs/adr/`, `plans/`, or `.agents/specs/`.

## Step 3. Synthesize the Rationale

Deliver a structured synthesis answering:

### 1. Problem & Context
What problem was the author solving? What constraints or forces were active when this code was introduced?

### 2. Tradeoffs & Rejected Alternatives
What alternatives were considered or bypassed? What compromises were accepted (e.g. simplicity vs performance, flexibility vs strictness)?

### 3. Citations & Evidence
Cite specific commits, PRs, issues, or ADRs that substantiate the explanation. Quote key commit messages or author comments directly.

### 4. Remaining Ambiguity
Explicitly call out any gaps where the code does not document its motivation and history lacks explanation.
