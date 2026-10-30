"""R13/R14: dispatch never offers a backlog/refining ticket whose depends_on
is unfinished, missing, or cyclic; idle names each waiting ticket's blocker."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kahnban import core, dispatcher, roles, scaffold


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", str(r)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "DepTest"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "dep@test.com"], check=True)
    scaffold.init_board(r, prefix="DEP")
    return r


def _write_ticket(repo: Path, col: str, filename: str, content: str) -> None:
    t_file = repo / "plans" / "tickets" / col / filename
    t_file.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", f"add {filename}"], check=True, capture_output=True)


def _ticket(ticket_id: str, title: str, depends_on: str = "") -> str:
    depends_line = f"depends_on: [{depends_on}]" if depends_on else "depends_on: []"
    return f"""---
id: {ticket_id}
title: {title}
status: backlog
category: feature
owner: unassigned
created: 2026-10-29
updated: 2026-10-29
{depends_line}
---

## Problem
{title}.

## Acceptance criteria
- [ ] does the thing (test: `python -c "pass"`)

## Blast radius
- `src/{ticket_id.lower()}.py`

## Implementation notes

## Validation
```bash
python -c "pass"
```

## Log
- 2026-10-29 - created
"""


def test_dependent_waits(repo: Path) -> None:
    config = core.load_config(repo)
    # DEP-001 is listed before its dependency DEP-002 (alphabetically first),
    # but DEP-002 is not done. DEP-001 must never be offered; DEP-002 (the
    # unfinished dependency, otherwise unblocked) is offered instead.
    _write_ticket(repo, "0-backlog", "DEP-001-depends-on-002.md", _ticket("DEP-001", "Depends on 002", "DEP-002"))
    _write_ticket(repo, "0-backlog", "DEP-002-the-dependency.md", _ticket("DEP-002", "The dependency"))

    rec = dispatcher.resolve_next_action(config, preferred_role=roles.SPEC_ANALYST)
    assert rec.action == "spec_and_refine"
    assert rec.ticket_id == "DEP-002"


def test_missing_and_cycle_wait(repo: Path) -> None:
    config = core.load_config(repo)
    # DEP-001 depends on a dependency that does not exist anywhere on the board.
    _write_ticket(repo, "0-backlog", "DEP-001-missing-dep.md", _ticket("DEP-001", "Missing dep", "DEP-999"))
    # DEP-002 depends on itself (a cycle of length one).
    _write_ticket(repo, "0-backlog", "DEP-002-self-cycle.md", _ticket("DEP-002", "Self cycle", "DEP-002"))

    rec = dispatcher.resolve_next_action(config, preferred_role=roles.SPEC_ANALYST)
    assert rec.action != "spec_and_refine"
    assert rec.ticket_id not in ("DEP-001", "DEP-002")


def test_idle_names_blockers(repo: Path) -> None:
    config = core.load_config(repo)
    _write_ticket(repo, "0-backlog", "DEP-001-missing-dep.md", _ticket("DEP-001", "Missing dep", "DEP-999"))
    _write_ticket(repo, "0-backlog", "DEP-002-self-cycle.md", _ticket("DEP-002", "Self cycle", "DEP-002"))

    rec = dispatcher.resolve_next_action(config, preferred_role=roles.SPEC_ANALYST)
    assert rec.action == "idle"
    assert "DEP-001" in rec.summary
    assert "DEP-999" in rec.summary
    assert "DEP-002" in rec.summary
    assert "cycle" in rec.summary.lower()
