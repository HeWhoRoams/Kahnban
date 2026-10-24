"""Regression tests for ponytail-audit production hardening fixes (Findings 1-14)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from kahnban import cli, core, dispatcher, frontmatter, gitops, handoff, linter, mcp_server, scaffold, skills
from conftest import set_board_config


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(r)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "AuditTest"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "audit@test.com"], check=True)
    scaffold.init_board(r, prefix="AUD", agentic=True)
    return r


def test_post_claim_hook_and_handoff_baton_in_worktree(repo: Path) -> None:
    """Finding 1: worktree_path was undefined in claim(); verify baton is written to worktree."""
    config = core.load_config(repo)
    ticket_file = repo / "plans" / "tickets" / "2-ready" / "AUD-001-feature.md"
    ticket_file.write_text(
        "---\nid: AUD-001\ntitle: Feature One\nstatus: ready\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Acceptance criteria\n- [ ] criterion 1\n\n## Blast radius\n- src/\n\n"
        "## Validation\n```bash\npython -c \"print(1)\"\n```\n\n"
        "## Log\n- 2026-10-22 ready\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket"], check=True)

    result = core.claim(config, "AUD-001", "coder-agent", create_worktree=True)
    assert result.to_column == "3-in-progress"
    assert not any("worktree_path" in m for m in result.messages)

    # Verify .agents/HANDOFF.json was written inside the provisioned worktree
    wt_dir = repo / ".worktrees" / "AUD-001"
    assert wt_dir.is_dir()
    baton_file = wt_dir / ".agents" / "HANDOFF.json"
    assert baton_file.is_file()
    baton_data = json.loads(baton_file.read_text(encoding="utf-8"))
    assert baton_data["ticket_id"] == "AUD-001"
    assert baton_data["assigned_role"] == "coder"


def test_cmd_feedback_no_name_error(repo: Path) -> None:
    """Finding 2: _project_root was undefined in cli.cmd_feedback(); feedback now rejects."""
    config = core.load_config(repo)
    ticket_file = repo / "plans" / "tickets" / "4-verifying" / "AUD-002-feedback.md"
    ticket_file.write_text(
        "---\nid: AUD-002\ntitle: Feature Two\nstatus: verifying\nowner: coder-agent\n"
        "created: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Acceptance criteria\n- [x] criterion 1\n\n## Blast radius\n- src/\n\n"
        "## Validation\n```bash\npython -c \"print(1)\"\n```\n\n"
        "## Log\n- 2026-10-22 verified\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket 2"], check=True)

    exit_code = cli.main(["--project-root", str(repo), "feedback", "AUD-002", "-m", "Fix the test asserts"])
    assert exit_code == 0
    ticket = core.find_ticket(config, "AUD-002")
    assert ticket.column == "3-in-progress"
    assert "Fix the test asserts" in core.section(frontmatter.parse(ticket.text)[1], "Log")


def test_skills_install_vscode_no_json_name_error(tmp_path: Path) -> None:
    """Finding 3: json was not imported in skills.py during vscode configuration."""
    test_repo = tmp_path / "vscode_repo"
    test_repo.mkdir()
    (test_repo / ".vscode").mkdir()
    res = skills.install_skills(test_repo, harness="vscode")
    assert res.ok is True
    mcp_config = test_repo / ".vscode" / "mcp.json"
    assert mcp_config.is_file()
    data = json.loads(mcp_config.read_text(encoding="utf-8"))
    assert "kahnban" in data["servers"]


def test_mcp_tool_next_no_load_config_name_error(repo: Path) -> None:
    """Finding 4: _load_config was called instead of _config in mcp_server.tool_next()."""
    res = mcp_server.tool_next(repo, {})
    assert res["ok"] is True
    assert "recommendation" in res
    assert "action" in res["recommendation"]


def test_transition_does_not_commit_unrelated_staged_files(repo: Path) -> None:
    """Finding 6: transition() must not commit foreign staged files into the board commit."""
    config = core.load_config(repo)
    # Developer stages an unfinished work file in the root repo
    unrelated_file = repo / "src_unrelated.py"
    unrelated_file.write_text("SECRET_DRAFT = True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "src_unrelated.py"], check=True)

    # Now create and transition a ticket
    draft = core.TicketDraft(title="Isolated Transition", problem="testing staged isolation")
    core.create_ticket(config, draft=draft)

    # The unrelated file should STILL be staged and NOT committed to HEAD
    status = gitops.status_porcelain(repo)
    assert any("src_unrelated.py" in line for line in status)
    head_files = gitops.diff_names(repo, "HEAD~1", "HEAD")
    assert "src_unrelated.py" not in head_files


def test_claim_local_flag_skips_remote(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 8: kahnban claim --local skips contacting remote origin."""
    config = core.load_config(repo)
    ticket_file = repo / "plans" / "tickets" / "2-ready" / "AUD-004-local.md"
    ticket_file.write_text(
        "---\nid: AUD-004\ntitle: Feature Four\nstatus: ready\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Acceptance criteria\n- [ ] pass\n\n## Blast radius\n- src/\n\n"
        "## Validation\n```bash\npython -c \"print(1)\"\n```\n\n"
        "## Log\n- 2026-10-22 ready\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket 4"], check=True)

    # Add a dummy remote origin
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git://invalid.example.com/repo.git"], check=True)

    called_pull = False
    def fake_pull(*a, **k):
        nonlocal called_pull
        called_pull = True
    monkeypatch.setattr(gitops, "pull_ff_only", fake_pull)

    # Calling with local=True should NOT call pull
    res = core.claim(config, "AUD-004", "agent", create_worktree=False, local=True)
    assert res.to_column == "3-in-progress"
    assert called_pull is False


