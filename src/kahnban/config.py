"""Board configuration: the config file, the errors every gate raises, and who is running.

``Config`` is read from ``plans/board.config.json``. The error classes live here so every
module can raise and catch them without importing the gates in :mod:`kahnban.core`, which
re-exports all of these names.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from kahnban import __version__, gitops

ENV_ROLE = "KAHNBAN_ROLE"
ENV_TICKET = "KAHNBAN_TICKET"
ENV_PROJECT_ROOT = "KAHNBAN_PROJECT_ROOT"
ENV_WORKTREE = "KAHNBAN_WORKTREE"


def project_root_from_env(env: Mapping[str, str]) -> Path:
    """The project a worker was started for (``KAHNBAN_PROJECT_ROOT``), or the current directory."""
    return Path(env.get(ENV_PROJECT_ROOT, ".")).resolve()

def worker_role() -> str:
    """The role of the factory worker this process runs under, or '' for a person.

    The one place the engine reads it: ``ready``, ``approve`` and the attended gates all
    treat a worker differently from a person, and the guard refuses any command that
    would clear or change this variable.
    """
    return os.environ.get(ENV_ROLE, "").strip()

class Autonomy:
    """``autonomy`` in board.config.json: whether the runner may take every gate itself."""

    UNATTENDED = "unattended"
    ATTENDED = "attended"

class HumanGate:
    """The gates an attended run can hand to a person."""

    READY = "ready"
    MERGE = "merge"

AUTONOMY_MODES = (Autonomy.UNATTENDED, Autonomy.ATTENDED)

HUMAN_GATES = {HumanGate.READY, HumanGate.MERGE}

CONFIG_RELATIVE = Path("plans") / "board.config.json"

DEFAULT_COLUMNS = (
    "0-backlog",
    "1-refining",
    "2-ready",
    "3-in-progress",
    "4-verifying",
    "5-done",
)

DEFAULT_REQUIRED_HEADINGS = (
    "Problem",
    "Acceptance criteria",
    "Blast radius",
    "Implementation notes",
    "Validation",
    "Log",
)

# Matched against the full path and the file name, case-insensitively.
DEFAULT_TEST_PATTERNS = (
    "tests/*",
    "test/*",
    "spec/*",
    "*/tests/*",
    "*/test/*",
    "*/spec/*",
    "*/__tests__/*",
    "test_*",
    "*_test.*",
    "*.test.*",
    "*.spec.*",
    "*_spec.*",
)

class KahnbanError(RuntimeError):
    """Base class for every Kahnban failure surfaced to a client."""

class ConfigError(KahnbanError):
    """Configuration is missing, malformed, or too old for this engine."""

class TicketNotFoundError(KahnbanError):
    """No ticket file matches the requested ID."""

class GateError(KahnbanError):
    """A transition was refused because a gate is not satisfied."""

class LockError(KahnbanError):
    """The board claim lock is held by another process."""

@dataclass(frozen=True)
class Config:
    project_root: Path
    path: Path
    engine_min_version: str = "0.0.0"
    id_prefix: str = "TKT"
    board_root: str = "plans/tickets"
    columns: tuple[str, ...] = DEFAULT_COLUMNS
    done_column: str = "5-done"
    wip_limit: int = 3
    use_worktrees: bool = True
    shared_caches: tuple[str, ...] = ()
    validation_timeout_sec: int = 1800
    log_output_max_bytes: int = 65536
    required_headings: tuple[str, ...] = DEFAULT_REQUIRED_HEADINGS
    validation_command: str = ""
    regression_command: str = ""
    design_doc_roots: tuple[str, ...] = ("plans",)
    extensions: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    ingest: Mapping[str, object] = field(default_factory=dict)
    allow_any_branch: bool = False
    sync_remote: bool = True
    require_proof: bool = False
    require_review: bool = False
    require_integration: bool = False
    require_spec: bool = False
    max_blast_radius_files: int = 0
    stale_after_days: int = 0
    test_patterns: tuple[str, ...] = DEFAULT_TEST_PATTERNS
    allowed_commands: tuple[str, ...] = ()
    lease_minutes: int = 30
    workers: Mapping[str, str] = field(default_factory=dict)
    worker_timeout_sec: int = 3600
    max_attempts: int = 3
    max_stop_nudges: int = 2
    strict_hooks: bool = False
    autonomy: str = Autonomy.UNATTENDED
    human_gates: tuple[str, ...] = (HumanGate.MERGE,)
    require_signed_approvals: bool = False

    @property
    def board_path(self) -> Path:
        return self.project_root / self.board_root

    @property
    def plans_dir(self) -> Path:
        return self.path.parent

    @property
    def archive_path(self) -> Path:
        return self.board_path / "archive"

    @property
    def in_progress_column(self) -> str:
        return self._column_at(3, "3-in-progress")

    @property
    def ready_column(self) -> str:
        return self._column_at(2, "2-ready")

    @property
    def refining_column(self) -> str:
        return self._column_at(1, "1-refining")

    @property
    def verifying_column(self) -> str:
        return self._column_at(4, "4-verifying")

    @property
    def backlog_column(self) -> str:
        return self._column_at(0, "0-backlog")

    def _column_at(self, index: int, fallback: str) -> str:
        if fallback in self.columns:
            return fallback
        if index < len(self.columns):
            return self.columns[index]
        raise ConfigError(f"config has no column at position {index}")

    def column_index(self, column: str) -> int:
        try:
            return self.columns.index(column)
        except ValueError as error:
            raise ConfigError(f"unknown column: {column}") from error

    def is_at_or_after(self, column: str, reference: str) -> bool:
        return self.column_index(column) >= self.column_index(reference)

    def status_for(self, column: str) -> str:
        return status_name(column)

def status_name(column: str) -> str:
    """``3-in-progress`` -> ``in-progress``; ``archive`` -> ``archive``."""
    head, separator, tail = column.partition("-")
    if separator and head.isdigit():
        return tail
    return column

def find_project_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` looking for ``plans/board.config.json``."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / CONFIG_RELATIVE).is_file():
            return candidate
    raise ConfigError(
        f"no {CONFIG_RELATIVE.as_posix()} found in {current} or any parent; "
        "run 'kahnban init' first"
    )

def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(value).split("."):
        digits = re.match(r"\d+", chunk.strip())
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)

def require_engine_version(config: Config) -> None:
    required = _version_tuple(config.engine_min_version)
    installed = _version_tuple(__version__)
    if installed < required:
        raise ConfigError(
            f"board requires kahnban >= {config.engine_min_version} but "
            f"{__version__} is installed.\n"
            "Upgrade with: py -3 -m pip install --upgrade kahnban"
        )

def load_config(
    project_root: Path | None = None,
    config_path: Path | None = None,
    *,
    check_version: bool = True,
) -> Config:
    """Load ``board.config.json``, resolving the board to the main worktree.

    A linked worktree contains its own checkout of ``plans/``; board state lives
    only on the default branch in the main worktree (D2), so discovery hops
    there when invoked from inside ``.worktrees/<ID>``.
    """
    if config_path is not None:
        path = Path(config_path).resolve()
        if not path.is_file():
            raise ConfigError(f"config file not found: {path}")
        root = Path(project_root).resolve() if project_root else path.parent.parent
    else:
        root = find_project_root(Path(project_root) if project_root else None)
        if (root / ".git").exists():
            main = gitops.main_worktree(root)
            if main.resolve() != root.resolve() and (main / CONFIG_RELATIVE).is_file():
                root = main.resolve()
        path = root / CONFIG_RELATIVE

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path}: invalid JSON ({error})") from error
    except OSError as error:
        raise ConfigError(f"{path}: cannot be read ({error})") from error
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a JSON object")

    columns = tuple(raw.get("columns") or DEFAULT_COLUMNS)
    if not columns:
        raise ConfigError(f"{path}: 'columns' must not be empty")
    done_column = str(raw.get("done_column") or columns[-1])
    if done_column not in columns:
        raise ConfigError(f"{path}: done_column '{done_column}' is not in columns")

    config = Config(
        project_root=root,
        path=path,
        engine_min_version=str(raw.get("engine_min_version", "0.0.0")),
        id_prefix=str(raw.get("id_prefix", "TKT")).upper(),
        board_root=str(raw.get("board_root", "plans/tickets")),
        columns=columns,
        done_column=done_column,
        wip_limit=int(raw.get("wip_limit", 3)),
        use_worktrees=bool(raw.get("use_worktrees", True)),
        shared_caches=tuple(raw.get("shared_caches") or ()),
        validation_timeout_sec=int(raw.get("validation_timeout_sec", 1800)),
        log_output_max_bytes=int(raw.get("log_output_max_bytes", 65536)),
        required_headings=tuple(
            raw.get("required_headings") or DEFAULT_REQUIRED_HEADINGS
        ),
        validation_command=str(raw.get("validation_command", "")),
        regression_command=str(raw.get("regression_command", "")),
        design_doc_roots=tuple(raw.get("design_doc_roots") or ("plans",)),
        extensions=dict(raw.get("extensions") or {}),
        ingest=dict(raw.get("ingest") or {}),
        allow_any_branch=bool(raw.get("allow_any_branch", False)),
        sync_remote=bool(raw.get("sync_remote", True)),
        require_proof=bool(raw.get("require_proof", False)),
        require_review=bool(raw.get("require_review", False)),
        require_integration=bool(raw.get("require_integration", False)),
        require_spec=bool(raw.get("require_spec", False)),
        max_blast_radius_files=int(raw.get("max_blast_radius_files", 0)),
        stale_after_days=int(raw.get("stale_after_days", 0)),
        test_patterns=tuple(raw.get("test_patterns") or DEFAULT_TEST_PATTERNS),
        allowed_commands=tuple(str(item) for item in raw.get("allowed_commands") or ()),
        lease_minutes=int(raw.get("lease_minutes", 30)),
        workers={str(k): str(v) for k, v in dict(raw.get("workers") or {}).items()},
        worker_timeout_sec=int(raw.get("worker_timeout_sec", 3600)),
        max_attempts=int(raw.get("max_attempts", 3)),
        max_stop_nudges=int(raw.get("max_stop_nudges", 2)),
        strict_hooks=bool(raw.get("strict_hooks", False)),
        autonomy=str(raw.get("autonomy", Autonomy.UNATTENDED)),
        human_gates=tuple(str(gate) for gate in raw.get("human_gates") or (HumanGate.MERGE,)),
        require_signed_approvals=bool(raw.get("require_signed_approvals", False)),
    )
    if config.autonomy not in AUTONOMY_MODES:
        raise KahnbanError(f"autonomy must be one of {', '.join(AUTONOMY_MODES)}, not '{config.autonomy}'")
    unknown = set(config.human_gates) - HUMAN_GATES
    if unknown:
        raise KahnbanError(f"human_gates may only hold {', '.join(sorted(HUMAN_GATES))}, not {', '.join(sorted(unknown))}")
    if check_version:
        require_engine_version(config)
    return config
