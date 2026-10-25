"""The refusals and fallbacks in worktree provisioning and teardown."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import gitops, worktree


def git_error() -> gitops.GitError:
    return gitops.GitError(["git", "worktree"], 1, "locked by another process")


def make_cache(root: Path, name: str = "node_modules") -> Path:
    cache = root / name
    cache.mkdir()
    (cache / "package.txt").write_text("kept\n", encoding="utf-8")
    return cache


# --- links ---------------------------------------------------------------------


def test_a_link_needs_a_target_and_a_free_path(tmp_path: Path) -> None:
    target = make_cache(tmp_path)

    with pytest.raises(worktree.WorktreeError, match="does not exist"):
        worktree.create_link(tmp_path / "nowhere", tmp_path / "link")
    worktree.create_link(target, tmp_path / "link")
    with pytest.raises(worktree.WorktreeError, match="already exists"):
        worktree.create_link(target, tmp_path / "link")

    assert worktree.is_link(tmp_path / "link")
    assert not worktree.is_link(target)


def test_removing_a_link_never_touches_what_it_points_at(tmp_path: Path) -> None:
    target = make_cache(tmp_path)
    worktree.create_link(target, tmp_path / "link")

    worktree.remove_link(tmp_path / "link")

    assert not (tmp_path / "link").exists()
    assert (target / "package.txt").read_text(encoding="utf-8") == "kept\n"
    with pytest.raises(worktree.WorktreeError, match="non-link"):
        worktree.remove_link(target)


def test_link_caches_skips_blanks_missing_and_present_entries_and_reports_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    destination = root / ".worktrees" / "TST-001"
    destination.mkdir(parents=True)
    make_cache(root, "present")
    make_cache(root, "taken")
    (destination / "taken").mkdir()
    make_cache(root, "broken")

    real = worktree.create_link

    def flaky(target: Path, link: Path) -> None:
        if link.name == "broken":
            raise worktree.WorktreeError("cannot link broken")
        real(target, link)

    monkeypatch.setattr(worktree, "create_link", flaky)

    created, warnings = worktree.link_caches(root, destination, ["", "/", "present", "absent", "taken", "broken"])

    assert created == [".worktrees/TST-001/present"]
    assert any("not found, skipped: absent" in w for w in warnings)
    assert any("already present, skipped: taken" in w for w in warnings)
    assert "cannot link broken" in warnings


# --- provision -------------------------------------------------------------------


def test_provision_refuses_an_existing_path_and_reuses_an_existing_branch(repo: Path) -> None:
    (repo / ".worktrees" / "TST-001").mkdir(parents=True)
    with pytest.raises(worktree.WorktreeError, match="already exists"):
        worktree.provision(repo, "TST-001", start_point="main")

    (repo / ".worktrees" / "TST-001").rmdir()
    gitops.branch(repo, "ticket/TST-001", "main")
    info = worktree.provision(repo, "TST-001", start_point="main")

    assert any("already exists; reusing it" in w for w in info.warnings)


def test_provision_turns_a_git_failure_into_a_worktree_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise git_error()

    monkeypatch.setattr(gitops, "worktree_add", fail)

    with pytest.raises(worktree.WorktreeError, match="locked by another process"):
        worktree.provision(repo, "TST-001", start_point="main")


# --- teardown ---------------------------------------------------------------------


def test_teardown_notes_a_junction_that_is_already_gone_and_one_that_is_not_a_link(repo: Path) -> None:
    worktree.provision(repo, "TST-001", start_point="main")
    (repo / "plain-dir").mkdir()

    with pytest.raises(worktree.WorktreeError, match="non-link"):
        worktree.teardown(repo, "TST-001", junctions=["plain-dir"])

    notes = worktree.teardown(repo, "TST-001", junctions=["", "gone"], force=True)

    assert "junction already gone: gone" in notes
    assert any(n.startswith("removed worktree") for n in notes)
    assert any(n.startswith("deleted branch") for n in notes)


def test_teardown_with_force_skips_a_junction_it_cannot_remove(repo: Path) -> None:
    worktree.provision(repo, "TST-001", start_point="main")
    (repo / "plain-dir").mkdir()

    notes = worktree.teardown(repo, "TST-001", junctions=["plain-dir"], force=True)

    assert any("junction removal skipped" in n for n in notes)


def test_a_locked_worktree_is_retried_then_reported_or_pruned_under_force(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree.provision(repo, "TST-001", start_point="main")
    attempts: list[int] = []

    def locked(*args: object, **kwargs: object) -> None:
        attempts.append(1)
        raise git_error()

    monkeypatch.setattr(gitops, "worktree_remove", locked)
    monkeypatch.setattr(worktree.time, "sleep", lambda seconds: None)

    with pytest.raises(worktree.WorktreeError, match="locked by another process"):
        worktree.teardown(repo, "TST-001")
    assert len(attempts) == 3

    # Forced, the metadata is pruned; git still sees the directory, so the branch cannot go.
    with pytest.raises(worktree.WorktreeError, match="used by worktree"):
        worktree.teardown(repo, "TST-001", force=True)


def test_a_branch_git_will_not_delete_is_an_error_and_a_missing_worktree_is_a_note(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gitops.branch(repo, "ticket/TST-001", "main")
    assert "no worktree to remove" in worktree.teardown(repo, "TST-001", delete_branch=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise git_error()

    monkeypatch.setattr(gitops, "delete_branch", refuse)
    with pytest.raises(worktree.WorktreeError):
        worktree.teardown(repo, "TST-001")
