"""KB-031: the dry-run ingest report surfaces each draft's spec and covers."""

from __future__ import annotations

import json
from pathlib import Path

from kahnban import core, ingest

from conftest import git

SPEC = """---
id: SPEC-005
title: Example spec
---

# Example spec

## Tickets

### Add the thing
Problem: there is no thing.

Acceptance criteria:
- [ ] the thing exists

Files:
- `src/thing.py`

Covers: R18, R19
"""


def write_spec(repo: Path) -> Path:
    path = repo / "specs" / "example.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SPEC, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "add spec document")
    return path


def test_text_report_shows_spec_and_covers(board: Path) -> None:
    spec = write_spec(board)
    config = core.load_config(board)

    [report] = ingest.ingest(config, [spec], dry_run=True)
    rendered = ingest.render_report([report])

    assert "spec: SPEC-005" in rendered
    assert "covers: R18, R19" in rendered


def test_json_report_has_spec_and_covers(board: Path) -> None:
    spec = write_spec(board)
    config = core.load_config(board)

    [report] = ingest.ingest(config, [spec], dry_run=True)
    payload = json.loads(json.dumps(report.as_dict()))

    draft = payload["drafts"][0]
    assert draft["spec"] == "SPEC-005"
    assert draft["covers"] == ["R18", "R19"]
