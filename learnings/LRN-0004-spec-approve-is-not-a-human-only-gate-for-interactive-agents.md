---
id: LRN-0004
title: spec approve is not a human-only gate for interactive agents
status: pending
occurrences: 1
severity: high
category: architecture
target_paths: [src/kahnban/specs.py]
first_seen: 2026-10-29
last_seen: 2026-10-29
resolved: ""
escalation_level: ""
---
### Problem / Friction Pattern
The guard only blocks spec approve when KAHNBAN_ROLE is set; an interactive agent session has none, and --by is free text, so any agent can approve as anyone.

### Occurrences & Environmental Gaps
| Occurrence | Ticket / Session | Location | Trigger / Environmental Gap |
| :--- | :--- | :--- | :--- |
| #1 | - | `src/kahnban/specs.py:107 approve_spec; src/kahnban/guard.py:72` | SPEC-001 was approved by claude-opus-5-5 at the user's request to test the gate |

### Systemic Environmental Diagnosis
Under investigation.

### Proposed Structural Remediation
Require a human reviewer key (as signed ticket approvals do) for spec approve; record the signer, not a free-text name
