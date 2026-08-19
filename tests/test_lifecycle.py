"""End-to-end acceptance: init -> new -> ready -> claim -> verify -> done -> cleanup.

This is the plan §9 checklist exercised through the CLI on a scratch repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from kahnban import core, frontmatter, gitops, linter
from kahnban.cli import main
from conftest import git, init_repo, refine_ticket

VALIDATION = f'{sys.executable} -c "print(\'validation ok\')"'


def cli(repo: Path, *argv: str) -> int:
    return main(["--project-root", str(repo), *argv])


def refine(config: core.Config, ticket_id: str) -> None:
    refine_ticket(
        config, ticket_id, blast_radius=("src/widget.py",), validation=VALIDATION
    )


def test_full_ticket_lifecycle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = init_repo(tmp_path / "adopter")

    # 1. init -------------------------------------------------------------
    assert cli(repo, "init", "--prefix", "E2E") == 0
    config = core.load_config(repo)
    assert config.id_prefix == "E2E"

    # 2. new --------------------------------------------------------------
    assert cli(repo, "new", "Add the widget", "--problem", "There is no widget.") == 0
    assert core.find_ticket(config, "E2E-001").column == "0-backlog"
    refine(config, "E2E-001")

    # 3. refining -> ready ------------------------------------------------
    assert cli(repo, "move", "E2E-001", "1-refining", "--reason", "starting research") == 0
    assert cli(repo, "ready", "E2E-001") == 0
    assert core.find_ticket(config, "E2E-001").column == "2-ready"

    # 4. claim with an isolated worktree ----------------------------------
    assert cli(repo, "claim", "E2E-001", "--owner", "agent-a", "--worktree") == 0
    ticket = core.find_ticket(config, "E2E-001")
    assert ticket.column == "3-in-progress"
    fields, _ = frontmatter.parse(ticket.text)
    tree = repo / ".worktrees" / "E2E-001"
    assert fields["branch"] == "ticket/E2E-001"
    assert fields["worktree"] == ".worktrees/E2E-001"
    assert tree.is_dir()
    assert gitops.current_branch(repo) == "main"
    assert gitops.current_branch(tree) == "ticket/E2E-001"

    # 5. do the work inside the worktree, in scope -----------------------
    (tree / "src").mkdir(parents=True, exist_ok=True)
    (tree / "src" / "widget.py").write_text("def widget():\n    return 42\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "E2E-001: add the widget")

    # 6. verify runs the validation command itself ------------------------
    assert cli(repo, "verify", "E2E-001") == 0
    captured = capsys.readouterr().out
    assert "validation ok" in captured
    ticket = core.find_ticket(config, "E2E-001")
    assert ticket.column == "4-verifying"
    _, body = frontmatter.parse(ticket.text)
    assert "verify exit=0" in core.section(body, "Log")

    # 7. human review: check the boxes, merge, then done -------------------
    assert cli(repo, "done", "E2E-001") == 1  # criteria still unchecked
    core.write_text(ticket.path, core.read_text(ticket.path).replace("- [ ]", "- [x]"))
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "accept E2E-001")
    assert cli(repo, "done", "E2E-001") == 1  # branch not merged yet
    git(repo, "merge", "--no-ff", "-m", "merge ticket/E2E-001", "ticket/E2E-001")
    assert cli(repo, "done", "E2E-001") == 0
    assert core.find_ticket(config, "E2E-001").column == "5-done"

    # 8. cleanup ----------------------------------------------------------
    assert cli(repo, "cleanup", "E2E-001") == 0
    assert not tree.exists()
    assert not gitops.branch_exists(repo, "ticket/E2E-001")

    # 9. the board is clean and the projections agree ---------------------
    assert cli(repo, "lint") == 0
    result = linter.lint(config)
    assert result.violations == [] and result.warnings == []
    payload = json.loads((repo / "plans" / "status.json").read_text(encoding="utf-8"))
    done = next(entry for entry in payload["columns"] if entry["name"] == "5-done")
    assert [t["id"] for t in done["tickets"]] == ["E2E-001"]
    assert done["tickets"][0]["title"] == "Add the widget"
    markdown = (repo / "plans" / "STATUS.md").read_text(encoding="utf-8")
    assert "| 5-done | 1 |" in markdown
    assert gitops.status_porcelain(repo) == []
    assert (repo / "src" / "widget.py").is_file()

    # 10. the audit trail is complete and every board commit is on main ---
    final = core.find_ticket(config, "E2E-001")
    log_text = core.section(frontmatter.parse(final.text)[1], "Log")
    for expected in (
        "created -> 0-backlog",
        "manual move 0-backlog -> 1-refining",
        "ready gate passed -> 2-ready",
        "claimed by agent-a -> 3-in-progress",
        "verify exit=0",
        "done gate passed -> 5-done",
        "cleanup:",
    ):
        assert expected in log_text, expected
    subjects = git(repo, "log", "--pretty=%s", "main").stdout.splitlines()
    assert "kanban(E2E-001): 2-ready -> 3-in-progress" in subjects
    assert "kanban(E2E-001): 4-verifying -> 5-done" in subjects
    assert "kanban(E2E-001): cleanup" in subjects


def test_two_agents_work_disjoint_domains_concurrently(tmp_path: Path) -> None:
    """Two claims coexist when their declared domains do not intersect."""
    repo = init_repo(tmp_path / "adopter")
    assert cli(repo, "init", "--prefix", "E2E") == 0
    config = core.load_config(repo)

    for title, owned in (("Own the ui", "src/ui/"), ("Own the engine", "src/engine/")):
        assert cli(repo, "new", title) == 0
    for ticket_id, owned in (("E2E-001", "src/ui/"), ("E2E-002", "src/engine/")):
        refine_ticket(config, ticket_id, blast_radius=(owned,), validation=VALIDATION)
        assert cli(repo, "move", ticket_id, "1-refining", "--reason", "refining") == 0
        assert cli(repo, "ready", ticket_id) == 0
        assert cli(repo, "claim", ticket_id, "--owner", f"agent-{ticket_id}") == 0

    assert core.find_ticket(config, "E2E-001").column == "3-in-progress"
    assert core.find_ticket(config, "E2E-002").column == "3-in-progress"
    assert linter.lint(config).violations == []

    # A third ticket that reaches into a claimed domain is refused.
    assert cli(repo, "new", "Touch the ui too") == 0
    refine_ticket(
        config, "E2E-003", blast_radius=("src/ui/panel.py",), validation=VALIDATION
    )
    assert cli(repo, "move", "E2E-003", "1-refining", "--reason", "refining") == 0
    assert cli(repo, "ready", "E2E-003") == 0

    assert cli(repo, "claim", "E2E-003", "--owner", "agent-c") == 1
    assert core.find_ticket(config, "E2E-003").column == "2-ready"