def test_done_supports_squashed_merges(repo: Path) -> None:
    """Finding 9: kahnban done and linter accept branches whose content was squash-merged."""
    # A squash merged outside kahnban is exactly what require_integration forbids.
    set_board_config(repo, require_proof=False, require_review=False, require_integration=False)
    config = core.load_config(repo)
    ticket_file = repo / "plans" / "tickets" / "2-ready" / "AUD-005-squash.md"
    ticket_file.write_text(
        "---\nid: AUD-005\ntitle: Squash Feature\nstatus: ready\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Problem\nFeature problem.\n\n"
        "## Acceptance criteria\n- [ ] works (test: `python -c \"print('OK')\"`)\n\n"
        "## Blast radius\n- src/\n\n"
        "## Validation\n```bash\npython -c \"print('OK')\"\n```\n\n"
        "## Implementation notes\nImplemented feature 5 with squash.\n\n"
        "## Log\n- 2026-10-22 ready\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket 5"], check=True)

    core.claim(config, "AUD-005", "coder-agent", create_worktree=True)
    wt = repo / ".worktrees" / "AUD-005"
    (wt / "src").mkdir(parents=True, exist_ok=True)
    (wt / "src" / "feature5.py").write_text("squash_content = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
    subprocess.run(["git", "-C", str(wt), "commit", "-m", "feature 5 work"], check=True)

    core.verify(config, "AUD-005")

    # Simulate GitHub Squash & Merge on main (commit the exact same tree directly)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "feature5.py").write_text("squash_content = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Squashed commit for AUD-005 (#42)"], check=True)

    # Branch is NOT an ancestor in commit-graph, but tree diff against main is empty
    assert not gitops.is_ancestor(repo, "ticket/AUD-005", "main")
    res = core.done(config, "AUD-005")
    assert res.to_column == "5-done"

    # Linter BL15 should pass without errors
    lint_res = linter.lint(config)
    assert lint_res.ok is True


def test_blast_radius_does_not_exempt_the_test_directory(repo: Path) -> None:
    """Finding 10, reversed: an undeclared test change could weaken the proof."""
    config = core.load_config(repo)
    ticket_file = repo / "plans" / "tickets" / "2-ready" / "AUD-006-tdd.md"
    ticket_file.write_text(
        "---\nid: AUD-006\ntitle: TDD Feature\nstatus: ready\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Problem\nFeature problem.\n\n"
        "## Acceptance criteria\n- [ ] works\n\n"
        "## Blast radius\n- src/feature6.py\n\n"  # Only src/feature6.py declared
        "## Validation\n```bash\npython -c \"print('OK')\"\n```\n\n"
        "## Log\n- 2026-10-22 ready\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add ticket 6"], check=True)

    core.claim(config, "AUD-006", "coder-agent", create_worktree=True)
    wt = repo / ".worktrees" / "AUD-006"
    (wt / "src").mkdir(parents=True, exist_ok=True)
    (wt / "src" / "feature6.py").write_text("feature = 6\n", encoding="utf-8")
    (wt / "tests").mkdir(parents=True, exist_ok=True)
    (wt / "tests" / "test_feature6.py").write_text("def test_f(): pass\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
    subprocess.run(["git", "-C", str(wt), "commit", "-m", "code and tests"], check=True)

    with pytest.raises(core.GateError, match="tests/test_feature6.py"):
        core.verify(config, "AUD-006")


def test_dispatcher_prioritizes_non_conflicting_ready_ticket(repo: Path) -> None:
    """Finding 12: dispatcher selects non-conflicting ready ticket over colliding ticket."""
    config = core.load_config(repo)
    # Ticket 7 is in-progress touching src/ui/
    t7 = repo / "plans" / "tickets" / "3-in-progress" / "AUD-007-in-progress.md"
    t7.write_text(
        "---\nid: AUD-007\ntitle: UI Work\nstatus: in-progress\nowner: agent-a\nbranch: ticket/AUD-007\n"
        "created: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Acceptance criteria\n- [ ] works\n\n## Blast radius\n- src/ui/\n\n"
        "## Validation\n```bash\npython -c \"print(1)\"\n```\n\n"
        "## Log\n- 2026-10-22 work\n",
        encoding="utf-8",
    )
    # Ticket 8 is ready but conflicts with AUD-007 (touches src/ui/button.py)
    t8 = repo / "plans" / "tickets" / "2-ready" / "AUD-008-conflicting.md"
    t8.write_text(
        "---\nid: AUD-008\ntitle: UI Button\nstatus: ready\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Acceptance criteria\n- [ ] works\n\n## Blast radius\n- src/ui/button.py\n\n"
        "## Validation\n```bash\npython -c \"print(1)\"\n```\n\n"
        "## Log\n- 2026-10-22 ready\n",
        encoding="utf-8",
    )
    # Ticket 9 is ready and non-conflicting (touches game/engine/)
    t9 = repo / "plans" / "tickets" / "2-ready" / "AUD-009-free.md"
    t9.write_text(
        "---\nid: AUD-009\ntitle: Engine Work\nstatus: ready\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\n\n"
        "## Acceptance criteria\n- [ ] works\n\n## Blast radius\n- game/engine/\n\n"
        "## Validation\n```bash\npython -c \"print(1)\"\n```\n\n"
        "## Log\n- 2026-10-22 ready\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "setup dispatcher test"], check=True)

    rec = dispatcher.resolve_next_action(config, preferred_role="claim")
    assert rec.action == "claim_and_implement"
    # Should pick AUD-009 because AUD-008 conflicts with active AUD-007
    assert rec.ticket_id == "AUD-009"
