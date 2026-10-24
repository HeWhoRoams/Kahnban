"""Worktree provisioning, cache junctions, and deterministic teardown.

Heavy build caches (``.godot``, ``node_modules``) are shared into a ticket's
worktree with NTFS junctions on Windows and directory symlinks elsewhere.  Every
link created is reported back so the caller can record it in ticket frontmatter
(``junctions:``) — teardown then removes exactly those links, and removing a
link never touches the target directory (§3.4).
"""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kahnban import gitops


class WorktreeError(RuntimeError):
    """Raised when worktree or junction management fails."""


@dataclass
class WorktreeInfo:
    path: Path
    branch: str
    junctions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def branch_name(ticket_id: str) -> str:
    return f"ticket/{ticket_id}"


def worktree_path(project_root: Path, ticket_id: str) -> Path:
    return project_root / ".worktrees" / ticket_id


def is_link(path: Path) -> bool:
    """True for symlinks and (on Windows) NTFS junctions."""
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    # What os.path.isjunction (3.12+) checks; older Pythons have no isjunction.
    try:
        return os.lstat(path).st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    except OSError:
        return False


def create_link(target: Path, link: Path) -> None:
    """Link ``link`` -> ``target``: NTFS junction on Windows, symlink elsewhere."""
    if not target.exists():
        raise WorktreeError(f"cache target does not exist: {target}")
    if link.exists() or is_link(link):
        raise WorktreeError(f"link path already exists: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        try:
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
            return
        except OSError as error:
            raise WorktreeError(f"NTFS junction creation failed for {link}: {error}") from error
    os.symlink(target, link, target_is_directory=True)


def remove_link(link: Path) -> None:
    """Remove a junction or symlink without following it into the target."""
    if not is_link(link):
        raise WorktreeError(f"refusing to remove non-link path: {link}")
    try:
        os.rmdir(link)
    except OSError:
        os.unlink(link)


def link_caches(
    project_root: Path, destination: Path, shared_caches: Iterable[str]
) -> tuple[list[str], list[str]]:
    """Link each configured cache into ``destination``.

    Returns ``(created, warnings)`` where ``created`` holds the link paths
    relative to ``project_root``.  A cache that does not exist in the project is
    a warning, not a failure — adopters share the same config across machines.
    """
    created: list[str] = []
    warnings: list[str] = []
    for entry in shared_caches:
        relative = entry.replace("\\", "/").strip("/")
        if not relative:
            continue
        target = project_root / relative
        link = destination / relative
        if not target.exists():
            warnings.append(f"shared cache not found, skipped: {relative}")
            continue
        if link.exists() or is_link(link):
            warnings.append(f"cache link already present, skipped: {relative}")
            continue
        try:
            create_link(target, link)
        except WorktreeError as error:
            warnings.append(str(error))
            continue
        created.append(link.relative_to(project_root).as_posix())
    return created, warnings


def provision(
    project_root: Path,
    ticket_id: str,
    *,
    start_point: str,
    shared_caches: Sequence[str] = (),
) -> WorktreeInfo:
    """Create ``ticket/<ID>`` and ``.worktrees/<ID>``, then link shared caches."""
    branch = branch_name(ticket_id)
    destination = worktree_path(project_root, ticket_id)
    info = WorktreeInfo(path=destination, branch=branch)

    if destination.exists():
        raise WorktreeError(f"worktree path already exists: {destination}")

    if gitops.branch_exists(project_root, branch):
        info.warnings.append(f"branch {branch} already exists; reusing it")
    else:
        gitops.branch(project_root, branch, start_point)

    try:
        gitops.worktree_add(project_root, destination, branch)
    except gitops.GitError as error:
        raise WorktreeError(str(error)) from error

    created, warnings = link_caches(project_root, destination, shared_caches)
    info.junctions = created
    info.warnings.extend(warnings)
    return info


def teardown(
    project_root: Path,
    ticket_id: str,
    *,
    junctions: Iterable[str] = (),
    force: bool = False,
    delete_branch: bool = True,
) -> list[str]:
    """Remove junctions, then the worktree, then the ticket branch.

    Junctions come first: ``git worktree remove`` misbehaves when foreign
    junction content sits inside the worktree.  Returns human-readable notes.
    """
    notes: list[str] = []
    destination = worktree_path(project_root, ticket_id)

    for entry in junctions:
        relative = entry.replace("\\", "/").strip("/")
        if not relative:
            continue
        link = project_root / relative
        if not link.exists() and not is_link(link):
            notes.append(f"junction already gone: {relative}")
            continue
        try:
            remove_link(link)
        except WorktreeError as error:
            if not force:
                raise
            notes.append(f"junction removal skipped: {error}")
            continue
        notes.append(f"removed junction: {relative}")

    if destination.exists():
        removed = False
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                gitops.worktree_remove(project_root, destination, force=force)
                removed = True
                break
            except gitops.GitError as error:
                last_err = error
                time.sleep(0.5)
        if removed:
            notes.append(f"removed worktree: {destination.name}")
        else:
            if force:
                gitops.worktree_prune(project_root)
                notes.append(f"worktree removal delayed by file lock; pruned metadata: {destination.name}")
            else:
                raise WorktreeError(str(last_err)) from last_err
    else:
        gitops.worktree_prune(project_root)
        notes.append("no worktree to remove")

    branch = branch_name(ticket_id)
    if delete_branch and gitops.branch_exists(project_root, branch):
        try:
            gitops.delete_branch(project_root, branch, force=force)
        except gitops.GitError as error:
            raise WorktreeError(str(error)) from error
        notes.append(f"deleted branch: {branch}")

    return notes
