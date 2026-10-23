---
name: grill-with-docs
description: "Stage 1: Intake. Interview the user in rounds until every decision behind an idea is settled, record terms in GLOSSARY.md and choices in ADR/, then write a draft spec (SPEC-NNN) with numbered requirements for the human to approve. The approved spec is the input to /to-tickets."
---

# /grill-with-docs — From an idea to an approvable spec

You turn a rough idea, feature request or bug report into a spec a human can approve in one read. Nothing reaches the board's ready column without an approved spec behind it when the board sets `require_spec`, so this interview is where the human's judgment goes in; everything after it runs on gates.

## The interview

Treat the idea as a tree of decisions: each decision opens the ones that depend on it.

1. **Ask in rounds.** A round holds every question you can ask *now*: the ones whose prerequisites are already answered. Number them, give your recommended answer for each, and wait. A question that depends on another one still open waits for a later round.
2. **Facts are yours, decisions are theirs.** Never ask the user something the code, the docs or a command can tell you. Look it up (or send a subagent to) and carry on with the rest of the round. Put only real choices to the user.
3. **Cover the edges.** Before you stop, the tree must answer: behaviour on missing, invalid and boundary input; what must never break (existing contracts, performance, data); and what is explicitly out of scope.
4. **Stop when nothing is assumed.** You are done when no open question remains and the user agrees you share the same picture. Do not write the spec before that.

## Record as you go

- **Terms:** when a word is used in a specific sense, define it in `GLOSSARY.md` (one line, plus the files it lives in).
- **Decisions:** when the user picks between real alternatives (a storage layout, a protocol, a dependency), write `ADR/NNNN-<slug>.md` with the options and why this one won.

## Write the spec

```bash
kahnban spec new "<feature name>"
```

Fill in the drafted `.agents/specs/SPEC-NNN-<slug>.md`:

- `## Problem`: the gap in two or three sentences.
- `## Requirements`: one observable outcome per line, `- R1: ...`, `- R2: ...`. Each must be checkable by a test. These ids are what tickets cite, so make each one small and unambiguous.
- `## Non-goals`, `## Decisions` (link the GLOSSARY entries and ADRs) and `## Edge cases`.
- Leave `## Tickets` for `/to-tickets`.

## Hand it over

Tell the user the spec is ready for review and that approving it is their call:

```bash
kahnban spec approve SPEC-NNN --by <their name>
```

Approval freezes the requirements. Do not approve it yourself, and never on the user's behalf.
