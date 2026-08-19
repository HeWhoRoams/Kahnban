"""Worktree provisioning and junction-safe teardown (plan §3.2 step 5, §3.4)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kahnban import gitops, worktree


def test_naming_helpers(tmp_path: Path) -> None:
    assert worktree.branch_name("TST-001") == "ticket/TST-001"
    assert worktree.worktree_path(tmp_path, "TST-001") == tmp_path / ".worktrees" / "TST-001"


def test_provision_creates_branch_and_worktree(repo: Path) -> None:
    info = worktree.provision(repo, "TST-001", start_point="main")

    assert info.branch == "ticket/TST-001"
    assert info.path == repo / ".worktrees" / "TST-001"
    assert (info.path / "README.md").exists()
    assert gitops.branch_exists(repo, "ticket/TST-001")
    assert info.junctions == []


def test_provision_refuses_an_existing_worktree_path(repo: Path) -> None:
    worktree.provision(repo, "TST-001", start_point="main")

    with pytest.raises(worktree.WorktreeError, match="already exists"):
        worktree.provision(repo, "TST-001", start_point="main")


def test_provision_reuses_an_existing_branch_with_a_warning(repo: Path) -> None:
    gitops.branch(repo, "ticket/TST-001", "main")

    info = worktree.provision(repo, "TST-001", start_point="main")

    assert any("already exists" in warning for warning in info.warnings)
    assert info.path.exists()


def test_provision_warns_about_missing_shared_caches(repo: Path) -> None:
    info = worktree.provision(
        repo, "TST-001", start_point="main", shared_caches=[".no-such-cache"]
    )

    assert info.junctions == []
    assert any("not found" in warning for warning in info.warnings)


def test_link_caches_creates_a_shared_link(repo: Path) -> None:
    cache = repo / ".cache"
    cache.mkdir()
    (cache / "heavy.bin").write_text("payload\n", encoding="utf-8")
    destination = repo / ".worktrees" / "TST-001"
    destination.mkdir(parents=True)

    created, warnings = worktree.link_caches(repo, destination, [".cache"])

    assert created == [".worktrees/TST-001/.cache"]
    assert warnings == []
    assert worktree.is_link(destination / ".cache")
    assert (destination / ".cache" / "heavy.bin").read_text(encoding="utf-8") == "payload\n"


def test_remove_link_leaves_the_target_intact(repo: Path) -> None:
    cache = repo / ".cache"
    cache.mkdir()
    (cache / "heavy.bin").write_text("payload\n", encoding="utf-8")
    link = repo / "linked-cache"
    worktree.create_link(cache, link)

    worktree.remove_link(link)

    assert not link.exists()
    assert (cache / "heavy.bin").read_text(encoding="utf-8") == "payload\n"


def test_remove_link_refuses_a_real_directory(repo: Path) -> None:
    real = repo / "not-a-link"
    real.mkdir()

    with pytest.raises(worktree.WorktreeError, match="non-link"):
        worktree.remove_link(real)

    assert real.is_dir()


def test_create_link_refuses_to_clobber(repo: Path) -> None:
    cache = repo / ".cache"
    cache.mkdir()
    occupied = repo / "occupied"
    occupied.mkdir()

    with pytest.raises(worktree.WorktreeError, match="already exists"):
        worktree.create_link(cache, occupied)

    with pytest.raises(worktree.WorktreeError, match="does not exist"):
        worktree.create_link(repo / "missing", repo / "new-link")


def test_teardown_removes_junctions_then_worktree_then_branch(repo: Path) -> None:
    cache = repo / ".cache"
    cache.mkdir()
    (cache / "heavy.bin").write_text("payload\n", encoding="utf-8")
    info = worktree.provision(
        repo, "TST-001", start_point="main", shared_caches=[".cache"]
    )
    assert info.junctions == [".worktrees/TST-001/.cache"]

    notes = worktree.teardown(repo, "TST-001", junctions=info.junctions)

    assert not info.path.exists()
    assert not gitops.branch_exists(repo, "ticket/TST-001")
    assert (cache / "heavy.bin").read_text(encoding="utf-8") == "payload\n"
    assert any("junction" in note for note in notes)
    assert any("worktree" in note for note in notes)
    assert any("branch" in note for note in notes)


def test_teardown_is_idempotent_for_missing_pieces(repo: Path) -> None:
    notes = worktree.teardown(repo, "TST-404", junctions=[".worktrees/TST-404/.cache"])

    assert any("already gone" in note for note in notes)
    assert any("no worktree" in note for note in notes)


def test_teardown_of_unmerged_work_needs_force(repo: Path) -> None:
    info = worktree.provision(repo, "TST-001", start_point="main")
    (info.path / "scratch.txt").write_text("work in flight\n", encoding="utf-8")
    gitops.run(info.path, ["add", "-A"])
    gitops.run(info.path, ["commit", "-m", "unmerged work"])

    with pytest.raises(worktree.WorktreeError):
        worktree.teardown(repo, "TST-001")

    notes = worktree.teardown(repo, "TST-001", force=True)

    assert not info.path.exists()
    assert not gitops.branch_exists(repo, "ticket/TST-001")
    assert notes


@pytest.mark.skipif(os.name != "nt", reason="NTFS junctions are Windows-only")
def test_windows_links_are_junctions_not_symlinks(repo: Path) -> None:
    cache = repo / ".cache"
    cache.mkdir()
    link = repo / "linked"
    worktree.create_link(cache, link)

    assert os.path.isjunction(link)
    assert not os.path.islink(link)
