"""Tests for HandoffBaton and situational dispatcher."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kahnban import core, dispatcher, handoff


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", str(r)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "DispTest"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "disp@test.com"], check=True)
    core.init_board(r, prefix="DISP")
    return r


def _write_ticket(repo: Path, col: str, filename: str, content: str) -> None:
    t_file = repo / "plans" / "tickets" / col / filename
    t_file.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", f"add {filename}"], check=True, capture_output=True)


def test_handoff_baton_roundtrip(repo: Path) -> None:
    config = core.load_config(repo)
    t_text = """---
id: DISP-001
title: Add auth middleware
status: ready
category: feature
owner: unassigned
created: 2026-10-21
updated: 2026-10-21
---

## Problem
Add auth.

## Acceptance criteria
- [ ] Token verified
- [ ] Expired token rejected

## Blast radius
- `src/auth.py`

## Validation
```bash
pytest tests/test_auth.py
```

## Log
- 2026-10-21 - created
"""
    _write_ticket(repo, "2-ready", "DISP-001-add-auth-middleware.md", t_text)

    baton = handoff.build_handoff_baton(config, "DISP-001", stage="implementation", assigned_role="coder")
    assert baton.ticket_id == "DISP-001"
    assert baton.assigned_role == "coder"
    assert baton.qa_contract.feature_test_command == "pytest tests/test_auth.py"
    assert "src/auth.py" in baton.qa_contract.blast_radius_files
    assert len(baton.acceptance_criteria) == 2

    # Write and read back
    p = handoff.write_handoff_baton(repo, baton)
    assert p.is_file()

    read_back = handoff.read_handoff_baton(repo, "DISP-001")
    assert read_back is not None
    assert read_back.ticket_id == "DISP-001"
    assert read_back.assigned_role == "coder"
    assert read_back.qa_contract.feature_test_command == "pytest tests/test_auth.py"


def test_qa_rejection_feedback_loop(repo: Path) -> None:
    config = core.load_config(repo)
    t_text = """---
id: DISP-001
title: Payment gateway
status: ready
category: feature
owner: unassigned
created: 2026-10-21
updated: 2026-10-21
---

## Problem
Pay gateway.

## Acceptance criteria
- [ ] Stripe charge succeeds

## Blast radius
- `src/pay.py`

## Validation
```bash
pytest tests/test_pay.py
```

## Log
- 2026-10-21 - created
"""
    _write_ticket(repo, "2-ready", "DISP-001-payment-gateway.md", t_text)

    # Initial baton
    baton = handoff.build_handoff_baton(config, "DISP-001", stage="implementation", assigned_role="coder")
    handoff.write_handoff_baton(repo, baton)

    # QA records rejection feedback
    updated = handoff.record_rejection_feedback(
        repo,
        "DISP-001",
        "Mock was used instead of testing real webhook signature",
        author="qa_lead"
    )
    assert updated is not None
    assert len(updated.verification_results.rejection_history) == 1
    assert updated.verification_results.rejection_history[0]["author"] == "qa_lead"
    assert "Mock was used" in updated.next_action["prompt"]


def test_dispatcher_priority(repo: Path) -> None:
    config = core.load_config(repo)

    # 1. Empty board: idle
    rec = dispatcher.resolve_next_action(config)
    assert rec.action == "idle"

    # 2. Add ticket to 0-backlog -> spec_and_refine
    t_backlog = """---
id: DISP-001
title: Design telemetry
status: backlog
category: feature
owner: unassigned
created: 2026-10-21
updated: 2026-10-21
---

## Problem
Telemetry.

## Acceptance criteria
- [ ] Telemetry events captured

## Blast radius
- `src/telemetry.py`

## Validation
```bash
pytest
```

## Log
- 2026-10-21 - created
"""
    _write_ticket(repo, "0-backlog", "DISP-001-design-telemetry.md", t_backlog)
    rec = dispatcher.resolve_next_action(config)
    assert rec.action == "spec_and_refine"
    assert rec.assigned_role == "spec_analyst"

    # 3. Add ticket to 2-ready -> claim_and_implement takes precedence over backlog
    t_ready = """---
id: DISP-002
title: Implement logger
status: ready
category: feature
owner: unassigned
created: 2026-10-21
updated: 2026-10-21
---

## Problem
Logger.

## Acceptance criteria
- [ ] Log formatted as JSON

## Blast radius
- `src/log.py`

## Validation
```bash
python -c "print('OK')"
```

## Log
- 2026-10-21 - created
"""
    _write_ticket(repo, "2-ready", "DISP-002-implement-logger.md", t_ready)
    rec = dispatcher.resolve_next_action(config)
    assert rec.action == "claim_and_implement"
    assert rec.assigned_role == "coder"
    assert rec.ticket_id == "DISP-002"
