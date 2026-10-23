"""Tests for Dual-Tier QA Verification (Feature Tests + Regression Tests)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kahnban import core
from conftest import set_board_config


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", str(r)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "QATest"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "qa@test.com"], check=True)
    core.init_board(r, prefix="QAT")
    # These tests place tickets straight into in-progress to exercise tier
    # ordering; the red/green proof is covered in test_factory_gates.py.
    set_board_config(r, require_proof=False)
    return r


def test_dual_tier_parser(repo: Path) -> None:
    config = core.load_config(repo)
    body = """## Problem
Needs feature and regression testing.

## Acceptance criteria
- [ ] Criteria 1

## Blast radius
- `src/feature.py`

## Validation
### Feature Tests
```bash
pytest tests/test_feature.py -v
```

### Regression Tests
```bash
pytest tests/ -q
```
"""
    feat_cmd, reg_cmd = core.parse_validation_commands(config, body)
    assert feat_cmd == "pytest tests/test_feature.py -v"
    assert reg_cmd == "pytest tests/ -q"


def test_dual_tier_execution_success(repo: Path) -> None:
    config = core.load_config(repo)
    # Ticket with passing feature test and passing regression test
    t_text = """---
id: QAT-001
title: Dual Test Pass
status: in-progress
category: feature
owner: test-agent
created: 2026-10-21
updated: 2026-10-21
---

## Problem
Feature works.

## Acceptance criteria
- [ ] Criterion 1

## Blast radius
- `main.py`

## Validation
### Feature Tests
```bash
python -c "print('Feature PASS')"
```

### Regression Tests
```bash
python -c "print('Regression PASS')"
```

## Log
- 2026-10-21 - claimed
"""
    ticket_file = repo / "plans" / "tickets" / "3-in-progress" / "QAT-001-dual-test-pass.md"
    ticket_file.write_text(t_text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket"], check=True)

    res = core.verify(config, "QAT-001")
    assert res.passed is True
    assert res.exit_code == 0
    assert "Feature PASS" in res.output
    assert "Regression PASS" in res.output
    # Check that ticket moved to 4-verifying
    ticket_after = core.find_ticket(config, "QAT-001")
    assert ticket_after.column == "4-verifying"


def test_dual_tier_feature_failure_skips_regression(repo: Path) -> None:
    config = core.load_config(repo)
    # Ticket with failing feature test
    t_text = """---
id: QAT-002
title: Feature Fail
status: in-progress
category: feature
owner: test-agent
created: 2026-10-21
updated: 2026-10-21
---

## Problem
Feature fails.

## Acceptance criteria
- [ ] Criterion 1

## Blast radius
- `main.py`

## Validation
### Feature Tests
```bash
python -c "import sys; print('Feature FAIL'); sys.exit(1)"
```

### Regression Tests
```bash
python -c "print('Regression SHOULD NOT RUN')"
```

## Log
- 2026-10-21 - claimed
"""
    ticket_file = repo / "plans" / "tickets" / "3-in-progress" / "QAT-002-feature-fail.md"
    ticket_file.write_text(t_text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket 2"], check=True)

    res = core.verify(config, "QAT-002")
    assert res.passed is False
    assert res.exit_code == 1
    assert "Feature FAIL" in res.output
    assert "Regression SHOULD NOT RUN" not in res.output
    # Ticket should stay in 3-in-progress
    ticket_after = core.find_ticket(config, "QAT-002")
    assert ticket_after.column == "3-in-progress"
