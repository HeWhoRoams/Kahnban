"""Gate behavior for claim, verify, done, move, and cleanup (plan §2.2, §3)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kahnban import core, frontmatter, gitops, worktree
from conftest import git, init_repo, scaffold_board, write_ticket


def commit_board(repo: Path, message: str = "board fixture") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def ticket_fields(path: Path) -> dict:
    fields, _ = frontmatter.parse(core.read_text(path))
    return fields


def log_of(path: Path) -> str:
    _, body = frontmatter.parse(core.read_text(path))
    return core.section(body, "Log")


# --- claim ------------------------------------------------------------------


def test_claim_moves_the_ticket_and_provisions_a_worktree(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    commit_board(board)

    result = core.claim(config, "TST-001", "copilot", create_worktree=True)

    assert result.to_column == "3-in-progress"
    fields = ticket_fields(result.path)
    assert fields["owner"] == "copilot"
    assert fields["branch"] == "ticket/TST-001"
    assert fields["worktree"] == ".worktrees/TST-001"
    assert (board / ".worktrees" / "TST-001" / "README.md").exists()
    assert gitops.branch_exists(board, "ticket/TST-001")
    # The board commit lands on the default branch, not the ticket branch (D2).
    assert gitops.current_branch(board) == "main"
    board_files = git(board, "show", "--name-only", "--pretty=format:", "main").stdout
    assert "plans/tickets/3-in-progress/TST-001-example.md" in board_files
    ticket_branch_files = git(
        board, "show", "--name-only", "--pretty=format:", "ticket/TST-001"
    ).stdout
    assert "plans/tickets/3-in-progress" not in ticket_branch_files


def test_claim_without_a_worktree_records_only_the_branch(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    commit_board(board)

    result = core.claim(config, "TST-001", "agent", create_worktree=False)

    assert ticket_fields(result.path)["branch"] == "ticket/TST-001"
    assert not (board / ".worktrees").exists()


def test_claim_refuses_tickets_outside_the_ready_column(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "1-refining", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="only 2-ready"):
        core.claim(config, "TST-001", "agent", create_worktree=False)


def test_claim_force_requires_a_reason_and_logs_it(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "1-refining", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="--force requires --reason"):
        core.claim(config, "TST-001", "agent", create_worktree=False, force=True)

    result = core.claim(
        config,
        "TST-001",
        "agent",
        create_worktree=False,
        force=True,
        reason="hotfix approved by owner",
    )

    assert "hotfix approved by owner" in log_of(result.path)


def test_claim_requires_an_owner(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="--owner is required"):
        core.claim(config, "TST-001", "   ", create_worktree=False)


def test_claim_refuses_unsatisfied_dependencies(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "dependency")
    write_ticket(
        config.board_path, "2-ready", "TST-002", "example", depends_on="[TST-001]"
    )
    commit_board(board)

    with pytest.raises(core.GateError, match="unsatisfied dependencies"):
        core.claim(config, "TST-002", "agent", create_worktree=False)


def test_claim_refuses_overlapping_blast_radius_and_names_the_conflict(
    board: Path,
) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "owner-of-ui",
        owner="agent-a",
        branch="ticket/TST-001",
        blast_radius=("src/ui/",),
    )
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-002",
        "wants-ui-panel",
        blast_radius=("src/ui/panel.py",),
    )
    commit_board(board)

    with pytest.raises(core.GateError) as error_info:
        core.claim(config, "TST-002", "agent-b", create_worktree=False)

    message = str(error_info.value)
    assert "TST-001" in message
    assert "src/ui/panel.py" in message
    assert core.find_ticket(config, "TST-002").column == "2-ready"


def test_claim_allows_disjoint_blast_radii(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "owner-of-ui",
        owner="agent-a",
        branch="ticket/TST-001",
        blast_radius=("src/ui/",),
    )
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-002",
        "owner-of-combat",
        blast_radius=("game/combat/targeting.py",),
    )
    commit_board(board)

    assert core.claim(config, "TST-002", "agent-b", create_worktree=False).to_column == (
        "3-in-progress"
    )


def test_force_overlap_requires_a_reason_and_logs_the_collision(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "owner-of-ui",
        owner="agent-a",
        branch="ticket/TST-001",
        blast_radius=("src/ui/",),
    )
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-002",
        "wants-ui",
        blast_radius=("src/ui/panel.py",),
    )
    commit_board(board)

    with pytest.raises(core.GateError, match="--force-overlap requires --reason"):
        core.claim(
            config, "TST-002", "agent-b", create_worktree=False, force_overlap=True
        )

    result = core.claim(
        config,
        "TST-002",
        "agent-b",
        create_worktree=False,
        force_overlap=True,
        reason="coordinated with agent-a",
    )

    entry = log_of(result.path)
    assert "coordinated with agent-a" in entry
    assert "TST-001" in entry


def test_wip_limit_warns_by_default_and_fails_with_strict(board: Path) -> None:
    scaffold_config = board / "plans" / "board.config.json"
    payload = json.loads(scaffold_config.read_text(encoding="utf-8"))
    payload["wip_limit"] = 1
    scaffold_config.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "busy",
        owner="agent-a",
        branch="ticket/TST-001",
        blast_radius=("src/a.py",),
    )
    write_ticket(config.board_path, "2-ready", "TST-002", "next", blast_radius=("src/b.py",))
    write_ticket(config.board_path, "2-ready", "TST-003", "later", blast_radius=("src/c.py",))
    commit_board(board)

    with pytest.raises(core.GateError, match="WIP limit 1 reached"):
        core.claim(config, "TST-002", "agent-b", create_worktree=False, strict_wip=True)

    result = core.claim(config, "TST-002", "agent-b", create_worktree=False)

    assert any("WIP limit" in message for message in result.messages)


def test_claim_holds_the_lock_for_the_whole_gate(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    commit_board(board)
    (config.board_path / core.LOCK_NAME).write_text("pid=999 at=now", encoding="utf-8")

    with pytest.raises(core.LockError):
        core.claim(config, "TST-001", "agent", create_worktree=False)


# --- concurrency (§3.3) -----------------------------------------------------

CLAIM_SCRIPT = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from kahnban import core

config = core.load_config(Path(sys.argv[2]))
try:
    result = core.claim(config, sys.argv[3], sys.argv[4], create_worktree=False)
except Exception as error:  # noqa: BLE001 - the loser must exit non-zero
    print(type(error).__name__ + ": " + str(error), file=sys.stderr)
    raise SystemExit(1)
print("claimed " + result.ticket_id)
"""


