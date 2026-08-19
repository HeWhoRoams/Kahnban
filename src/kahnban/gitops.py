"""Git subprocess wrappers.

Every git invocation in Kahnban funnels through this module.  Two rules hold
without exception: arguments are always list-form (never a shell string), and a
non-zero exit raises :class:`GitError` carrying the command and stderr so the
failure is never swallowed.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git invocation exits non-zero."""

    def __init__(self, cmd: Sequence[str], returncode: int, stderr: str) -> None:
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stderr = (stderr or "").strip()
        rendered = " ".join(self.cmd)
        message = f"git command failed (exit {returncode}): {rendered}"
        if self.stderr:
            message = f"{message}\n{self.stderr}"
        super().__init__(message)


def run(
    repo: Path,
    args: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` inside ``repo``.

    Raises :class:`GitError` on a non-zero exit unless ``check`` is false.
    """
    cmd = ["git", "-C", str(repo), *args]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if check and completed.returncode != 0:
        raise GitError(cmd, completed.returncode, completed.stderr)
    return completed


def _out(repo: Path, args: Sequence[str]) -> str:
    return run(repo, args).stdout.strip()


# --- repository facts -------------------------------------------------------


def is_repo(path: Path) -> bool:
    completed = run(path, ["rev-parse", "--git-dir"], check=False)
    return completed.returncode == 0


def toplevel(path: Path) -> Path:
    return Path(_out(path, ["rev-parse", "--show-toplevel"]))


def current_branch(repo: Path) -> str:
    return _out(repo, ["rev-parse", "--abbrev-ref", "HEAD"])


def default_branch(repo: Path) -> str:
    """Best-effort default-branch name.

    Prefers ``origin/HEAD`` when a remote exists, then ``init.defaultBranch``,
    then the checked-out branch.
    """
    completed = run(repo, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], check=False)
    if completed.returncode == 0:
        ref = completed.stdout.strip()
        if ref.startswith("origin/"):
            return ref[len("origin/") :]
    for candidate in ("main", "master"):
        if branch_exists(repo, candidate):
            return candidate
    return current_branch(repo)


def main_worktree(repo: Path) -> Path:
    """The main working tree of ``repo``, even when called from a linked worktree."""
    completed = run(
        repo, ["rev-parse", "--path-format=absolute", "--git-common-dir"], check=False
    )
    if completed.returncode == 0:
        return Path(completed.stdout.strip()).parent
    common = Path(_out(repo, ["rev-parse", "--git-common-dir"]))
    if not common.is_absolute():
        common = (repo / common).resolve()
    return common.parent


def has_remote(repo: Path, name: str = "origin") -> bool:
    return name in run(repo, ["remote"]).stdout.split()


def branch_exists(repo: Path, name: str) -> bool:
    completed = run(
        repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{name}"], check=False
    )
    return completed.returncode == 0


def rev_parse(repo: Path, ref: str) -> str:
    return _out(repo, ["rev-parse", ref])


def commit_exists(repo: Path, sha: str) -> bool:
    completed = run(repo, ["cat-file", "-e", f"{sha}^{{commit}}"], check=False)
    return completed.returncode == 0


def is_ancestor(repo: Path, sha: str, branch: str) -> bool:
    """True when ``sha`` is reachable from ``branch``."""
    completed = run(repo, ["merge-base", "--is-ancestor", sha, branch], check=False)
    if completed.returncode in (0, 1):
        return completed.returncode == 0
    raise GitError(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, branch],
        completed.returncode,
        completed.stderr,
    )


def merge_base(repo: Path, left: str, right: str) -> str:
    return _out(repo, ["merge-base", left, right])


def diff_names(repo: Path, base: str, head: str) -> list[str]:
    output = _out(repo, ["diff", "--name-only", f"{base}..{head}"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def status_porcelain(repo: Path) -> list[str]:
    output = run(repo, ["status", "--porcelain"]).stdout
    return [line for line in output.splitlines() if line.strip()]


# --- mutations --------------------------------------------------------------


def mv(repo: Path, source: Path, destination: Path) -> None:
    run(repo, ["mv", str(source), str(destination)])


def add(repo: Path, paths: Iterable[Path | str]) -> None:
    rendered = [str(path) for path in paths]
    if not rendered:
        return
    run(repo, ["add", "--", *rendered])


def commit(repo: Path, message: str, *, allow_empty: bool = False) -> str:
    args = ["commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    run(repo, args)
    return rev_parse(repo, "HEAD")


def reset_hard(repo: Path, ref: str) -> None:
    run(repo, ["reset", "--hard", ref])


def branch(repo: Path, name: str, start_point: str) -> None:
    run(repo, ["branch", name, start_point])


def delete_branch(repo: Path, name: str, *, force: bool = False) -> None:
    run(repo, ["branch", "-D" if force else "-d", name])


def worktree_add(repo: Path, path: Path, branch_name: str) -> None:
    run(repo, ["worktree", "add", str(path), branch_name])


def worktree_remove(repo: Path, path: Path, *, force: bool = False) -> None:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    run(repo, args)


def worktree_prune(repo: Path) -> None:
    run(repo, ["worktree", "prune"])


def pull_ff_only(repo: Path, remote: str = "origin", branch_name: str | None = None) -> None:
    args = ["pull", "--ff-only", remote]
    if branch_name:
        args.append(branch_name)
    run(repo, args)


def push(repo: Path, remote: str = "origin", branch_name: str | None = None) -> None:
    args = ["push", remote]
    if branch_name:
        args.append(branch_name)
    run(repo, args)
