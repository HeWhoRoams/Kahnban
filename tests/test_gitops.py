from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kahnban import gitops
from conftest import git, init_repo


def test_run_surfaces_stderr_in_git_error(repo: Path) -> None:
    with pytest.raises(gitops.GitError) as error_info:
        gitops.run(repo, ["checkout", "does-not-exist"])

    error = error_info.value
    assert error.returncode != 0
    assert error.stderr
    assert "does-not-exist" in str(error)


def test_run_never_uses_a_shell(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    original = subprocess.run

    def spy(cmd, **kwargs):  # type: ignore[no-untyped-def]
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return original(cmd, **kwargs)

    monkeypatch.setattr(gitops.subprocess, "run", spy)
    gitops.current_branch(repo)

    assert isinstance(seen["cmd"], list)
    assert seen["kwargs"].get("shell") is None


def test_repo_facts(repo: Path) -> None:
    assert gitops.is_repo(repo)
    assert gitops.current_branch(repo) == "main"
    assert gitops.default_branch(repo) == "main"
    assert not gitops.has_remote(repo)
    assert gitops.toplevel(repo).resolve() == repo.resolve()


def test_mv_add_commit_round_trip(repo: Path) -> None:
    source = repo / "a.txt"
    source.write_text("hello\n", encoding="utf-8")
    gitops.add(repo, ["a.txt"])
    first = gitops.commit(repo, "add a")

    gitops.mv(repo, Path("a.txt"), Path("b.txt"))
    second = gitops.commit(repo, "rename a -> b")

    assert first != second
    assert not (repo / "a.txt").exists()
    assert (repo / "b.txt").read_text(encoding="utf-8") == "hello\n"
    assert gitops.status_porcelain(repo) == []


def test_branch_ancestor_and_diff_helpers(repo: Path) -> None:
    gitops.branch(repo, "ticket/TST-001", "main")
    assert gitops.branch_exists(repo, "ticket/TST-001")

    git(repo, "checkout", "ticket/TST-001")
    (repo / "src").mkdir()
    (repo / "src" / "feature.py").write_text("x = 1\n", encoding="utf-8")
    gitops.add(repo, ["src/feature.py"])
    tip = gitops.commit(repo, "feature work")
    git(repo, "checkout", "main")

    base = gitops.merge_base(repo, "main", "ticket/TST-001")
    assert gitops.diff_names(repo, base, "ticket/TST-001") == ["src/feature.py"]
    assert not gitops.is_ancestor(repo, tip, "main")
    assert gitops.commit_exists(repo, tip)

    git(repo, "merge", "--ff-only", "ticket/TST-001")
    assert gitops.is_ancestor(repo, tip, "main")

    gitops.delete_branch(repo, "ticket/TST-001")
    assert not gitops.branch_exists(repo, "ticket/TST-001")


def test_commit_exists_is_false_for_unknown_sha(repo: Path) -> None:
    assert not gitops.commit_exists(repo, "0" * 40)


def test_worktree_add_and_remove(repo: Path) -> None:
    gitops.branch(repo, "ticket/TST-002", "main")
    worktree = repo / ".worktrees" / "TST-002"
    gitops.worktree_add(repo, worktree, "ticket/TST-002")

    assert (worktree / "README.md").exists()

    gitops.worktree_remove(repo, worktree)
    assert not worktree.exists()


def _bare_remote(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch", "main", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return path


def _clone(source: Path, destination: Path) -> Path:
    subprocess.run(
        ["git", "clone", str(source), str(destination)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(destination, "config", "user.name", "Kahnban Test")
    git(destination, "config", "user.email", "test@example.invalid")
    return destination


def test_push_and_pull_against_a_local_bare_remote(tmp_path: Path) -> None:
    bare = _bare_remote(tmp_path / "origin.git")
    clone_a = init_repo(tmp_path / "a")
    git(clone_a, "remote", "add", "origin", str(bare))
    gitops.push(clone_a, "origin", "main")
    assert gitops.has_remote(clone_a)

    clone_b = _clone(bare, tmp_path / "b")

    (clone_a / "second.txt").write_text("2\n", encoding="utf-8")
    gitops.add(clone_a, ["second.txt"])
    gitops.commit(clone_a, "second")
    gitops.push(clone_a, "origin", "main")

    gitops.pull_ff_only(clone_b, "origin", "main")
    assert (clone_b / "second.txt").exists()


def test_pull_ff_only_and_push_refuse_divergence(tmp_path: Path) -> None:
    bare = _bare_remote(tmp_path / "origin.git")
    clone_a = init_repo(tmp_path / "a")
    git(clone_a, "remote", "add", "origin", str(bare))
    gitops.push(clone_a, "origin", "main")
    clone_b = _clone(bare, tmp_path / "b")

    for clone, name in ((clone_a, "a.txt"), (clone_b, "b.txt")):
        (clone / name).write_text("x\n", encoding="utf-8")
        gitops.add(clone, [name])
        gitops.commit(clone, "add " + name)
    gitops.push(clone_a, "origin", "main")

    with pytest.raises(gitops.GitError):
        gitops.pull_ff_only(clone_b, "origin", "main")

    with pytest.raises(gitops.GitError):
        gitops.push(clone_b, "origin", "main")
