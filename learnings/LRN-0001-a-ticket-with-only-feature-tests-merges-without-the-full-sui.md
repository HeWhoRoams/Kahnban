---
id: LRN-0001
title: A ticket with only feature tests merges without the full suite
status: pending
occurrences: 1
severity: medium
category: testing
target_paths: []
first_seen: 2026-10-26
last_seen: 2026-10-26
resolved: ""
escalation_level: ""
---
### Problem / Friction Pattern
No problem description recorded.

### Occurrences & Environmental Gaps
| Occurrence | Ticket / Session | Location | Trigger / Environmental Gap |
| :--- | :--- | :--- | :--- |
| #1 | KB-001 | `plans/board.config.json` | Initial occurrence |

### Systemic Environmental Diagnosis
The board set validation_command but not regression_command, so a ticket that names its own feature tests got no regression run at verify or at the merge queue.

### Proposed Structural Remediation
Set regression_command to the full suite in the init defaults, or have init warn when only validation_command is set.