def test_parallel_claims_of_one_ticket_produce_exactly_one_winner(
    board: Path, tmp_path: Path
) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "contested")
    commit_board(board)
    script = tmp_path / "claim.py"
    script.write_text(CLAIM_SCRIPT, encoding="utf-8")
    source_root = str(Path(__file__).resolve().parents[1] / "src")

    processes = [
        subprocess.Popen(
            [sys.executable, str(script), source_root, str(board), "TST-001", owner],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for owner in ("agent-a", "agent-b")
    ]
    results = [(process.wait(timeout=120), *process.communicate()) for process in processes]

    winners = [result for result in results if result[0] == 0]
    losers = [result for result in results if result[0] != 0]
    assert len(winners) == 1, results
    assert len(losers) == 1, results
    assert losers[0][2].strip(), "the losing claim must explain itself on stderr"
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"
    assert not (config.board_path / core.LOCK_NAME).exists()


def test_distributed_claim_race_rolls_back_the_loser(tmp_path: Path) -> None:
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch", "main", str(bare)],
        capture_output=True,
        text=True,
        check=True,
    )
    upstream = init_repo(tmp_path / "upstream")
    board_root = scaffold_board(upstream)
    write_ticket(board_root, "2-ready", "TST-001", "contested")
    commit_board(upstream)
    git(upstream, "remote", "add", "origin", str(bare))
    gitops.push(upstream, "origin", "main")

    clones = []
    for name in ("clone-a", "clone-b"):
        subprocess.run(
            ["git", "clone", str(bare), str(tmp_path / name)],
            capture_output=True,
            text=True,
            check=True,
        )
        clone = tmp_path / name
        git(clone, "config", "user.name", "Kahnban Test")
        git(clone, "config", "user.email", "test@example.invalid")
        clones.append(clone)

    first = core.claim(
        core.load_config(clones[0]), "TST-001", "agent-a", create_worktree=False
    )
    assert first.to_column == "3-in-progress"

    # The second clone pulls before gating, so it sees the upstream claim and
    # refuses without ever creating a commit.
    config_b = core.load_config(clones[1])
    with pytest.raises(core.GateError, match="only 2-ready"):
        core.claim(config_b, "TST-001", "agent-b", create_worktree=False)

    assert gitops.status_porcelain(clones[1]) == []
    assert core.find_ticket(core.load_config(clones[1]), "TST-001").column == (
        "3-in-progress"
    )
    assert (
        git(clones[1], "log", "-1", "--pretty=%s").stdout.strip()
        == "kanban(TST-001): 2-ready -> 3-in-progress"
    )


