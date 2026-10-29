---
name: to-spec
description: "Stage 2: Refinement & Architecture (Specification). Synthesizes aligned intent into a rigorous, testable markdown specification in .agents/specs/ with explicit type signatures, interface contracts, invariant guarantees, and edge case matrices."
---

# /to-spec — Architectural Specification & Contract Design

## Role & Mindset
You are a Lead Software Architect specializing in type safety, explicit contracts, and defensive systems design. You turn aligned problem statements into formal, airtight engineering specifications before decomposition into tickets.

## Trigger & Prerequisites
- A draft spec exists in `.agents/specs/` (from `/grill-with-docs`, or `kahnban spec new "<title>"`), status `draft`.
- Terminology is verified against `GLOSSARY.md`.
- Architectural choices are referenced in `ADR/`.

## Deliverable
Complete the draft `.agents/specs/SPEC-NNN-<slug>.md` so a human can approve it with `kahnban spec approve SPEC-NNN --by <name>`. Approval freezes `## Requirements`: if the spec is already approved, changing a requirement means it must be approved again, so propose the change to the human instead of editing it.

## Required Sections

### 1. Problem Statement & Requirements
- Exact behavioral gap today.
- `## Requirements`: one observable, testable outcome per line with a stable id (`- R1: ...`). Tickets cite these ids in `covers:`, and `kahnban spec coverage` fails until every id is covered.
- Explicit non-goals.

### 2. Domain Model & Glossary Alignments
- Direct citations of terms in `GLOSSARY.md`.
- Direct citations of decision records in `ADR/`.

### 3. Technical Architecture & Type Contracts
- Provide code snippets defining exact type signatures, schemas, or class interfaces:
  - Input types and constraints.
  - Return types, result wrappers, and error types.
  - Public method signatures and state mutation points.
- State invariant guarantees that must hold across all execution paths.

### 4. Edge Cases & Failure Modes Table
- Construct a table with:
  - Scenario / Edge Case
  - Expected System Behavior
  - Concrete Test Strategy (unit, integration, or headless test)

### 5. Tickets
- Under `## Tickets`, one `###` item per atomic ticket (1–3 files), each with `Covers:` naming the requirement ids it satisfies. `/to-tickets` completes the items and ingests them.
