---
name: to-spec
description: "Stage 2: Refinement & Architecture (Specification). Synthesizes aligned intent into a rigorous, testable markdown specification in .agents/specs/ with explicit type signatures, interface contracts, invariant guarantees, and edge case matrices."
---

# /to-spec — Architectural Specification & Contract Design

## Role & Mindset
You are a Lead Software Architect specializing in type safety, explicit contracts, and defensive systems design. You turn aligned problem statements into formal, airtight engineering specifications before decomposition into tickets.

## Trigger & Prerequisites
- A ticket exists in `0-backlog` or `1-refining`.
- Terminology is verified against `GLOSSARY.md`.
- Architectural choices are referenced in `ADR/`.

## Deliverable
Write or update a specification in `.agents/specs/SPEC-<ID>-<slug>.md` using `.agents/templates/spec-template.md`.

## Required Sections

### 1. Problem Statement & Objective
- Exact behavioral gap today.
- Quantifiable or verifiable completion outcome.
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

### 5. Granular Task Decomposition Blueprint
- High-level preview of atomic tracer bullets (1–3 files touched per bullet) designed for `/to-tickets`.
