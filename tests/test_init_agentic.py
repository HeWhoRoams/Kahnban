"""Tests for agentic board scaffolding (kahnban init --agentic)."""

from __future__ import annotations

import json
from pathlib import Path

from kahnban import cli, core
from conftest import git


def test_init_board_agentic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "agent@example.com")
    git(repo, "config", "user.name", "Agent")

    written = core.init_board(repo, prefix="HOA", agentic=True)

    # 1. Kanban board files
    assert (repo / "plans" / "board.config.json").exists()
    assert (repo / "plans" / "tickets" / "0-backlog").is_dir()
    assert (repo / "plans" / "board.json").exists()
    assert (repo / "plans" / "STATUS.md").exists()

    # 2. .agents/ layout
    assert (repo / ".agents" / "AGENTS.md").exists()
    assert (repo / ".agents" / "state" / "ACTIVE_SESSION.md").exists()
    assert (repo / ".agents" / "specs").is_dir()
    assert (repo / ".agents" / "templates" / "spec-template.md").exists()
    assert (repo / ".agents" / "templates" / "ticket-template.md").exists()
    assert (repo / ".agents" / "templates" / "active-session-template.md").exists()
    assert (repo / ".agents" / "templates" / "glossary-template.md").exists()
    assert (repo / ".agents" / "templates" / "adr-template.md").exists()

    # 3. Root artifacts
    assert (repo / "GLOSSARY.md").exists()
    assert (repo / ".agents" / "skills" / "tdd" / "SKILL.md").exists()
    assert (repo / "ADR").is_dir()
    assert (repo / "ADR" / "0001-record-architecture-decisions.md").exists()

    # 4. .agents/skills/ self-contained suite
    assert (repo / ".agents" / "skills" / "grill-with-docs" / "SKILL.md").exists()
    assert (repo / ".agents" / "skills" / "to-spec" / "SKILL.md").exists()
    assert (repo / ".agents" / "skills" / "to-tickets" / "SKILL.md").exists()
    assert (repo / ".agents" / "skills" / "tdd" / "SKILL.md").exists()
    assert (repo / ".agents" / "skills" / "code-review" / "SKILL.md").exists()

    # 5. Git history: verify clean commit
    log = git(repo, "log", "--oneline").stdout.splitlines()
    assert len(log) == 1
    assert "initialize board (HOA)" in log[0]


def test_cli_init_agentic(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "cli_repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "agent@example.com")
    git(repo, "config", "user.name", "Agent")

    code = cli.main(
        [
            "--project-root",
            str(repo),
            "init",
            "--prefix",
            "CIT",
            "--agentic",
        ]
    )
    assert code == cli.EXIT_OK
    out, _ = capsys.readouterr()
    assert "[OK] initialized board in" in out
    assert "CIT" in out

    assert (repo / ".agents" / "AGENTS.md").exists()
    assert (repo / ".agents" / "state" / "ACTIVE_SESSION.md").exists()
    assert (repo / "GLOSSARY.md").exists()


def test_init_existing_repo_non_destructive(tmp_path: Path) -> None:
    repo = tmp_path / "existing_repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "developer@example.com")
    git(repo, "config", "user.name", "Dev")

    # Existing repo files
    (repo / ".gitignore").write_text("*.log\nnode_modules/\n", encoding="utf-8")
    src = repo / "src"
    src.mkdir()
    (src / "app.py").write_text("print('hello')", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "feat: existing app codebase")

    # Run init into existing repo
    written = core.init_board(repo, prefix="APP", agentic=True)

    # 1. Existing files intact
    assert (src / "app.py").read_text(encoding="utf-8") == "print('hello')"
    gitignore_content = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "*.log" in gitignore_content
    assert "node_modules/" in gitignore_content
    assert ".worktrees/" in gitignore_content

    # 2. Board and skills installed
    assert (repo / "plans" / "board.config.json").exists()
    assert (repo / ".agents" / "skills" / "tdd" / "SKILL.md").exists()
    assert (repo / ".agents" / "state" / "ACTIVE_SESSION.md").exists()

    # 3. Git commit history has exactly 2 commits
    log = git(repo, "log", "--oneline").stdout.splitlines()
    assert len(log) == 2
    assert "initialize board (APP)" in log[0]
    assert "feat: existing app codebase" in log[1]
