---
id: LRN-0005
title: A ticket's blast radius cannot be amended once it is in progress
status: pending
occurrences: 1
severity: medium
category: architecture
target_paths: [src/kahnban/ingest.py]
first_seen: 2026-10-29
last_seen: 2026-10-29
resolved: ""
escalation_level: ""
---
### Problem / Friction Pattern
ingest --update only refreshes backlog and refining tickets, so a radius error found at the first verify needs a logged move back to refining and a re-ready, which discards the claim.

### Occurrences & Environmental Gaps
| Occurrence | Ticket / Session | Location | Trigger / Environmental Gap |
| :--- | :--- | :--- | :--- |
| #1 | - | `src/kahnban/ingest.py:910` | SPEC-001 KB-015: verify failed 3 regression tests pinning old skill names in files outside the generated radius |

### Systemic Environmental Diagnosis
Under investigation.

### Proposed Structural Remediation
Offer an audited amend-radius path for in-progress tickets that keeps the claim and branch, re-freezes the contract hash, and clears any approval
