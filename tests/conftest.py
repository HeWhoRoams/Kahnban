"""Shared fixtures: throwaway git repos and scaffolded boards."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kahnban import gitops


DEFAULT_CONFIG = {
    "engine_min_version": "0.1.0",
    "id_prefix": "TST",
    "board_root": "plans/tickets",
    "columns": [
        "0-backlog",
        "1-refining",
        "2-ready",
        "3-in-progress",
        "4-verifying",
        "5-done",
    ],
    "done_column": "5-done",
    "wip_limit": 3,
    "use_worktrees": True,
    "shared_caches": [],
    "validation_timeout_sec": 60,
    "log_output_max_bytes": 4096,
    "required_headings": [
        "Problem",
        "Acceptance criteria",
        "Blast radius",
        "Implementation notes",
        "Validation",
        "Log",
    ],
    "validation_command": "",
    "design_doc_roots": ["plans"],
    "extensions": {},
}


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return gitops.run(repo, args)


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch", "main", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(path, "config", "user.name", "Kahnban Test")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("scratch repo\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "initial commit")
    return path


def write_ticket(
    board_root: Path,
    column: str,
    ticket_id: str,
    slug: str,
    *,
    title: str = "Example ticket",
    status: str | None = None,
    owner: str = "unassigned",
    branch: str = "",
    worktree: str = "",
    depends_on: str = "[]",
    blocked_on: str = "",
    blast_radius: tuple[str, ...] = ("src/example.py",),
    acceptance: tuple[str, ...] = ("- [ ] behaves",),
    validation: str = "git --version",
    log: tuple[str, ...] = ("- 2026-08-18 10:00 - created -> 0-backlog",),
    extra_frontmatter: str = "",
    junctions: str = "[]",
) -> Path:
    head, separator, tail = column.partition("-")
    derived = tail if separator and head.isdigit() else column
    resolved_status = status if status is not None else derived
    radius = "\n".join("- `" + item + "`" for item in blast_radius)
    criteria = "\n".join(acceptance)
    log_lines = "\n".join(log)
    extra = extra_frontmatter + "\n" if extra_frontmatter else ""
    text = f"""---
id: {ticket_id}
title: {title}
status: {resolved_status}
owner: {owner}
branch: "{branch}"
worktree: "{worktree}"
created: 2026-08-18
updated: 2026-08-18
legacy_id: ""
design_docs: []
depends_on: {depends_on}
blocked_on: "{blocked_on}"
junctions: {junctions}
{extra}---

## Problem
Something needs doing.

## Acceptance criteria
{criteria}

## Blast radius
{radius}

## Implementation notes
- Keep it small.

## Validation
```
{validation}
```

## Log
{log_lines}
"""
    destination = board_root / column / f"{ticket_id}-{slug}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination


def scaffold_board(repo: Path, config_overrides: dict | None = None) -> Path:
    """Create plans/board.config.json plus the column tree; commit it."""
    config = dict(DEFAULT_CONFIG)
    config.update(config_overrides or {})
    plans = repo / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "board.config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    board_root = repo / config["board_root"]
    for column in [*config["columns"], "archive"]:
        directory = board_root / column
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").write_text("", encoding="utf-8")
    # Mirror what `kahnban init` writes, so tracked state matches production.
    (repo / ".gitignore").write_text(
        ".worktrees/\nplans/tickets/.artifacts/\nplans/tickets/.claim.lock\n",
        encoding="utf-8",
        newline="\n",
    )
    template = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "kahnban"
        / "templates"
        / "ticket.md"
    )
    if template.exists():
        (board_root / "template.md").write_text(
            template.read_text(encoding="utf-8"), encoding="utf-8"
        )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "scaffold board")
    return board_root


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    return init_repo(tmp_path / "scratch")


@pytest.fixture()
def board(repo: Path) -> Path:
    scaffold_board(repo)
    return repo
