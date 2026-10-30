---
id: LRN-0002
title: Ingest splits Depends-on titles on ' and ' and commas
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
A Depends on: line naming a ticket whose title contains 'and' or a comma is split into fragments, which resolve to nothing and land in blocked_on.

### Occurrences & Environmental Gaps
| Occurrence | Ticket / Session | Location | Trigger / Environmental Gap |
| :--- | :--- | :--- | :--- |
| #1 | - | `src/kahnban/ingest.py` | SPEC-001 ingest dry-run: 'Add the MIT licence and third-party notices' became two unresolved names |

### Systemic Environmental Diagnosis
Under investigation.

### Proposed Structural Remediation
Resolve the whole line against known titles first and split only when that fails, or require ; as the separator
