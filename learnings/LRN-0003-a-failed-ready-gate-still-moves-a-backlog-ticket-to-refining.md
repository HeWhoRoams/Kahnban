---
id: LRN-0003
title: A failed ready gate still moves a backlog ticket to refining
status: pending
occurrences: 1
severity: medium
category: architecture
target_paths: [src/kahnban/core.py]
first_seen: 2026-10-29
last_seen: 2026-10-29
resolved: ""
escalation_level: ""
---
### Problem / Friction Pattern
kahnban ready on a backlog ticket whose dependencies are not done refuses, yet moves it 0-backlog -> 1-refining, which dispatch intake prefers over backlog.

### Occurrences & Environmental Gaps
| Occurrence | Ticket / Session | Location | Trigger / Environmental Gap |
| :--- | :--- | :--- | :--- |
| #1 | - | `src/kahnban/core.py ready` | SPEC-001: probing 14 waiting tickets with kahnban ready moved them all to 1-refining |

### Systemic Environmental Diagnosis
Under investigation.

### Proposed Structural Remediation
Leave the ticket in its column when the only problems are unfinished dependencies, or move only on success