def test_a_rejected_claim_push_is_rolled_back_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The narrow race window: the remote moves after our pull, before our push."""
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch", "main", str(bare)],
        capture_output=True,
        text=True,
        check=True,
    )
    upstream = init_repo(tmp_path / "upstream")
    board_root = scaffold_board(upstream)
    write_ticket(board_root, "2-ready", "TST-001", "contested")
    commit_board(upstream)
    git(upstream, "remote", "add", "origin", str(bare))
    gitops.push(upstream, "origin", "main")

    subprocess.run(
        ["git", "clone", str(bare), str(tmp_path / "loser")],
        capture_output=True,
        text=True,
        check=True,
    )
    loser = tmp_path / "loser"
    git(loser, "config", "user.name", "Kahnban Test")
    git(loser, "config", "user.email", "test@example.invalid")
    config = core.load_config(loser)
    before = git(loser, "rev-parse", "HEAD").stdout.strip()

    # The winner claims upstream while the loser is mid-gate: pulling is a no-op
    # for the loser, so its push is what discovers the loss.
    core.claim(core.load_config(upstream), "TST-001", "agent-a", create_worktree=False)
    gitops.push(upstream, "origin", "main")
    monkeypatch.setattr(core.gitops, "pull_ff_only", lambda *a, **k: None)

    with pytest.raises(core.GateError, match="lost the race"):
        core.claim(config, "TST-001", "agent-b", create_worktree=False)

    assert git(loser, "rev-parse", "HEAD").stdout.strip() == before
    assert gitops.status_porcelain(loser) == []
    assert core.find_ticket(config, "TST-001").column == "2-ready"


# --- verify (D4) ------------------------------------------------------------


def claimed_ticket(
    board: Path,
    *,
    validation: str = "git --version",
    blast_radius: tuple[str, ...] = ("src/feature.py",),
    worktree_flag: bool = True,
) -> core.Config:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "example",
        validation=validation,
        blast_radius=blast_radius,
    )
    commit_board(board)
    core.claim(config, "TST-001", "agent", create_worktree=worktree_flag)
    return config


def test_verify_runs_the_command_and_advances_on_success(board: Path) -> None:
    config = claimed_ticket(board)

    result = core.verify(config, "TST-001")

    assert result.passed
    assert result.exit_code == 0
    assert result.transition is not None
    assert result.transition.to_column == "4-verifying"
    entry = log_of(result.transition.path)
    assert "verify exit=0" in entry
    assert "git version" in entry
    assert result.artifact is not None and result.artifact.is_file()
    assert "git version" in result.artifact.read_text(encoding="utf-8")


def test_verify_blocks_on_a_non_zero_exit_and_still_logs(board: Path) -> None:
    config = claimed_ticket(board, validation="git rev-parse --verify no-such-ref")

    result = core.verify(config, "TST-001")

    assert not result.passed
    assert result.exit_code != 0
    ticket = core.find_ticket(config, "TST-001")
    assert ticket.column == "3-in-progress"
    assert "no transition" in log_of(ticket.path)
    assert gitops.status_porcelain(board) == []


def test_verify_refuses_diff_outside_the_blast_radius(board: Path) -> None:
    config = claimed_ticket(board, blast_radius=("src/feature.py",))
    tree = board / ".worktrees" / "TST-001"
    (tree / "src").mkdir(parents=True, exist_ok=True)
    (tree / "src" / "feature.py").write_text("ok = 1\n", encoding="utf-8")
    (tree / "unrelated.py").write_text("sneaky = 1\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "work plus scope creep")

    with pytest.raises(core.GateError) as error_info:
        core.verify(config, "TST-001")

    message = str(error_info.value)
    assert "unrelated.py" in message
    assert "src/feature.py" not in message.split("\n")[1]
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"


def test_verify_accepts_in_scope_diffs(board: Path) -> None:
    config = claimed_ticket(board, blast_radius=("src/",))
    tree = board / ".worktrees" / "TST-001"
    (tree / "src").mkdir(parents=True, exist_ok=True)
    (tree / "src" / "feature.py").write_text("ok = 1\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "in-scope work")

    assert core.verify(config, "TST-001").passed


def test_force_scope_requires_a_reason_and_logs_the_override(board: Path) -> None:
    config = claimed_ticket(board, blast_radius=("src/feature.py",))
    tree = board / ".worktrees" / "TST-001"
    (tree / "unrelated.py").write_text("sneaky = 1\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "scope creep")

    with pytest.raises(core.GateError, match="--force-scope requires --reason"):
        core.verify(config, "TST-001", force_scope=True)

    result = core.verify(
        config, "TST-001", force_scope=True, reason="radius amended next ticket"
    )

    assert result.passed
    assert result.transition is not None
    entry = log_of(result.transition.path)
    assert "radius amended next ticket" in entry
    assert "unrelated.py" in entry


def test_verify_output_cannot_forge_a_markdown_heading(board: Path) -> None:
    config = claimed_ticket(
        board, validation=sys.executable + ' -c "print(\'## Log\')"'
    )

    result = core.verify(config, "TST-001")

    assert result.passed
    assert result.transition is not None
    text = core.read_text(result.transition.path)
    _, body = frontmatter.parse(text)
    assert "    ## Log" in core.section(body, "Log")
    assert body.count("\n## Log") == 1


def test_verify_truncates_oversized_output_but_keeps_the_artifact(board: Path) -> None:
    config_path = board / "plans" / "board.config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["log_output_max_bytes"] = 200
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    command = sys.executable + ' -c "print(\'y\' * 5000)"'
    config = claimed_ticket(board, validation=command)

    result = core.verify(config, "TST-001")

    assert result.passed
    assert result.transition is not None
    assert "truncated" in log_of(result.transition.path)
    assert result.artifact is not None
    assert len(result.artifact.read_text(encoding="utf-8")) > 5000


def test_verify_manual_evidence_only_for_visual_deferred(
    board: Path, tmp_path: Path
) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "headless",
        extra_frontmatter="validation_class: headless-verified",
    )
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-002",
        "visual",
        blast_radius=("src/other.py",),
        extra_frontmatter="validation_class: visual-deferred",
    )
    commit_board(board)
    core.claim(config, "TST-001", "agent", create_worktree=False)
    core.claim(config, "TST-002", "agent", create_worktree=False)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("screenshot compared by hand\n", encoding="utf-8")

    with pytest.raises(core.GateError, match="visual-deferred"):
        core.verify(config, "TST-001", manual_evidence=evidence)

    result = core.verify(config, "TST-002", manual_evidence=evidence)

    assert result.passed
    assert result.transition is not None
    entry = log_of(result.transition.path)
    assert "MANUAL-EVIDENCE (unverified)" in entry
    assert "screenshot compared by hand" in entry


def test_verify_requires_the_in_progress_column(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="verify applies to 3-in-progress"):
        core.verify(config, "TST-001")


# --- done -------------------------------------------------------------------


def verified_ticket(board: Path) -> core.Config:
    config = claimed_ticket(board)
    tree = board / ".worktrees" / "TST-001"
    (tree / "src").mkdir(parents=True, exist_ok=True)
    (tree / "src" / "feature.py").write_text("ok = 1\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "ticket work")
    assert core.verify(config, "TST-001").passed
    return config


def check_all_boxes(config: core.Config, ticket_id: str) -> None:
    ticket = core.find_ticket(config, ticket_id)
    text = core.read_text(ticket.path).replace("- [ ]", "- [x]")
    core.write_text(ticket.path, text)
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", "check acceptance boxes")


def test_done_refuses_an_unmerged_branch(board: Path) -> None:
    config = verified_ticket(board)
    check_all_boxes(config, "TST-001")

    with pytest.raises(core.GateError, match="not merged"):
        core.done(config, "TST-001")

    assert core.find_ticket(config, "TST-001").column == "4-verifying"


def test_done_refuses_unchecked_criteria(board: Path) -> None:
    config = verified_ticket(board)
    git(board, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")

    with pytest.raises(core.GateError, match="still unchecked"):
        core.done(config, "TST-001")


def test_done_accepts_a_merged_branch(board: Path) -> None:
    config = verified_ticket(board)
    check_all_boxes(config, "TST-001")
    git(board, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")

    result = core.done(config, "TST-001")

    assert result.to_column == "5-done"
    assert "merge-commit:" in log_of(result.path)


def test_done_accepts_a_verified_merge_commit_for_a_deleted_branch(board: Path) -> None:
    config = verified_ticket(board)
    check_all_boxes(config, "TST-001")
    git(board, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")
    merge_sha = git(board, "rev-parse", "HEAD").stdout.strip()
    worktree.teardown(board, "TST-001", junctions=(), force=True)

    result = core.done(config, "TST-001", merge_commit=merge_sha)

    assert result.to_column == "5-done"
    assert merge_sha[:12] in log_of(result.path)


def test_done_rejects_a_merge_commit_that_is_not_on_the_default_branch(
    board: Path,
) -> None:
    config = verified_ticket(board)
    check_all_boxes(config, "TST-001")
    unmerged = git(board, "rev-parse", "ticket/TST-001").stdout.strip()

    with pytest.raises(core.GateError, match="is not on 'main'"):
        core.done(config, "TST-001", merge_commit=unmerged)

    with pytest.raises(core.GateError, match="does not exist"):
        core.done(config, "TST-001", merge_commit="0" * 40)


# --- move and cleanup -------------------------------------------------------


def test_move_requires_a_reason_and_logs_it(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="--reason is required"):
        core.move(config, "TST-001", "4-verifying", reason="  ")

    result = core.move(config, "TST-001", "4-verifying", reason="rescued from a crash")

    assert result.to_column == "4-verifying"
    assert "rescued from a crash" in log_of(result.path)


def test_move_can_archive_a_ticket(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    result = core.move(config, "TST-001", "archive", reason="superseded")

    assert result.path.parent.name == "archive"
    assert core.next_id(config) == "TST-002"


def test_cleanup_removes_worktree_and_branch_and_clears_fields(board: Path) -> None:
    config = verified_ticket(board)
    check_all_boxes(config, "TST-001")
    git(board, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")
    core.done(config, "TST-001")

    result = core.cleanup(config, "TST-001")

    assert not (board / ".worktrees" / "TST-001").exists()
    assert not gitops.branch_exists(board, "ticket/TST-001")
    fields = ticket_fields(result.path)
    assert fields["branch"] == ""
    assert fields["worktree"] == ""
    assert fields["junctions"] == []
    assert result.to_column == "5-done"
    assert gitops.status_porcelain(board) == []


def test_cleanup_refuses_outside_the_done_column_without_abandon(board: Path) -> None:
    config = claimed_ticket(board)

    with pytest.raises(core.GateError, match="--abandon"):
        core.cleanup(config, "TST-001")

    with pytest.raises(core.GateError, match="--abandon requires --reason"):
        core.cleanup(config, "TST-001", abandon=True)

    result = core.cleanup(config, "TST-001", abandon=True, reason="approach rejected")

    assert "approach rejected" in log_of(result.path)
    assert not (board / ".worktrees" / "TST-001").exists()
    assert not gitops.branch_exists(board, "ticket/TST-001")


@pytest.mark.skipif(os.name != "nt", reason="NTFS junctions are Windows-only")
def test_cleanup_removes_junctions_without_touching_the_target(board: Path) -> None:
    config_path = board / "plans" / "board.config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["shared_caches"] = [".cache"]
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Real shared caches are gitignored build output, so they are never checked
    # out into a worktree — the junction is the only copy inside it.
    gitignore = board / ".gitignore"
    gitignore.write_text(
        gitignore.read_text(encoding="utf-8") + ".cache/\n", encoding="utf-8"
    )
    cache = board / ".cache"
    cache.mkdir()
    (cache / "heavy.bin").write_text("payload\n", encoding="utf-8")

    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    commit_board(board)
    claim = core.claim(config, "TST-001", "agent", create_worktree=True)

    junctions = ticket_fields(claim.path)["junctions"]
    assert junctions == [".worktrees/TST-001/.cache"]
    linked = board / ".worktrees" / "TST-001" / ".cache" / "heavy.bin"
    assert linked.read_text(encoding="utf-8") == "payload\n"

    core.cleanup(config, "TST-001", abandon=True, reason="test teardown")

    assert (cache / "heavy.bin").read_text(encoding="utf-8") == "payload\n"
    assert not (board / ".worktrees" / "TST-001").exists()
