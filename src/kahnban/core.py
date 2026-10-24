"""Board configuration, ticket lookup, gates, and the single transition writer.

Everything that changes board state passes through :func:`transition`, which
performs the four mandatory steps of plan §2.2: frontmatter mutation, ``## Log``
append, ``git mv`` + commit **on the default branch**, and projection regen.

Failures always raise.  Nothing here swallows exceptions; the CLI and MCP server
translate raised errors into stderr text and exit codes.
"""

from __future__ import annotations

import fnmatch
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import random
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kahnban import __version__, attempts, frontmatter, gitops, status, trust, worktree

LOCK_NAME = ".claim.lock"
LOCK_STALE_SECONDS = 300
ARTIFACT_DIR = attempts.ARTIFACT_DIR


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
TEMPLATE_NAME = "template.md"
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
# What the ready gate freezes: the sections a ticket is judged against.
CONTRACT_SECTIONS = ("Acceptance criteria", "Blast radius", "Validation")
# The relay baton the engine writes into every worktree; never part of a change.
HANDOFF_IN_WORKTREE = ".agents/HANDOFF.json"
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


# --- configuration ----------------------------------------------------------


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


# --- tickets ----------------------------------------------------------------


@dataclass(frozen=True)
class Ticket:
    path: Path
    column: str
    ticket_id: str

    @property
    def text(self) -> str:
        return read_text(self.path)


@dataclass
class TicketDraft:
    """A ticket before it has an ID — the unit every entry point produces.

    ``kahnban new`` builds one from a title, ``kahnban capture`` one per idea,
    and ``kahnban ingest`` one per section of a plan document.  Provenance
    fields let a re-ingest recognize what it already created.
    """

    title: str
    problem: str = ""
    acceptance: list[str] = field(default_factory=list)
    blast_radius: list[str] = field(default_factory=list)
    notes: str = ""
    validation: str = ""
    depends_on: list[str] = field(default_factory=list)
    design_docs: list[str] = field(default_factory=list)
    blocked_on: str = ""
    owner: str = "unassigned"
    source_doc: str = ""
    source_anchor: str = ""
    source_hash: str = ""
    extra_frontmatter: dict[str, object] = field(default_factory=dict)
    log_note: str = ""
    # Populated by the ingest parser for reporting; never written to the ticket.
    unresolved_dependencies: list[str] = field(default_factory=list)


@dataclass
class TransitionResult:
    ticket_id: str
    from_column: str
    to_column: str
    path: Path
    commit: str | None = None
    messages: list[str] = field(default_factory=list)


@dataclass
class VerifyResult:
    ticket_id: str
    passed: bool
    exit_code: int
    command: str
    output: str
    artifact: Path | None = None
    transition: TransitionResult | None = None
    messages: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    return frontmatter.normalize_newlines(path.read_text(encoding="utf-8"))


def write_text_atomic(path: Path, text: str) -> None:
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        temp_path.write_text(frontmatter.normalize_newlines(text), encoding="utf-8", newline="\n")
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def write_text(path: Path, text: str) -> None:
    write_text_atomic(path, text)


ID_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)")


def ticket_id_of(path: Path) -> str | None:
    """Ticket ID encoded in a filename, or None when it does not encode one."""
    match = ID_PATTERN.match(path.stem)
    if not match:
        return None
    return f"{match.group(1).upper()}-{match.group(2)}"


def board_columns(config: Config, *, include_archive: bool = False) -> list[str]:
    columns = list(config.columns)
    if include_archive and config.archive_path.is_dir():
        columns.append("archive")
    return columns


def iter_tickets(config: Config, *, include_archive: bool = False) -> list[Ticket]:
    """Every ticket file on the board, ordered by column then filename."""
    tickets: list[Ticket] = []
    for column in board_columns(config, include_archive=include_archive):
        directory = config.board_path / column
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == TEMPLATE_NAME:
                continue
            identifier = ticket_id_of(path) or path.stem.upper()
            tickets.append(Ticket(path=path, column=column, ticket_id=identifier))
    return tickets


def find_ticket(config: Config, ticket_id: str) -> Ticket:
    """Exact ID match against the filename prefix — never a substring match."""
    wanted = ticket_id.strip().upper()
    if not wanted:
        raise TicketNotFoundError("ticket id must not be empty")
    matches = [
        ticket
        for ticket in iter_tickets(config, include_archive=True)
        if ticket.ticket_id == wanted
    ]
    if not matches:
        raise TicketNotFoundError(f"ticket {wanted} not found on the board")
    if len(matches) > 1:
        locations = ", ".join(f"{t.column}/{t.path.name}" for t in matches)
        raise KahnbanError(f"ticket {wanted} exists in more than one place: {locations}")
    return matches[0]


def next_id(config: Config) -> str:
    """Allocate the next ID, scanning every column **and** ``archive/``."""
    prefix = config.id_prefix.upper()
    highest = 0
    width = 3
    for ticket in iter_tickets(config, include_archive=True):
        match = ID_PATTERN.match(ticket.path.stem)
        if not match or match.group(1).upper() != prefix:
            continue
        number = int(match.group(2))
        highest = max(highest, number)
        width = max(width, len(match.group(2)))
    number = highest + 1
    return f"{prefix}-{number:0{width}d}"


def slugify(title: str, *, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "untitled"


# --- body helpers (shared with the linter) ----------------------------------


def section(body: str, heading: str) -> str:
    """Text of ``## <heading>`` up to the next ``## `` heading ('' when absent)."""
    lines = frontmatter.normalize_newlines(body).split("\n")
    wanted = heading.strip().lower()
    for index, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower() == wanted:
            end = next(
                (
                    offset
                    for offset in range(index + 1, len(lines))
                    if lines[offset].startswith("## ")
                ),
                len(lines),
            )
            return "\n".join(lines[index + 1 : end]).strip("\n")
    return ""


def has_section(body: str, heading: str) -> bool:
    wanted = heading.strip().lower()
    return any(
        line.startswith("## ") and line[3:].strip().lower() == wanted
        for line in frontmatter.normalize_newlines(body).split("\n")
    )


CHECKBOX_PATTERN = re.compile(r"^\s*[-*]\s*\[( |x|X)\]")


def checkboxes(body: str, heading: str = "Acceptance criteria") -> tuple[int, int]:
    """``(checked, unchecked)`` counts inside one section."""
    checked = unchecked = 0
    for line in section(body, heading).split("\n"):
        match = CHECKBOX_PATTERN.match(line)
        if not match:
            continue
        if match.group(1) == " ":
            unchecked += 1
        else:
            checked += 1
    return checked, unchecked


def parse_blast_radius(body: str) -> list[str]:
    """Declared paths under ``## Blast radius``, normalized to forward slashes.

    An entry may carry a note after its path (``- `src/a.py` — the parser``):
    a backticked path is taken as the path, and an unquoted one ends where a
    spaced dash or parenthesis starts the note.
    """
    entries: list[str] = []
    for line in section(body, "Blast radius").split("\n"):
        stripped = line.strip()
        if not stripped.startswith(("-", "*")):
            continue
        item = stripped[1:].strip()
        quoted = re.match(r"`([^`]+)`", item)
        if quoted:
            item = quoted.group(1)
        else:
            item = re.split(r"\s+(?:—|–|-|\()", item, maxsplit=1)[0]
        item = item.strip().strip('"').strip("'").strip()
        if not item or item.lower().startswith("_none"):
            continue
        entries.append(normalize_path_entry(item))
    return [entry for entry in entries if entry]


def normalize_path_entry(entry: str) -> str:
    normalized = entry.replace("\\", "/").strip().strip("`")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.strip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def paths_overlap(left: str, right: str) -> bool:
    """Identical path or directory-prefix containment in either direction."""
    a = normalize_path_entry(left)
    b = normalize_path_entry(right)
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def path_within(candidate: str, declared: Iterable[str]) -> bool:
    target = normalize_path_entry(candidate)
    for entry in declared:
        normalized = normalize_path_entry(entry)
        if not normalized:
            continue
        if target == normalized or target.startswith(normalized + "/"):
            return True
    return False


def radius_overlaps(
    left: Sequence[str], right: Sequence[str]
) -> list[tuple[str, str]]:
    return [(a, b) for a in left for b in right if paths_overlap(a, b)]


def extension_problems(
    config: Config, fields: Mapping[str, object], body: str, column: str
) -> list[str]:
    """Extension-field violations for a ticket sitting in ``column``.

    Handles ``enum``, ``required_from``, and conditional ``require_log_match``
    (matched against the ``## Log`` section only).
    """
    problems: list[str] = []
    log_text = section(body, "Log")
    for name, spec in (config.extensions or {}).items():
        if not isinstance(spec, Mapping):
            continue
        raw_value = fields.get(name)
        value = "" if raw_value is None else raw_value
        present = bool(value) if isinstance(value, (str, list)) else True
        required_from = spec.get("required_from")
        required = bool(
            required_from
            and required_from in config.columns
            and column in config.columns
            and config.is_at_or_after(column, str(required_from))
        )
        if required and not present:
            problems.append(
                f"extension field '{name}' is required from column {required_from}"
            )
        allowed = spec.get("enum")
        if present and isinstance(allowed, Sequence) and not isinstance(allowed, str):
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if candidate not in allowed:
                    rendered = ", ".join(str(item) for item in allowed)
                    problems.append(
                        f"extension field '{name}' value '{candidate}' "
                        f"is not one of: {rendered}"
                    )
        condition = spec.get("when")
        if not isinstance(condition, Mapping):
            continue
        equals = condition.get("equals")
        if equals is not None and value != equals:
            continue
        from_column = condition.get("from_column")
        if (
            from_column
            and from_column in config.columns
            and column in config.columns
            and not config.is_at_or_after(column, str(from_column))
        ):
            continue
        pattern = condition.get("require_log_match")
        if pattern and not re.search(str(pattern), log_text):
            problems.append(
                f"extension field '{name}'={value} requires a '## Log' entry "
                f"matching /{pattern}/"
            )
    return problems


FENCE_PATTERN = re.compile(r"^```[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)


def parse_validation_commands(config: Config, body: str) -> tuple[str, str]:
    """Extract (feature_test_command, regression_test_command) from ## Validation."""
    val_section = section(body, "Validation")
    
    feat_cmd = ""
    reg_cmd = ""
    
    # Split by subheadings if present
    subheadings = re.split(r"(?m)^###\s+", val_section)
    for part in subheadings:
        if not part.strip():
            continue
        header = part.splitlines()[0].strip().lower()
        fence_match = FENCE_PATTERN.search(part + "\n")
        if fence_match:
            cmd = fence_match.group(1).strip()
            if "feature" in header:
                feat_cmd = cmd
            elif "regression" in header:
                reg_cmd = cmd

    # Fallback if unsectioned single block: use as feature command
    if not feat_cmd:
        match = FENCE_PATTERN.search(val_section + "\n")
        if match:
            feat_cmd = match.group(1).strip()
        elif config.validation_command.strip():
            feat_cmd = config.validation_command.strip()

    # Fallback for regression command
    if not reg_cmd:
        if config.regression_command.strip():
            reg_cmd = config.regression_command.strip()
        else:
            reg_cmd = feat_cmd

    if not feat_cmd:
        raise GateError(
            "no validation command found: add a fenced command block under "
            "'## Validation' or set 'validation_command' in board.config.json"
        )

    return feat_cmd, reg_cmd


def validation_command(config: Config, body: str) -> str:
    """First fenced block under ``## Validation``, else the config default."""
    match = FENCE_PATTERN.search(section(body, "Validation") + "\n")
    if match:
        command = match.group(1).strip()
        if command:
            return command
    if config.validation_command.strip():
        return config.validation_command.strip()
    raise GateError(
        "no validation command found: add a fenced command block under "
        "'## Validation' or set 'validation_command' in board.config.json"
    )


# --- the frozen contract and its proof --------------------------------------


CRITERION_TEST_PATTERN = re.compile(r"\btest:\s*`([^`]+)`")


def contract_hash(body: str) -> str:
    """Digest of the contract sections; ticking a checkbox leaves it unchanged."""
    text = "\n".join(f"## {name}\n{section(body, name)}" for name in CONTRACT_SECTIONS)
    text = re.sub(r"\[[xX]\]", "[ ]", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def verify_contract(
    config: Config, ticket_id: str, fields: Mapping[str, object], body: str
) -> bool:
    """False when nothing was frozen; raises when the contract changed after ready."""
    frozen = str(fields.get("contract_hash") or "").strip()
    if not frozen:
        return False
    if frozen != contract_hash(body):
        raise GateError(
            f"{ticket_id}: acceptance criteria, blast radius or validation changed "
            "after the ready gate froze them. Restore them, or move the ticket back "
            f"with 'kahnban move {ticket_id} {config.refining_column} --reason <why>' "
            "and re-run 'kahnban ready'."
        )
    return True


def criterion_tests(body: str) -> list[tuple[str, str | None]]:
    """``(criterion, test command or None)`` for each acceptance checkbox.

    A criterion names its proof inline: ``- [ ] rejects x (test: `cmd`)``.
    """
    criteria: list[tuple[str, str | None]] = []
    for line in section(body, "Acceptance criteria").split("\n"):
        match = CHECKBOX_PATTERN.match(line)
        if not match:
            continue
        found = CRITERION_TEST_PATTERN.findall(line)
        criteria.append((line[match.end() :].strip(), found[-1].strip() if found else None))
    return criteria


def untested_criteria_problem(
    fields: Mapping[str, object], body: str
) -> str | None:
    """require_proof: every criterion names its test unless proof is manual."""
    if str(fields.get("validation_class", "")) == "visual-deferred":
        return None
    untested = [text for text, command in criterion_tests(body) if command is None]
    if not untested:
        return None
    return (
        "require_proof: these criteria name no test (append (test: `cmd`)):\n"
        + "\n".join(f"    - {text}" for text in untested)
    )


def decomposition_problems(config: Config, body: str) -> list[str]:
    """Ticket-size rules: a few named files, one of them a test when proof is required."""
    radius = parse_blast_radius(body)
    problems: list[str] = []
    if config.max_blast_radius_files:
        if len(radius) > config.max_blast_radius_files:
            problems.append(
                f"blast radius lists {len(radius)} paths; the limit is "
                f"{config.max_blast_radius_files}: split the ticket"
            )
        folders = [path for path in radius if (config.project_root / path).is_dir()]
        if folders:
            problems.append(
                "blast radius names directories, not files: " + ", ".join(folders)
            )
    if config.require_proof and radius and not any(is_test_path(config, p) for p in radius):
        problems.append("blast radius names no test file, so the change cannot be proven")
    return problems


def disallowed_commands(config: Config, body: str) -> list[str]:
    """Ticket-supplied commands outside ``allowed_commands`` (empty list: no limit).

    Tickets can come from ingested AI plans, and verify runs their commands with
    your privileges; config-level commands are the adopter's own and exempt.
    """
    if not config.allowed_commands:
        return []
    commands = [
        line
        for block in FENCE_PATTERN.findall(section(body, "Validation") + "\n")
        for line in command_lines(block)
    ]
    commands += [command for _, command in criterion_tests(body) if command]
    return [
        command
        for command in dict.fromkeys(commands)
        if not any(
            command == prefix or command.startswith(prefix + " ")
            for prefix in config.allowed_commands
        )
    ]


def _require_allowed_commands(config: Config, ticket_id: str, body: str) -> None:
    refused = disallowed_commands(config, body)
    if refused:
        raise GateError(
            f"{ticket_id} runs commands outside 'allowed_commands':\n"
            + "\n".join(f"  - {command}" for command in refused)
        )


def _tick_passed_criteria(text: str, passed: set[str]) -> str:
    """Check only the boxes whose own test command exited 0."""
    if not passed:
        return text
    fields, body = frontmatter.parse(text)
    lines = section(body, "Acceptance criteria").split("\n")
    for index, line in enumerate(lines):
        found = CRITERION_TEST_PATTERN.findall(line)
        if CHECKBOX_PATTERN.match(line) and found and found[-1].strip() in passed:
            lines[index] = re.sub(r"\[\s\]", "[x]", line, count=1)
    return frontmatter.serialize(
        fields, replace_section(body, "Acceptance criteria", "\n".join(lines))
    )


def is_test_path(config: Config, path: str) -> bool:
    normalized = normalize_path_entry(path).lower()
    name = normalized.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatchcase(normalized, pattern.lower())
        or fnmatch.fnmatchcase(name, pattern.lower())
        for pattern in config.test_patterns
    )


def command_lines(block: str) -> list[str]:
    """One command per line; a trailing ``\\`` or backtick continues the line."""
    commands: list[str] = []
    pending = ""
    for raw in frontmatter.normalize_newlines(block).split("\n"):
        line = raw.strip()
        if line.endswith(("\\", "`")):
            pending += line[:-1].strip() + " "
            continue
        line = (pending + line).strip()
        pending = ""
        if line and not line.startswith("#"):
            commands.append(line)
    if pending.strip():
        commands.append(pending.strip())
    return commands


def run_command(config: Config, command: str, cwd: Path) -> tuple[int, str]:
    """Run one command line through the platform shell."""
    argv: str | list[str] = command
    use_shell = True
    if os.name == "nt":
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
        use_shell = False
    try:
        completed = subprocess.run(
            argv,
            shell=use_shell,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=config.validation_timeout_sec,
        )
        return completed.returncode, (completed.stdout or "") + (completed.stderr or "")
    except subprocess.TimeoutExpired as expired:
        partial = "".join(
            part for part in (expired.stdout, expired.stderr) if isinstance(part, str)
        )
        return 124, f"TIMEOUT after {config.validation_timeout_sec}s\n{partial}"


def run_block(config: Config, block: str, cwd: Path) -> tuple[int, str]:
    """Run every command line in order; the first non-zero exit fails the block.

    A shell reports only its last command's status, so a multi-line block run as
    one script passes when an earlier line fails.
    """
    commands = command_lines(block)
    if not commands:
        raise GateError(f"validation block has no command lines:\n{block}")
    if len(commands) == 1:
        return run_command(config, commands[0], cwd)
    outputs: list[str] = []
    for number, command in enumerate(commands, 1):
        code, output = run_command(config, command, cwd)
        outputs.append(f"$ {command}\n{output}")
        if code != 0:
            outputs.append(f"[line {number} of {len(commands)} exited {code}; rest skipped]")
            return code, "\n".join(outputs)
    return 0, "\n".join(outputs)


# --- locking ----------------------------------------------------------------


LOCK_RETRY_ATTEMPTS = 15
LOCK_RETRY_INTERVAL = 0.1


@contextmanager
def board_lock(
    config: Config,
    *,
    stale_seconds: int = LOCK_STALE_SECONDS,
    max_retries: int = LOCK_RETRY_ATTEMPTS,
    retry_interval: float = LOCK_RETRY_INTERVAL,
    hold_seconds: int = 0,
):
    """Exclusive board lock covering gate checks through commit (§3.3).

    A holder that runs tests passes ``hold_seconds``; the lock records that
    deadline so waiters do not break it as stale while the tests are running.
    """
    lock_path = config.board_path / LOCK_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    descriptor: int | None = None
    for attempt in range(1, max_retries + 1):
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                holder = lock_path.read_text(encoding="utf-8").strip()
            except OSError:
                age, holder = 0.0, "unknown"
            held_until = re.search(r"\buntil=(\d+)", holder)
            if age > stale_seconds and time.time() > int(held_until.group(1) if held_until else 0):
                warnings.append(
                    f"broke stale board lock after {int(age)}s (held by {holder})"
                )
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if attempt < max_retries:
                jitter = random.uniform(0.01, 0.04)
                backoff_factor = min(1.2 ** (attempt - 1), 3.0)
                delay = min(retry_interval * backoff_factor + jitter, 0.5)
                time.sleep(delay)
                continue
            raise LockError(
                f"board is locked by another kahnban process ({holder}); "
                f"retry once it finishes"
            ) from None
    assert descriptor is not None
    try:
        os.write(
            descriptor,
            (
                f"pid={os.getpid()} at={datetime.now().isoformat(timespec='seconds')}"
                + (f" until={int(time.time()) + hold_seconds}" if hold_seconds else "")
                + "\n"
            ).encode(),
        )
        os.close(descriptor)
        descriptor = None
        yield warnings
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


# --- projections ------------------------------------------------------------


LOG_ENTRY = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) - (.*)$")


def log_metrics(log: str) -> dict[str, Any]:
    """Counts and cycle time read from a ticket's ``## Log`` (the audit trail)."""
    entries = [
        (datetime.strptime(match.group(1), "%Y-%m-%d %H:%M"), match.group(2))
        for match in (LOG_ENTRY.match(line) for line in log.split("\n"))
        if match
    ]
    done = next((when for when, text in entries if text.startswith("done gate passed")), None)
    return {
        "verify_attempts": sum(text.startswith("verify exit=") for _, text in entries),
        "rejections": sum(text.startswith("rejected by") for _, text in entries),
        "escalations": sum(text.startswith("escalated to a human") for _, text in entries),
        "cycle_hours": (
            round((done - entries[0][0]).total_seconds() / 3600, 1) if done and entries else None
        ),
    }


def collect_records(config: Config) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for ticket in iter_tickets(config):
        record: dict[str, Any] = {
            "id": ticket.ticket_id,
            "title": "",
            "status": config.status_for(ticket.column),
            "owner": "",
            "branch": "",
            "worktree": "",
            "updated": "",
            "column": ticket.column,
            "description": "",
            "depends_on": [],
            "blocked_on": "",
            "blast_radius": [],
        }
        try:
            fields, body = frontmatter.parse(ticket.text)
        except frontmatter.FrontmatterError:
            # Visible, not silent: lint reports the parse failure as BL01.
            record["title"] = "(invalid frontmatter)"
            records.append(record)
            continue
        for key in ("id", "title", "status", "owner", "branch", "worktree", "updated"):
            value = fields.get(key, "")
            if isinstance(value, list):
                value = ", ".join(value)
            if value:
                record[key] = str(value)

        raw_depends = fields.get("depends_on", [])
        if isinstance(raw_depends, list):
            record["depends_on"] = [str(d) for d in raw_depends]
        elif raw_depends:
            if isinstance(raw_depends, str):
                record["depends_on"] = [d.strip() for d in raw_depends.split(",") if d.strip()]
            else:
                record["depends_on"] = [str(raw_depends)]

        record["blocked_on"] = str(fields.get("blocked_on", "") or "")
        record["blast_radius"] = parse_blast_radius(body)
        record["metrics"] = log_metrics(section(body, "Log"))

        prob = section(body, "Problem") or section(body, "Objective")
        if prob:
            paragraphs = [p.strip() for p in prob.split("\n\n") if p.strip()]
            record["description"] = paragraphs[0].replace("\n", " ") if paragraphs else ""

        records.append(record)
    return records


def sync(config: Config, *, timestamp: datetime | None = None) -> list[Path]:
    """Regenerate projections (STATUS.md, status.json, board.json); returns paths written."""
    return status.write(
        config.plans_dir,
        collect_records(config),
        config.columns,
        timestamp=timestamp or datetime.now(),
        project_name=config.project_root.name,
        wip_limit=config.wip_limit,
    )


# --- the single transition writer -------------------------------------------


def _relative(config: Config, path: Path) -> str:
    return Path(path).resolve().relative_to(config.project_root.resolve()).as_posix()


def _require_board_branch(config: Config, *, allow_branch: bool = False) -> str:
    """Board commits land on the default branch, never a ticket branch (D2)."""
    default = gitops.default_branch(config.project_root)
    current = gitops.current_branch(config.project_root)
    if current != default and not allow_branch and not config.allow_any_branch:
        raise GateError(
            f"board state must be committed on the default branch '{default}' but "
            f"'{current}' is checked out in {config.project_root}. "
            "Run kahnban from the main worktree or pass --allow-branch."
        )
    return default


def _apply_frontmatter(text: str, updates: Mapping[str, object]) -> str:
    """Set frontmatter keys, adding any the ticket does not carry yet."""
    fields, body = frontmatter.parse(text)
    missing = {key: value for key, value in updates.items() if key not in fields}
    if missing:
        fields.update(missing)  # type: ignore[arg-type]
        text = frontmatter.serialize(fields, body)
    return frontmatter.mutate(text, updates)  # type: ignore[arg-type]


def log_line(entry: str, *, timestamp: datetime | None = None) -> str:
    stamp = (timestamp or datetime.now()).strftime("%Y-%m-%d %H:%M")
    return f"- {stamp} - {entry}"


def _check_veto(config: Config, ticket: Ticket, target_column: str, log_entry: str) -> None:
    """Run the ``pre-transition`` hook: exit 2 vetoes the move; with ``strict_hooks`` so does any failure."""
    from kahnban import hooks

    event = {"from": ticket.column, "to": target_column, "log_entry": log_entry}
    veto = hooks.run_hook(
        config.project_root, "pre-transition", ticket.ticket_id, column=target_column, payload=event
    )
    if not veto.executed:
        return
    if veto.exit_code == 2:
        raise GateError(
            f"pre-transition hook refused {ticket.column} -> {target_column}: "
            + (veto.stderr.strip() or "no reason given")
        )
    if config.strict_hooks and veto.exit_code != 0:
        raise GateError(
            f"pre-transition hook failed (exit {veto.exit_code}) and strict_hooks is on, so "
            f"{ticket.column} -> {target_column} is refused: "
            + (veto.stderr.strip() or "no output")
        )


def transition(
    config: Config,
    ticket_id: str,
    target_column: str,
    *,
    log_entry: str,
    fm_updates: Mapping[str, object] | None = None,
    extra_paths: Sequence[Path] = (),
    commit_message: str | None = None,
    timestamp: datetime | None = None,
    verification: Mapping[str, object] | None = None,
    vetoed: bool = False,
) -> TransitionResult:
    """Move a ticket and commit the board change on the default branch.

    Every move is also a handoff: a ``pre-transition`` hook can veto it (exit 2),
    the ticket's baton is rewritten for whoever acts next, and a
    ``post-transition`` hook hears about it.
    """
    from kahnban import hooks

    valid_targets = [*config.columns, "archive"]
    if target_column not in valid_targets:
        raise GateError(
            f"unknown target column '{target_column}'; expected one of: "
            + ", ".join(valid_targets)
        )
    ticket = find_ticket(config, ticket_id)
    _require_board_branch(config)
    event = {"from": ticket.column, "to": target_column, "log_entry": log_entry}
    if not vetoed:  # claim runs the veto itself, before it creates a worktree
        _check_veto(config, ticket, target_column, log_entry)
    now = timestamp or datetime.now()

    updates: dict[str, object] = {
        "status": config.status_for(target_column),
        "updated": now.date().isoformat(),
    }
    updates.update(fm_updates or {})

    text = _apply_frontmatter(ticket.text, updates)
    text = frontmatter.append_log(text, log_line(log_entry, timestamp=now))
    write_text(ticket.path, text)

    destination = config.board_path / target_column / ticket.path.name
    if destination.resolve() != ticket.path.resolve():
        destination.parent.mkdir(parents=True, exist_ok=True)
        gitops.mv(
            config.project_root,
            Path(_relative(config, ticket.path)),
            Path(_relative(config, destination)),
        )

    projections = sync(config, timestamp=now)
    paths = [destination, *projections, *extra_paths]
    rel_paths = [_relative(config, path) for path in paths]
    gitops.add(config.project_root, rel_paths)
    commit_paths = list(rel_paths)
    if destination.resolve() != ticket.path.resolve():
        commit_paths.append(_relative(config, ticket.path))
    message = commit_message or (
        f"kanban({ticket.ticket_id}): {ticket.column} -> {target_column}"
    )
    sha = gitops.commit(config.project_root, message, paths=commit_paths)

    result = TransitionResult(
        ticket_id=ticket.ticket_id,
        from_column=ticket.column,
        to_column=target_column,
        path=destination,
        commit=sha,
    )
    baton = _refresh_baton(config, ticket.ticket_id, log_entry, result.messages, verification)
    after = hooks.run_hook(
        config.project_root,
        "post-transition",
        ticket.ticket_id,
        column=target_column,
        baton_path=str(baton or ""),
        payload={**event, "commit": sha},
    )
    if after.executed and after.exit_code != 0:
        result.messages.append(
            f"[WARN] post-transition hook exit {after.exit_code}: {after.stderr.strip()[:300]}"
        )
    return result


def _refresh_baton(
    config: Config,
    ticket_id: str,
    event: str,
    messages: list[str],
    verification: Mapping[str, object] | None = None,
) -> Path | None:
    """Rewrite the ticket's handoff baton; a failure is a warning, never a lost move."""
    from kahnban import handoff

    try:
        return handoff.refresh(
            config,
            ticket_id,
            event=event,
            verification=dict(verification) if verification is not None else None,
        )
    except (KahnbanError, frontmatter.FrontmatterError, OSError) as error:
        messages.append(f"[WARN] handoff baton not refreshed: {error}")
        return None


def refresh_baton_strict(config: Config, ticket_id: str, event: str) -> Path | None:
    """Rewrite the baton and fail loudly; None means the baton feature is off for this project."""
    from kahnban import handoff

    try:
        return handoff.refresh(config, ticket_id, event=event)
    except (frontmatter.FrontmatterError, OSError) as error:
        raise KahnbanError(f"handoff baton for {ticket_id} cannot be written: {error}") from error


def _report_refusal(config: Config, ticket_id: str, gate: str, reason: str) -> None:
    """Run the ``on-refusal`` hook: every gate that says no says so the same way."""
    from kahnban import hooks

    hooks.run_hook(
        config.project_root, "on-refusal", ticket_id, payload={"gate": gate, "reason": reason}
    )


def _refusals_reported(gate: Callable[..., Any]) -> Callable[..., Any]:
    """Fire ``on-refusal`` whenever ``gate`` raises :class:`GateError`, then re-raise."""

    @functools.wraps(gate)
    def wrapper(config: Config, ticket_id: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return gate(config, ticket_id, *args, **kwargs)
        except GateError as error:
            _report_refusal(config, ticket_id, gate.__name__, str(error))
            raise

    return wrapper


# --- gates ------------------------------------------------------------------


def template_text(config: Config) -> str:
    """The board's ticket template, falling back to the engine's copy."""
    template_path = config.board_path / TEMPLATE_NAME
    if not template_path.is_file():
        template_path = Path(__file__).parent / "templates" / "ticket.md"
    return read_text(template_path)


def normalize_acceptance(lines: Iterable[str]) -> list[str]:
    """Render acceptance lines as unchecked checkboxes.

    Imported criteria are never carried over as checked: a box is only ticked
    after ``kahnban verify`` runs the validation command (Principle 5).
    """
    rendered: list[str] = []
    for raw in lines:
        text = raw.strip()
        if not text:
            continue
        match = CHECKBOX_PATTERN.match(text)
        if match:
            text = text[match.end() :].strip()
        elif text.startswith(("-", "*")):
            text = text[1:].strip()
        if text:
            rendered.append(f"- [ ] {text}")
    return rendered


def _tick_acceptance_criteria(text: str, *, ticked: bool = True) -> str:
    """Set every checkbox in '## Acceptance criteria' to checked (or unchecked)."""
    fields, body = frontmatter.parse(text)
    criteria = section(body, 'Acceptance criteria')
    if not criteria:
        return text
    box, mark = (r'\[\s*\]', '[x]') if ticked else (r'\[[xX]\]', '[ ]')
    rewritten = re.sub(r'^(\s*[-*]\s*)' + box, r'\g<1>' + mark, criteria, flags=re.MULTILINE)
    if rewritten == criteria:
        return text
    return frontmatter.serialize(fields, replace_section(body, 'Acceptance criteria', rewritten))


def render_ticket(
    config: Config,
    draft: TicketDraft,
    ticket_id: str,
    *,
    column: str,
    timestamp: datetime,
    base_text: str | None = None,
) -> str:
    """Build a complete ticket file from a draft and the board template."""
    fields, body = frontmatter.parse(base_text or template_text(config))
    updates: dict[str, object] = {
        "id": ticket_id,
        "title": draft.title.strip(),
        "status": config.status_for(column),
        "owner": draft.owner or "unassigned",
        "created": timestamp.date().isoformat(),
        "updated": timestamp.date().isoformat(),
        "depends_on": list(draft.depends_on),
        "design_docs": list(draft.design_docs),
        "blocked_on": draft.blocked_on,
    }
    if draft.source_doc or draft.source_anchor or draft.source_hash:
        updates["source_doc"] = draft.source_doc
        updates["source_anchor"] = draft.source_anchor
        updates["source_hash"] = draft.source_hash
    updates.update(draft.extra_frontmatter)
    for key, value in updates.items():
        fields[key] = value

    # Every draft-managed section is replaced, blank included: a ticket must
    # never inherit the template's example checkbox or example path, or an empty
    # draft would satisfy the refinement gate on boilerplate alone.
    body = replace_section(body, "Problem", draft.problem.strip())
    body = replace_section(
        body, "Acceptance criteria", "\n".join(normalize_acceptance(draft.acceptance))
    )
    body = replace_section(
        body,
        "Blast radius",
        "\n".join(f"- `{normalize_path_entry(item)}`" for item in draft.blast_radius),
    )
    body = replace_section(body, "Implementation notes", draft.notes.strip())
    command = draft.validation.strip() or config.validation_command.strip()
    body = replace_section(
        body, "Validation", f"```\n{command}\n```" if command else ""
    )
    body = replace_section(body, "Log", "")
    return frontmatter.serialize(fields, body)


def allocate_ids(config: Config, count: int) -> list[str]:
    """Sequential IDs for a batch, allocated once from the global scan.

    Callers that need the IDs before writing (dependency wiring during a plan
    ingest) allocate here and pass them back to :func:`create_tickets`.
    """
    if count <= 0:
        return []
    first = next_id(config)
    prefix, _, number = first.rpartition("-")
    width = len(number)
    start = int(number)
    return [f"{prefix}-{start + offset:0{width}d}" for offset in range(count)]


def create_tickets(
    config: Config,
    drafts: Sequence[TicketDraft],
    *,
    identifiers: Sequence[str] | None = None,
    timestamp: datetime | None = None,
    commit_message: str | None = None,
    log_note: str = "",
) -> list[TransitionResult]:
    """Write a batch of tickets into the backlog as **one** board commit.

    IDs are allocated together so a 40-ticket plan ingest does not produce 40
    commits, and a failed batch leaves nothing half-written.
    """
    if not drafts:
        return []
    for draft in drafts:
        if not draft.title.strip():
            raise GateError("every ticket draft needs a title")
    _require_board_branch(config)
    now = timestamp or datetime.now()
    column = config.backlog_column
    if identifiers is None:
        identifiers = allocate_ids(config, len(drafts))
    elif len(identifiers) != len(drafts):
        raise KahnbanError(
            f"got {len(identifiers)} identifiers for {len(drafts)} drafts"
        )

    written: list[Path] = []
    results: list[TransitionResult] = []
    for ticket_id, draft in zip(identifiers, drafts):
        destination = (
            config.board_path / column / f"{ticket_id}-{slugify(draft.title)}.md"
        )
        if destination.exists():
            raise KahnbanError(f"ticket file already exists: {destination}")
        text = render_ticket(
            config, draft, ticket_id, column=column, timestamp=now
        )
        entry = f"created -> {column}"
        note = draft.log_note or log_note
        if note:
            entry = f"{entry} | {note}"
        text = frontmatter.append_log(text, log_line(entry, timestamp=now))
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_text(destination, text)
        written.append(destination)
        results.append(
            TransitionResult(
                ticket_id=ticket_id,
                from_column="(new)",
                to_column=column,
                path=destination,
            )
        )

    projections = sync(config, timestamp=now)
    commit_paths = [_relative(config, path) for path in (*written, *projections)]
    gitops.add(
        config.project_root,
        commit_paths,
    )
    if commit_message is None:
        if len(results) == 1:
            commit_message = f"kanban({results[0].ticket_id}): create -> {column}"
        else:
            commit_message = (
                f"kanban: create {len(results)} tickets -> {column} "
                f"({results[0].ticket_id}..{results[-1].ticket_id})"
            )
    sha = gitops.commit(config.project_root, commit_message, paths=commit_paths)
    for result in results:
        result.commit = sha
    return results


def create_ticket(
    config: Config,
    title: str | None = None,
    *,
    problem: str | None = None,
    owner: str = "unassigned",
    draft: TicketDraft | None = None,
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban new`` — allocate an ID and commit one ticket into the backlog."""
    if draft is None:
        if not (title or "").strip():
            raise GateError("a ticket title is required")
        draft = TicketDraft(
            title=str(title), problem=problem or "", owner=owner
        )
    return create_tickets(config, [draft], timestamp=timestamp)[0]


def update_ticket_body(
    config: Config,
    ticket_id: str,
    draft: TicketDraft,
    *,
    note: str,
    timestamp: datetime | None = None,
) -> TransitionResult:
    """Re-render an un-started ticket from a draft, preserving its ID and Log.

    Used when a source plan changed: the ticket keeps its identity and audit
    trail, and the refreshed content is committed with a logged reason.
    """
    ticket = find_ticket(config, ticket_id)
    if ticket.column not in (config.backlog_column, config.refining_column):
        raise GateError(
            f"{ticket.ticket_id} is in {ticket.column}; re-ingest only rewrites "
            f"tickets still in {config.backlog_column} or {config.refining_column}"
        )
    _require_board_branch(config)
    now = timestamp or datetime.now()
    previous_fields, previous_body = frontmatter.parse(ticket.text)
    text = render_ticket(
        config,
        draft,
        ticket.ticket_id,
        column=ticket.column,
        timestamp=now,
        base_text=template_text(config),
    )
    fields, body = frontmatter.parse(text)
    fields["created"] = previous_fields.get("created", now.date().isoformat())
    text = frontmatter.serialize(fields, body)
    for entry in core_log_entries(previous_body):
        text = frontmatter.append_log(text, entry)
    text = frontmatter.append_log(text, log_line(note, timestamp=now))
    write_text(ticket.path, text)

    projections = sync(config, timestamp=now)
    gitops.add(
        config.project_root,
        [_relative(config, path) for path in (ticket.path, *projections)],
    )
    sha = gitops.commit(
        config.project_root, f"kanban({ticket.ticket_id}): refresh from source"
    )
    return TransitionResult(
        ticket_id=ticket.ticket_id,
        from_column=ticket.column,
        to_column=ticket.column,
        path=ticket.path,
        commit=sha,
    )


def core_log_entries(body: str) -> list[str]:
    """Existing ``## Log`` lines, so a rewrite never drops the audit trail."""
    return [
        line.rstrip()
        for line in section(body, "Log").split("\n")
        if line.strip()
    ]


def replace_section(body: str, heading: str, content: str) -> str:
    """Replace one ``## <heading>`` section body, leaving the rest untouched."""
    lines = frontmatter.normalize_newlines(body).split("\n")
    wanted = heading.strip().lower()
    for index, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower() == wanted:
            end = next(
                (
                    offset
                    for offset in range(index + 1, len(lines))
                    if lines[offset].startswith("## ")
                ),
                len(lines),
            )
            replacement = [content] if content else []
            tail = lines[end:]
            if tail:
                replacement.append("")
            return "\n".join([*lines[: index + 1], *replacement, *tail])
    return body


@_refusals_reported
def ready(
    config: Config, ticket_id: str, *, timestamp: datetime | None = None
) -> TransitionResult:
    """``kahnban ready`` — the refinement gate (plan §2.2)."""
    ticket = find_ticket(config, ticket_id)
    target = config.ready_column
    if ticket.column not in (config.refining_column, config.backlog_column):
        raise GateError(
            f"{ticket.ticket_id} is in {ticket.column}; "
            f"'ready' applies to {config.refining_column}"
        )
    if os.environ.get("KAHNBAN_ROLE") and needs_human(config, ticket):
        raise GateError(
            f"{ticket.ticket_id} waits for a human: this is an attended run, so a person "
            f"reviews it and runs 'kahnban confirm {ticket.ticket_id}' before the ready gate"
        )
    problems = ready_problems(config, ticket)
    if problems:
        raise GateError(
            f"{ticket.ticket_id} is not ready:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )
    frozen = contract_hash(frontmatter.parse(ticket.text)[1])
    result = transition(
        config,
        ticket.ticket_id,
        target,
        log_entry=f"ready gate passed -> {target} | contract {frozen}",
        fm_updates={"contract_hash": frozen, "confirmed": ""},
        timestamp=timestamp,
    )
    from kahnban.handoff import get_handoff_path
    from kahnban.hooks import run_hook

    baton = get_handoff_path(config.project_root, ticket.ticket_id)
    run_hook(
        config.project_root,
        "post-ready",
        ticket.ticket_id,
        column=target,
        baton_path=str(baton) if baton.exists() else "",
    )
    return result


def ready_problems(config: Config, ticket: Ticket) -> list[str]:
    """Everything that keeps ``ticket`` out of the ready column; empty when it may pass."""
    fields, body = frontmatter.parse(ticket.text)
    problems: list[str] = []

    checked, unchecked = checkboxes(body)
    if checked + unchecked < 1:
        problems.append("'## Acceptance criteria' has no checkboxes")
    if not parse_blast_radius(body):
        problems.append("'## Blast radius' is empty")
    blocked_on = fields.get("blocked_on") or ""
    if isinstance(blocked_on, list):
        blocked_on = ", ".join(blocked_on)
    if str(blocked_on).strip():
        problems.append(f"blocked_on is set: {blocked_on}")
    problems.extend(_dependency_problems(config, fields))
    problems.extend(extension_problems(config, fields, body, config.ready_column))
    if config.require_proof:
        untested = untested_criteria_problem(fields, body)
        if untested:
            problems.append(untested)
    problems.extend(
        f"command outside 'allowed_commands': {command}"
        for command in disallowed_commands(config, body)
    )
    problems.extend(decomposition_problems(config, body))
    if config.require_spec:
        from kahnban import specs

        problems.extend(specs.ticket_problems(config, fields, require_approved=True))
    return problems


def _dependency_problems(config: Config, fields: Mapping[str, object]) -> list[str]:
    problems: list[str] = []
    for dependency in _as_list(fields.get("depends_on")):
        try:
            dependency_ticket = find_ticket(config, dependency)
        except KahnbanError:
            problems.append(f"depends_on '{dependency}' does not exist")
            continue
        if dependency_ticket.column != config.done_column:
            problems.append(
                f"depends_on '{dependency}' is in {dependency_ticket.column}, "
                f"not {config.done_column}"
            )
    return problems


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def in_progress_radii(
    config: Config, *, exclude: str | None = None
) -> dict[str, list[str]]:
    """Blast radius of every ticket currently in the in-progress column."""
    radii: dict[str, list[str]] = {}
    for ticket in iter_tickets(config):
        if ticket.column != config.in_progress_column:
            continue
        if exclude and ticket.ticket_id == exclude.upper():
            continue
        try:
            _, body = frontmatter.parse(ticket.text)
        except frontmatter.FrontmatterError:
            continue
        radii[ticket.ticket_id] = parse_blast_radius(body)
    return radii


@_refusals_reported
def claim(
    config: Config,
    ticket_id: str,
    owner: str,
    *,
    create_worktree: bool | None = None,
    force: bool = False,
    force_overlap: bool = False,
    strict_wip: bool = False,
    local: bool = False,
    reason: str = "",
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban claim`` — §3.2 claim flow under the board lock."""
    if not owner.strip():
        raise GateError("--owner is required to claim a ticket")
    target = config.in_progress_column
    use_worktree = config.use_worktrees if create_worktree is None else create_worktree
    messages: list[str] = []

    with board_lock(config) as lock_warnings:
        messages.extend(lock_warnings)
        _require_board_branch(config)
        default_branch = gitops.default_branch(config.project_root)
        remote = gitops.has_remote(config.project_root)

        if remote and not local and config.sync_remote:
            try:
                gitops.pull_ff_only(config.project_root, "origin", default_branch)
            except gitops.GitError as error:
                raise GateError(
                    "cannot fast-forward the default branch before claiming; "
                    f"resolve the divergence first.\n{error}"
                ) from error

        ticket = find_ticket(config, ticket_id)
        if ticket.column != config.ready_column:
            if not force:
                raise GateError(
                    f"{ticket.ticket_id} is in {ticket.column}; only "
                    f"{config.ready_column} tickets can be claimed "
                    "(override with --force and a --reason)"
                )
            if not reason.strip():
                raise GateError("--force requires --reason")
            messages.append(
                f"forced claim from {ticket.column}: {reason.strip()}"
            )

        fields, body = frontmatter.parse(ticket.text)
        problems = _dependency_problems(config, fields)
        if problems:
            raise GateError(
                f"{ticket.ticket_id} has unsatisfied dependencies:\n"
                + "\n".join(f"  - {problem}" for problem in problems)
            )
        contract_updates: dict[str, object] = {}
        if not verify_contract(config, ticket.ticket_id, fields, body):
            contract_updates["contract_hash"] = contract_hash(body)
            messages.append("contract frozen at claim (ticket skipped the ready gate)")

        in_progress = in_progress_radii(config, exclude=ticket.ticket_id)
        if len(in_progress) >= config.wip_limit:
            detail = (
                f"WIP limit {config.wip_limit} reached "
                f"({len(in_progress)} tickets in {target})"
            )
            if strict_wip:
                raise GateError(detail)
            messages.append(f"[WARN] {detail}")

        candidate_radius = parse_blast_radius(body)
        collisions: list[str] = []
        for other_id, other_radius in sorted(in_progress.items()):
            for mine, theirs in radius_overlaps(candidate_radius, other_radius):
                collisions.append(f"{other_id}: '{mine}' overlaps '{theirs}'")
        if collisions:
            if not force_overlap:
                raise GateError(
                    f"{ticket.ticket_id} blast radius overlaps in-progress work:\n"
                    + "\n".join(f"  - {item}" for item in collisions)
                    + "\nAmend the blast radius, wait, or override with "
                    "--force-overlap --reason <why>"
                )
            if not reason.strip():
                raise GateError("--force-overlap requires --reason")
            messages.append(
                "forced overlap claim: "
                + reason.strip()
                + " ["
                + "; ".join(collisions)
                + "]"
            )

        _check_veto(config, ticket, target, f"claimed by {owner.strip()} -> {target}")
        for attempt in (1, 2):
            info: worktree.WorktreeInfo | None = None
            updates: dict[str, object] = {"owner": owner.strip(), **contract_updates}
            if use_worktree:
                info = worktree.provision(
                    config.project_root,
                    ticket.ticket_id,
                    start_point=default_branch,
                    shared_caches=config.shared_caches,
                )
                messages.extend(f"[WARN] {note}" for note in info.warnings)
                updates["branch"] = info.branch
                updates["worktree"] = info.path.relative_to(
                    config.project_root
                ).as_posix()
                updates["junctions"] = list(info.junctions)
            else:
                updates["branch"] = worktree.branch_name(ticket.ticket_id)

            log_entry = f"claimed by {owner.strip()} -> {target}"
            if messages:
                log_entry += " | " + "; ".join(
                    message for message in messages if not message.startswith("[WARN]")
                ).strip(" ;")
            try:
                result = transition(
                    config,
                    ticket.ticket_id,
                    target,
                    log_entry=log_entry.rstrip(" |"),
                    fm_updates=updates,
                    timestamp=timestamp,
                    vetoed=True,
                )
            except Exception:
                if info is not None:  # a refused claim leaves no worktree or branch behind
                    worktree.teardown(
                        config.project_root, ticket.ticket_id, junctions=info.junctions, force=True
                    )
                raise
            result.messages = [*messages, *result.messages]
            write_lease(config, ticket.ticket_id, owner.strip())
            from kahnban.handoff import get_handoff_path
            from kahnban.hooks import run_hook

            baton = get_handoff_path(config.project_root, ticket.ticket_id)
            run_hook(
                config.project_root,
                "post-claim",
                ticket.ticket_id,
                column=target,
                worktree=info.path.relative_to(config.project_root).as_posix() if info else "",
                baton_path=str(baton) if baton.exists() else "",
            )

            if not remote or local or not config.sync_remote:
                return result
            try:
                gitops.push(config.project_root, "origin", default_branch)
                return result
            except gitops.GitError as error:
                _rollback_commit(config, result.commit)
                drop_lease(config, ticket.ticket_id)
                if info is not None:
                    worktree.teardown(
                        config.project_root,
                        ticket.ticket_id,
                        junctions=info.junctions,
                        force=True,
                    )
                if attempt == 2:
                    raise GateError(
                        f"claim of {ticket.ticket_id} lost the race: the default "
                        "branch moved upstream and the claim commit was rejected. "
                        f"Rolled back locally.\n{error}"
                    ) from error
                messages.append(
                    "[WARN] push rejected; retrying claim after pull --ff-only"
                )
                gitops.pull_ff_only(config.project_root, "origin", default_branch)
                ticket = find_ticket(config, ticket.ticket_id)
                if ticket.column != config.ready_column and not force:
                    raise GateError(
                        f"{ticket.ticket_id} was claimed by another clone "
                        f"(now in {ticket.column})"
                    ) from error
    raise GateError(f"claim of {ticket_id} failed")


def _rollback_commit(config: Config, sha: str | None) -> None:
    """Undo exactly the commit we just created, and nothing older."""
    if not sha:
        return
    head = gitops.rev_parse(config.project_root, "HEAD")
    if head != sha:
        raise KahnbanError(
            "refusing to roll back: HEAD moved since the board commit "
            f"({head[:8]} != {sha[:8]}); resolve the repository state manually"
        )
    gitops.reset_hard(config.project_root, "HEAD~1")


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text.encode("utf-8", "replace")) <= limit:
        return text
    half = max(limit // 2, 1)
    encoded = text.encode("utf-8", "replace")
    head = encoded[:half].decode("utf-8", "replace")
    tail = encoded[-half:].decode("utf-8", "replace")
    omitted = len(encoded) - len(head.encode()) - len(tail.encode())
    return f"{head}\n...[{omitted} bytes truncated]...\n{tail}"


def _indent_output(text: str) -> str:
    """Indent captured output so no line can pose as a markdown heading."""
    lines = frontmatter.normalize_newlines(text).split("\n")
    return "\n".join(f"    {line}" if line.strip() else "" for line in lines)


def diff_scope_problems(
    config: Config, ticket: Ticket, fields: Mapping[str, object], radius: Sequence[str]
) -> tuple[list[str], list[str]]:
    """(out-of-scope paths, notes) for the ticket branch vs its blast radius."""
    branch = str(fields.get("branch") or "").strip() or worktree.branch_name(
        ticket.ticket_id
    )
    if not gitops.branch_exists(config.project_root, branch):
        return [], [f"[WARN] branch {branch} does not exist; scope check skipped"]
    default_branch = gitops.default_branch(config.project_root)
    base = gitops.merge_base(config.project_root, default_branch, branch)
    changed = gitops.diff_names(config.project_root, base, branch)
    # Tests, CI and agent rules are code too: a change to them must be declared.
    exempt = (config.board_root, HANDOFF_IN_WORKTREE)
    offenders = [
        path
        for path in changed
        if not path_within(path, exempt) and not path_within(path, radius)
    ]
    return offenders, []


# --- leases: who is working an in-progress ticket right now -------------------
#
# ponytail: leases are local files (like the board lock), so they arbitrate
# workers on one machine; cross-clone claims are still arbitrated by the push.


def _lease_path(config: Config, ticket_id: str) -> Path:
    return config.board_path / ".leases" / f"{ticket_id}.json"


def live_lease(config: Config, ticket_id: str) -> str:
    """Holder of an unexpired lease on ``ticket_id``, or ''."""
    path = _lease_path(config, ticket_id)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        holder, until = str(data["owner"]), float(data["until"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return holder if until > time.time() else ""


def write_lease(config: Config, ticket_id: str, owner: str, minutes: int | None = None) -> None:
    path = _lease_path(config, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    ignore = path.parent / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8", newline="\n")
    until = time.time() + 60 * (minutes or config.lease_minutes)
    write_text_atomic(path, json.dumps({"owner": owner, "until": until}))


def drop_lease(config: Config, ticket_id: str) -> None:
    _lease_path(config, ticket_id).unlink(missing_ok=True)


def lease(
    config: Config,
    ticket_id: str,
    owner: str,
    *,
    minutes: int | None = None,
    timestamp: datetime | None = None,
) -> TransitionResult | None:
    """``kahnban lease`` — renew your hold on an in-progress ticket, or take over
    one whose holder's lease expired (the takeover is committed and logged)."""
    owner = owner.strip()
    if not owner:
        raise GateError("--owner is required to lease a ticket")
    with board_lock(config):
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        if ticket.column != config.in_progress_column:
            raise GateError(
                f"{ticket.ticket_id} is in {ticket.column}; leases apply to "
                f"{config.in_progress_column}"
            )
        holder = live_lease(config, ticket.ticket_id)
        if holder and holder.lower() != owner.lower():
            raise GateError(f"{ticket.ticket_id} is leased by '{holder}'; wait for it to expire")
        fields, _ = frontmatter.parse(ticket.text)
        previous = str(fields.get("owner") or "").strip()
        result = None
        if previous.lower() != owner.lower():
            result = transition(
                config,
                ticket.ticket_id,
                ticket.column,
                log_entry=f"taken over by {owner} from {previous or 'nobody'} (no live lease)",
                fm_updates={"owner": owner},
                commit_message=f"kanban({ticket.ticket_id}): taken over by {owner}",
                timestamp=timestamp,
            )
        write_lease(config, ticket.ticket_id, owner, minutes)
        return result


@_refusals_reported
def escalate(
    config: Config, ticket_id: str, reason: str, *, timestamp: datetime | None = None
) -> TransitionResult:
    """``kahnban escalate`` — park a ticket for a human; the dispatcher skips it."""
    if not reason.strip():
        raise GateError("--reason is required to escalate a ticket")
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry=f"escalated to a human: {reason.strip()}",
            fm_updates={"blocked_on": f"human: {reason.strip()}"},
            commit_message=f"kanban({ticket.ticket_id}): escalated",
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
    drop_lease(config, ticket.ticket_id)
    attempts.clear(config, ticket.ticket_id)
    try:
        from kahnban.hooks import run_hook

        run_hook(
            config.project_root,
            "on-escalate",
            ticket.ticket_id,
            column=ticket.column,
            payload={"reason": reason.strip()},
        )
    except Exception as hook_err:
        result.messages.append(f"[WARN] on-escalate hook error: {hook_err}")
    return result


@_refusals_reported
def unblock(
    config: Config, ticket_id: str, reason: str, *, timestamp: datetime | None = None
) -> TransitionResult:
    """``kahnban unblock`` — a human clears ``blocked_on`` so work can resume."""
    if not reason.strip():
        raise GateError("--reason is required to unblock a ticket")
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry=f"unblocked: {reason.strip()}",
            fm_updates={"blocked_on": ""},
            commit_message=f"kanban({ticket.ticket_id}): unblocked",
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
    attempts.clear(config, ticket.ticket_id)  # a human looked at it: start counting again
    return result


@_refusals_reported
def confirm(
    config: Config, ticket_id: str, *, timestamp: datetime | None = None
) -> TransitionResult:
    """``kahnban confirm`` — a human signs off the next gate of an attended run.

    Before ``ready`` that is the refined ticket's contract; in verifying it is the exact
    branch tip that ``merge`` will land. Each mark is tied to what was reviewed, so an
    edited contract or new commits need a new one.
    """
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        fields, body = frontmatter.parse(ticket.text)
        gate = _human_gate(config, ticket.column)
        if not gate:
            raise GateError(
                f"{ticket.ticket_id} is in {ticket.column}; only a ticket waiting for 'ready' "
                "or 'merge' has anything to confirm"
            )
        mark = f"ready:{contract_hash(body)}"
        if gate == HumanGate.MERGE:
            tip = branch_tip(config, ticket_branch(fields, ticket.ticket_id))
            if not tip:
                raise GateError(f"{ticket.ticket_id} has no branch to confirm")
            mark = f"merge:{tip}"
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry=f"confirmed by a human for {gate}",
            fm_updates={"confirmed": mark, "blocked_on": ""},
            commit_message=f"kanban({ticket.ticket_id}): confirmed for {gate}",
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
    attempts.clear(config, ticket.ticket_id)
    return result


def _human_gate(config: Config, column: str) -> str:
    if column in (config.backlog_column, config.refining_column):
        return HumanGate.READY
    return HumanGate.MERGE if column == config.verifying_column else ""


def needs_human(config: Config, ticket: Ticket) -> str:
    """The gate an attended run must hand to a human before taking it, or ''."""
    gate = _human_gate(config, ticket.column)
    if config.autonomy != Autonomy.ATTENDED or gate not in config.human_gates:
        return ""
    fields, body = frontmatter.parse(ticket.text)
    mark = str(fields.get("confirmed") or "").strip()
    if gate == HumanGate.READY:
        return "" if mark == f"ready:{contract_hash(body)}" else gate
    tip = branch_tip(config, ticket_branch(fields, ticket.ticket_id))
    return "" if mark == f"merge:{tip}" else gate


def ticket_branch(fields: Mapping[str, object], ticket_id: str) -> str:
    return str(fields.get("branch") or "").strip() or worktree.branch_name(ticket_id)


def branch_tip(config: Config, branch: str) -> str:
    """Commit at the tip of ``branch``, or '' when the branch is gone."""
    if not gitops.branch_exists(config.project_root, branch):
        return ""
    return gitops.rev_parse(config.project_root, branch)


def _signature_problem(config: Config, fields: Mapping[str, object], reviewer: str) -> str:
    """With ``require_signed_approvals``: why this approval is not the engine's own, or ''."""
    if not config.require_signed_approvals:
        return ""
    return trust.signature_problem(
        config.project_root,
        str(fields.get("id") or ""),
        str(fields.get("approved_sha") or "").strip(),
        reviewer,
        str(fields.get("approval_sig") or "").strip(),
    )


def _release_problems(
    config: Config,
    fields: Mapping[str, object],
    branch: str,
    tip: str,
    default_branch: str,
) -> list[str]:
    """require_review / require_integration conditions for ``done``."""
    problems: list[str] = []
    reviewer = str(fields.get("reviewer") or "").strip()
    owner = str(fields.get("owner") or "").strip()
    if config.require_review:
        if not reviewer:
            problems.append(
                "not approved: a reviewer runs 'kahnban approve <ID> --reviewer <name>'"
            )
        elif reviewer.lower() == owner.lower():
            problems.append(f"approved by its own owner '{owner}'")
        elif tip and str(fields.get("approved_sha") or "").strip() != tip:
            problems.append(f"{branch} moved after approval; reject it and re-verify")
    if reviewer and (forged := _signature_problem(config, fields, reviewer)):
        problems.append(forged)
    if config.require_integration:
        integrated = str(fields.get("integrated_sha") or "").strip()
        if not integrated:
            problems.append(
                "not integrated: 'kahnban merge <ID>' tests the merged result before it lands"
            )
        elif not gitops.is_ancestor(config.project_root, integrated, default_branch):
            problems.append(f"integration commit {integrated[:12]} is not on '{default_branch}'")
        elif tip and not gitops.is_ancestor(config.project_root, tip, integrated):
            problems.append(f"{branch} has commits that were never integration-tested")
    return problems


def require_clean_tip(config: Config, tree: Path, branch: str) -> str:
    """Verify tests what will merge: the committed tip, nothing uncommitted."""
    output = gitops.run(tree, ["status", "--porcelain", "--untracked-files=all"]).stdout
    ignorable = (HANDOFF_IN_WORKTREE, *config.shared_caches)
    dirty = [
        path
        for path in (
            line[3:].split(" -> ")[-1].strip().strip('"')
            for line in output.splitlines()
            if line.strip()
        )
        if not path_within(path, ignorable)
    ]
    if dirty:
        raise GateError(
            f"{tree.name} has uncommitted changes; verify tests the committed tip "
            f"of {branch}, so commit them (or .gitignore build output) first:\n"
            + "\n".join(f"  - {path}" for path in dirty)
        )
    head = gitops.rev_parse(tree, "HEAD")
    tip = gitops.rev_parse(config.project_root, branch)
    if head != tip:
        raise GateError(
            f"{tree.name} is at {head[:12]}, not at the tip of {branch} ({tip[:12]})"
        )
    return head


def _proof_plan(
    config: Config,
    ticket_id: str,
    fields: Mapping[str, object],
    body: str,
    branch: str,
    cwd: Path,
) -> tuple[str, list[str]]:
    """require_proof: (merge-base, changed source paths) for the red check."""
    if cwd == config.project_root or not gitops.branch_exists(config.project_root, branch):
        raise GateError(
            f"require_proof: {ticket_id} needs its ticket branch and worktree "
            "(claim with --worktree) so the change can be proven"
        )
    untested = untested_criteria_problem(fields, body)
    if untested:
        raise GateError(f"{ticket_id}: {untested}")
    base = gitops.merge_base(
        config.project_root, gitops.default_branch(config.project_root), branch
    )
    source = [
        path
        for path in gitops.diff_names(config.project_root, base, branch)
        if not path_within(path, (config.board_root, HANDOFF_IN_WORKTREE))
        and not is_test_path(config, path)
    ]
    if not source:
        raise GateError(
            f"require_proof: {branch} changes no source files, so there is "
            "nothing for its tests to prove"
        )
    return base, source


def _red_run(
    config: Config,
    ticket_id: str,
    tip: str,
    base: str,
    source: Sequence[str],
    feature: str,
) -> tuple[int, str]:
    """Feature tests on the verified commit with its source files reverted to base.

    Runs in a throwaway worktree: in the coder's own worktree, bytecode or a build
    cache keyed on file size and mtime can make the reverted source behave like
    the new one, and the check would refuse honest work.
    """
    tree = config.project_root / ".worktrees" / f".red-{ticket_id}"
    _remove_scratch_tree(config, tree)
    gitops.run(config.project_root, ["worktree", "add", "--detach", str(tree), tip])
    try:
        worktree.link_caches(config.project_root, tree, config.shared_caches)
        gitops.run(tree, ["restore", f"--source={base}", "--worktree", "--", *source])
        return run_block(config, feature, tree)
    finally:
        _remove_scratch_tree(config, tree)


@_refusals_reported
def verify(
    config: Config,
    ticket_id: str,
    *,
    manual_evidence: Path | None = None,
    force_scope: bool = False,
    reason: str = "",
    timestamp: datetime | None = None,
) -> VerifyResult:
    """``kahnban verify`` — runs the validation command itself (D4)."""
    target = config.verifying_column
    # ponytail: fixed budget of four timeouts; heartbeat the lock if verifies run longer
    with board_lock(config, hold_seconds=config.validation_timeout_sec * 4) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        if ticket.column != config.in_progress_column:
            raise GateError(
                f"{ticket.ticket_id} is in {ticket.column}; verify applies to "
                f"{config.in_progress_column}"
            )
        fields, body = frontmatter.parse(ticket.text)
        messages = list(lock_warnings)
        now = timestamp or datetime.now()
        if not verify_contract(config, ticket.ticket_id, fields, body):
            messages.append("[WARN] no contract_hash (claimed before contracts were frozen, or removed)")

        if manual_evidence is not None:
            evidence_path = Path(manual_evidence)
            if str(fields.get("validation_class", "")) != "visual-deferred":
                raise GateError(
                    "--manual-evidence is only accepted for tickets with "
                    "validation_class: visual-deferred"
                )
            if not evidence_path.is_file():
                raise GateError(f"evidence file not found: {evidence_path}")
            evidence = _truncate(
                evidence_path.read_text(encoding="utf-8", errors="replace"),
                config.log_output_max_bytes,
            )
            ticked_text = _tick_acceptance_criteria(ticket.text)
            if ticked_text != ticket.text:
                write_text(ticket.path, ticked_text)
                ticket = find_ticket(config, ticket.ticket_id)
            entry = (
                f"MANUAL-EVIDENCE (unverified) from {evidence_path.name} -> {target}\n"
                + _indent_output(evidence)
            )
            result = transition(
                config,
                ticket.ticket_id,
                target,
                log_entry=entry,
                timestamp=now,
            )
            messages.extend(result.messages)
            result.messages = messages
            return VerifyResult(
                ticket_id=ticket.ticket_id,
                passed=True,
                exit_code=0,
                command=f"(manual evidence: {evidence_path})",
                output=evidence,
                transition=result,
                messages=messages,
            )

        radius = parse_blast_radius(body)
        offenders, notes = diff_scope_problems(config, ticket, fields, radius)
        messages.extend(notes)
        if offenders:
            if not force_scope:
                raise GateError(
                    f"{ticket.ticket_id} changed paths outside its blast radius:\n"
                    + "\n".join(f"  - {path}" for path in offenders)
                    + "\nAmend '## Blast radius' during refinement, or override "
                    "with --force-scope --reason <why>"
                )
            if not reason.strip():
                raise GateError("--force-scope requires --reason")
            messages.append(
                "forced scope override: "
                + reason.strip()
                + " ["
                + ", ".join(offenders)
                + "]"
            )

        _require_allowed_commands(config, ticket.ticket_id, body)
        feat_cmd, reg_cmd = parse_validation_commands(config, body)
        worktree_field = str(fields.get("worktree") or "").strip()
        cwd = config.project_root
        if worktree_field:
            candidate = config.project_root / worktree_field
            if candidate.is_dir():
                cwd = candidate
            else:
                messages.append(
                    f"[WARN] recorded worktree {worktree_field} is missing; "
                    "running validation in the project root"
                )
        branch = ticket_branch(fields, ticket.ticket_id)
        tip = ""
        if cwd != config.project_root:
            tip = require_clean_tip(config, cwd, branch)
            messages.append(f"verifying {branch} at {tip[:12]}")
        proof_base, source_paths = (
            _proof_plan(config, ticket.ticket_id, fields, body, branch, cwd)
            if config.require_proof
            else ("", [])
        )
        criteria = [command for _, command in criterion_tests(body) if command]

        started = datetime.now()
        stages: list[tuple[str, str]] = []
        commands = [feat_cmd]
        messages.append(f"Running Tier 1 (Feature Tests): {feat_cmd}")
        exit_code, stage_output = run_block(config, feat_cmd, cwd)
        stages.append(("TIER 1: FEATURE TESTS", stage_output))
        feature_passed = exit_code == 0

        passed_criteria: set[str] = set()
        if exit_code == 0 and criteria:
            reports: list[str] = []
            for criterion in dict.fromkeys(criteria):
                code, criterion_output = run_command(config, criterion, cwd)
                reports.append(
                    f"[{'PASS' if code == 0 else 'FAIL'}] $ {criterion}\n{criterion_output}"
                )
                if code == 0:
                    passed_criteria.add(criterion)
                elif exit_code == 0:
                    exit_code = code
            stages.append(("ACCEPTANCE CRITERIA", "\n".join(reports)))
            commands.append(f"{len(passed_criteria)}/{len(set(criteria))} criterion tests")

        if exit_code == 0 and reg_cmd and reg_cmd != feat_cmd:
            messages.append(f"Running Tier 2 (Regression Tests): {reg_cmd}")
            exit_code, stage_output = run_block(config, reg_cmd, cwd)
            stages.append(("TIER 2: REGRESSION TESTS", stage_output))
            commands.append(reg_cmd)
        regression_passed = exit_code == 0

        if exit_code == 0 and proof_base:
            red_code, stage_output = _red_run(
                config, ticket.ticket_id, tip, proof_base, source_paths, feat_cmd
            )
            if red_code == 0:
                exit_code = 1
                stage_output += (
                    "\n[FAIL] the feature tests pass without this change, so they "
                    "do not prove it"
                )
            stages.append(("RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail)", stage_output))
            commands.append(f"red check vs {proof_base[:12]}")

        command = commands[0] if len(commands) == 1 else " && ".join(
            f"[{item}]" for item in commands
        )
        output = stages[0][1] if len(stages) == 1 else "\n\n".join(
            f"=== {title} ===\n{text}" for title, text in stages
        )
        duration = (datetime.now() - started).total_seconds()
        artifact = _write_artifact(config, ticket.ticket_id, command, output, now)
        entry_lines = [
            f"verify exit={exit_code} in {duration:.1f}s (cwd={cwd.name})",
            f"    $ {command}",
            _indent_output(_truncate(output, config.log_output_max_bytes)),
            f"    full output: {_relative(config, artifact)}",
        ]
        if messages:
            entry_lines.insert(1, "    " + "; ".join(messages))
        verification = {
            "feature_passed": feature_passed,
            "regression_passed": regression_passed,
            "artifact": _relative(config, artifact),
        }

        if exit_code == 0:
            ticked_text = _tick_passed_criteria(ticket.text, passed_criteria)
            if ticked_text != ticket.text:
                write_text(ticket.path, ticked_text)
                ticket = find_ticket(config, ticket.ticket_id)
            entry = "\n".join([entry_lines[0] + f" -> {target}", *entry_lines[1:]])
            # A fresh verify invalidates any earlier approval or integration.
            result = transition(
                config,
                ticket.ticket_id,
                target,
                log_entry=entry,
                fm_updates={
                    "verified_sha": tip,
                    "reviewer": "",
                    "approved_sha": "",
                    "approval_sig": "",
                    "integrated_sha": "",
                },
                timestamp=now,
                verification=verification,
            )
            drop_lease(config, ticket.ticket_id)
            # Trigger post-verify hook
            try:
                from kahnban.hooks import run_hook
                from kahnban.handoff import get_handoff_path
                h_path = get_handoff_path(config.project_root, ticket.ticket_id)
                run_hook(
                    config.project_root,
                    "post-verify",
                    ticket.ticket_id,
                    column=target,
                    worktree=worktree_field,
                    baton_path=str(h_path) if h_path.exists() else "",
                )
            except Exception as hook_err:
                messages.append(f"[WARN] post-verify hook error: {hook_err}")
            messages.extend(result.messages)
            result.messages = messages
            return VerifyResult(
                ticket_id=ticket.ticket_id,
                passed=True,
                exit_code=0,
                command=command,
                output=output,
                artifact=artifact,
                transition=result,
                messages=messages,
            )

        # Failed attempts stay in the audit trail; the ticket does not move.
        entry = "\n".join([entry_lines[0] + " (no transition)", *entry_lines[1:]])
        text = _apply_frontmatter(
            ticket.text, {"updated": now.date().isoformat()}
        )
        text = frontmatter.append_log(text, log_line(entry, timestamp=now))
        write_text(ticket.path, text)
        rel = _relative(config, ticket.path)
        gitops.add(config.project_root, [rel])
        gitops.commit(
            config.project_root,
            f"kanban({ticket.ticket_id}): verify failed (exit {exit_code})",
            paths=[rel],
        )
        reason = f"verify failed (exit {exit_code}); full output: {verification['artifact']}"
        _refresh_baton(config, ticket.ticket_id, reason, messages, verification)
        _report_refusal(config, ticket.ticket_id, "verify", reason)
        return VerifyResult(
            ticket_id=ticket.ticket_id,
            passed=False,
            exit_code=exit_code,
            command=command,
            output=output,
            artifact=artifact,
            messages=messages,
        )


def _write_artifact(
    config: Config, ticket_id: str, command: str, output: str, when: datetime
) -> Path:
    directory = config.board_path / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8", newline="\n")
    path = directory / f"{ticket_id}-{when.strftime('%Y%m%d-%H%M%S')}.log"
    path.write_text(
        f"# {ticket_id} verify at {when.isoformat(timespec='seconds')}\n"
        f"# command: {command}\n\n{output}",
        encoding="utf-8",
        newline="\n",
        errors="replace",
    )
    return path


def is_board_or_meta_path(path: str, config: Config) -> bool:
    posix_p = path.replace("\\", "/")
    board_dir = str(config.board_root).replace("\\", "/")
    plans_dir = str(Path(config.board_root).parent).replace("\\", "/")
    return (
        posix_p.startswith(f"{board_dir}/")
        or (plans_dir != "." and posix_p.startswith(f"{plans_dir}/"))
        or posix_p.startswith(".agents/")
        or posix_p.startswith(".worktrees/")
    )


def is_branch_content_merged(repo: Path, branch: str, default_branch: str, config: Config) -> bool:
    """Return True if branch is merged or content-equivalent (squashed/rebased)."""
    if gitops.is_ancestor(repo, branch, default_branch):
        return True
    changed = gitops.diff_names(repo, default_branch, branch)
    scoped_changed = [p for p in changed if not is_board_or_meta_path(p, config)]
    if scoped_changed:
        diff = gitops.run(repo, ["diff", default_branch, branch, "--", *scoped_changed], check=False)
        return diff.returncode == 0 and not diff.stdout.strip()
    return True


@_refusals_reported
def done(
    config: Config,
    ticket_id: str,
    *,
    merge_commit: str | None = None,
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban done`` — requires the ticket branch to be merged (plan §2.2)."""
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        if ticket.column != config.verifying_column:
            raise GateError(
                f"{ticket.ticket_id} is in {ticket.column}; done applies to "
                f"{config.verifying_column}"
            )
        fields, body = frontmatter.parse(ticket.text)
        unfrozen = not verify_contract(config, ticket.ticket_id, fields, body)
        problems: list[str] = []

        checked, unchecked = checkboxes(body)
        if checked + unchecked == 0:
            problems.append("'## Acceptance criteria' has no checkboxes")
        if unchecked:
            problems.append(f"{unchecked} acceptance criteria are still unchecked")

        default_branch = gitops.default_branch(config.project_root)
        branch = ticket_branch(fields, ticket.ticket_id)
        tip = branch_tip(config, branch)
        problems.extend(_release_problems(config, fields, branch, tip, default_branch))
        merge_note = ""
        if merge_commit:
            sha = merge_commit.strip()
            if not gitops.commit_exists(config.project_root, sha):
                problems.append(f"--merge-commit {sha} does not exist in this repo")
            elif not gitops.is_ancestor(config.project_root, sha, default_branch):
                problems.append(
                    f"--merge-commit {sha} is not on '{default_branch}'"
                )
            else:
                merge_note = f"merge-commit: {gitops.rev_parse(config.project_root, sha)}"
        elif gitops.branch_exists(config.project_root, branch):
            if not is_branch_content_merged(config.project_root, branch, default_branch, config):
                problems.append(
                    f"branch '{branch}' is not merged into '{default_branch}'; "
                    "merge it or pass --merge-commit <sha>"
                )
            else:
                if gitops.is_ancestor(config.project_root, branch, default_branch):
                    merge_note = f"merge-commit: {gitops.rev_parse(config.project_root, branch)}"
                else:
                    merge_note = f"merge-type: squashed/rebased into {default_branch}"
        else:
            recorded = re.search(r"merge-commit:\s*([0-9a-fA-F]{7,40})", section(body, "Log"))
            if not recorded:
                problems.append(
                    f"branch '{branch}' no longer exists and no 'merge-commit: <sha>' "
                    "Log entry was found; pass --merge-commit <sha>"
                )
            elif not gitops.is_ancestor(
                config.project_root, recorded.group(1), default_branch
            ):
                problems.append(
                    f"recorded merge-commit {recorded.group(1)} is not on "
                    f"'{default_branch}'"
                )
            else:
                merge_note = f"merge-commit: {recorded.group(1)}"

        if problems:
            raise GateError(
                f"{ticket.ticket_id} cannot be marked done:\n"
                + "\n".join(f"  - {problem}" for problem in problems)
            )

        integrated = str(fields.get("integrated_sha") or "").strip()
        if integrated:
            merge_note = f"merge-commit: {integrated}"  # the merge itself, not the branch tip
        entry = f"done gate passed -> {config.done_column}"
        if merge_note:
            entry += f" | {merge_note}"
        if unfrozen:
            entry += " | [WARN] no contract_hash"
        result = transition(
            config,
            ticket.ticket_id,
            config.done_column,
            log_entry=entry,
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
        try:
            from kahnban.hooks import run_hook
            from kahnban.handoff import get_handoff_path
            h_path = get_handoff_path(config.project_root, ticket.ticket_id)
            run_hook(
                config.project_root,
                "post-done",
                ticket.ticket_id,
                column=config.done_column,
                baton_path=str(h_path) if h_path.exists() else "",
            )
        except Exception as hook_err:
            result.messages.append(f"[WARN] post-done hook error: {hook_err}")
        return result


def _verifying_ticket(config: Config, ticket_id: str, action: str) -> Ticket:
    ticket = find_ticket(config, ticket_id)
    if ticket.column != config.verifying_column:
        raise GateError(
            f"{ticket.ticket_id} is in {ticket.column}; {action} applies to "
            f"{config.verifying_column}"
        )
    return ticket


@_refusals_reported
def approve(
    config: Config,
    ticket_id: str,
    reviewer: str,
    *,
    note: str = "",
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban approve`` — someone other than the owner signs off the verified tip."""
    reviewer = reviewer.strip()
    if not reviewer:
        raise GateError("--reviewer is required to approve a ticket")
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = _verifying_ticket(config, ticket_id, "approve")
        fields, body = frontmatter.parse(ticket.text)
        verify_contract(config, ticket.ticket_id, fields, body)
        owner = str(fields.get("owner") or "").strip()
        if reviewer.lower() == owner.lower():
            raise GateError(
                f"{ticket.ticket_id} is owned by '{owner}'; a different reviewer must approve it"
            )
        branch = ticket_branch(fields, ticket.ticket_id)
        tip = branch_tip(config, branch)
        verified = str(fields.get("verified_sha") or "").strip()
        if tip and verified and tip != verified:
            raise GateError(
                f"{branch} moved since verify ({verified[:12]} -> {tip[:12]}); "
                "reject it so the new commits are verified"
            )
        entry = f"approved by {reviewer}" + (f" at {tip[:12]}" if tip else "")
        if note.strip():
            entry += f": {note.strip()}"
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry=entry,
            fm_updates={
                "reviewer": reviewer,
                "approved_sha": tip,
                "approval_sig": (
                    trust.sign(config.project_root, ticket.ticket_id, tip, reviewer)
                    if config.require_signed_approvals and not os.environ.get("KAHNBAN_ROLE")
                    else ""  # a worker does not sign; the runner countersigns once it has checked
                ),
            },
            commit_message=f"kanban({ticket.ticket_id}): approved by {reviewer}",
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
        return result


def countersign(
    config: Config, ticket_id: str, *, timestamp: datetime | None = None
) -> TransitionResult:
    """The runner signs an approval a worker recorded, once it matches the reviewed tip."""
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = _verifying_ticket(config, ticket_id, "countersign")
        fields, _ = frontmatter.parse(ticket.text)
        reviewer = str(fields.get("reviewer") or "").strip()
        approved = str(fields.get("approved_sha") or "").strip()
        tip = branch_tip(config, ticket_branch(fields, ticket.ticket_id))
        if not reviewer or approved != tip:
            raise GateError(f"{ticket.ticket_id} has no approval of the current tip to countersign")
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry=f"approval by {reviewer} countersigned by the runner at {tip[:12]}",
            fm_updates={"approval_sig": trust.sign(config.project_root, ticket.ticket_id, tip, reviewer)},
            commit_message=f"kanban({ticket.ticket_id}): approval countersigned",
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
        return result


@_refusals_reported
def reject(
    config: Config,
    ticket_id: str,
    reviewer: str,
    message: str,
    *,
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban reject`` — send a verified ticket back to its coder, with the reasons.

    The reasons are committed to the ticket's ``## Log``; every box is unticked so
    the next verify has to earn them again.
    """
    if not message.strip():
        raise GateError("a rejection needs a message saying what to fix")
    reviewer = reviewer.strip() or "reviewer"
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = _verifying_ticket(config, ticket_id, "reject")
        unticked = _tick_acceptance_criteria(ticket.text, ticked=False)
        if unticked != ticket.text:
            write_text(ticket.path, unticked)
        result = transition(
            config,
            ticket.ticket_id,
            config.in_progress_column,
            log_entry=f"rejected by {reviewer}:\n{_indent_output(message.strip())}",
            fm_updates={
                "verified_sha": "",
                "reviewer": "",
                "approved_sha": "",
                "approval_sig": "",
                "integrated_sha": "",
            },
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
    from kahnban import handoff

    drop_lease(config, ticket.ticket_id)  # the old holder's session is over
    # The baton is a local mirror for the coder's prompt; the Log is the record.
    handoff.record_rejection_feedback(
        config.project_root, ticket.ticket_id, message.strip(), author=reviewer
    )
    return result


def _remove_scratch_tree(config: Config, tree: Path) -> None:
    """Remove a scratch worktree, unlinking cache junctions before git touches it."""
    for cache in config.shared_caches:
        link = tree / cache.replace("\\", "/").strip("/")
        if worktree.is_link(link):
            worktree.remove_link(link)
    if tree.exists():
        gitops.run(config.project_root, ["worktree", "remove", "--force", str(tree)], check=False)
    gitops.worktree_prune(config.project_root)
    if tree.exists():
        raise KahnbanError(f"could not remove scratch worktree {tree}; remove it by hand")


@_refusals_reported
def merge(
    config: Config, ticket_id: str, *, timestamp: datetime | None = None
) -> VerifyResult:
    """``kahnban merge`` — the merge queue: test the merged result, then land it.

    The ticket branch is merged onto the current default branch in a throwaway
    worktree, the feature and regression tests run on that result, and the
    default branch is fast-forwarded only if they pass. The board lock
    serializes merges, so each one is tested against everything merged before it.
    """
    with board_lock(config, hold_seconds=config.validation_timeout_sec * 3) as lock_warnings:
        default_branch = _require_board_branch(config)
        ticket = _verifying_ticket(config, ticket_id, "merge")
        fields, body = frontmatter.parse(ticket.text)
        verify_contract(config, ticket.ticket_id, fields, body)
        branch = ticket_branch(fields, ticket.ticket_id)
        tip = branch_tip(config, branch)
        if not tip:
            raise GateError(f"{branch} does not exist; there is nothing to merge")
        reviewer = str(fields.get("reviewer") or "").strip()
        if config.require_review and (
            not reviewer or str(fields.get("approved_sha") or "").strip() != tip
        ):
            raise GateError(
                f"{ticket.ticket_id} is not approved at {tip[:12]}; a reviewer runs "
                f"'kahnban approve {ticket.ticket_id} --reviewer <name>' first"
            )
        if reviewer and (forged := _signature_problem(config, fields, reviewer)):
            raise GateError(f"{ticket.ticket_id}: {forged}")
        _require_allowed_commands(config, ticket.ticket_id, body)
        feat_cmd, reg_cmd = parse_validation_commands(config, body)
        messages = list(lock_warnings)
        now = timestamp or datetime.now()
        base = gitops.rev_parse(config.project_root, default_branch)
        tree = config.project_root / ".worktrees" / f".merge-{ticket.ticket_id}"
        _remove_scratch_tree(config, tree)
        gitops.run(config.project_root, ["worktree", "add", "--detach", str(tree), base])
        stages: list[tuple[str, str]] = []
        try:
            _, warnings = worktree.link_caches(config.project_root, tree, config.shared_caches)
            messages.extend(f"[WARN] {warning}" for warning in warnings)
            title = str(fields.get("title") or ticket.ticket_id)
            merged = gitops.run(
                tree,
                ["merge", "--no-ff", "--no-edit", "-m", f"merge {branch}: {title}", branch],
                check=False,
            )
            if merged.returncode != 0:
                conflicts = gitops.run(
                    tree, ["diff", "--name-only", "--diff-filter=U"], check=False
                ).stdout.split()
                raise GateError(
                    f"{branch} does not merge cleanly onto {default_branch}; rebase it, "
                    "re-verify, and merge again:\n"
                    + "\n".join(f"  - {path}" for path in conflicts or [merged.stderr.strip()])
                )
            merge_sha = gitops.rev_parse(tree, "HEAD")
            exit_code, output = run_block(config, feat_cmd, tree)
            stages.append(("INTEGRATION: FEATURE TESTS", output))
            if exit_code == 0 and reg_cmd and reg_cmd != feat_cmd:
                exit_code, output = run_block(config, reg_cmd, tree)
                stages.append(("INTEGRATION: REGRESSION TESTS", output))
        finally:
            _remove_scratch_tree(config, tree)

        command = f"merge {branch} onto {default_branch} {base[:12]}"
        output = "\n\n".join(f"=== {heading} ===\n{text}" for heading, text in stages)
        artifact = _write_artifact(config, ticket.ticket_id, command, output, now)
        detail = [
            f"    $ {command}",
            _indent_output(_truncate(output, config.log_output_max_bytes)),
            f"    full output: {_relative(config, artifact)}",
        ]
        if exit_code != 0:
            text = frontmatter.append_log(
                ticket.text,
                log_line(
                    "\n".join([f"merge refused: integration tests exit={exit_code}", *detail]),
                    timestamp=now,
                ),
            )
            write_text(ticket.path, text)
            rel = _relative(config, ticket.path)
            gitops.add(config.project_root, [rel])
            gitops.commit(
                config.project_root,
                f"kanban({ticket.ticket_id}): merge refused (exit {exit_code})",
                paths=[rel],
            )
            reason = (
                f"merge refused: integration tests exit={exit_code}; "
                f"full output: {_relative(config, artifact)}"
            )
            _refresh_baton(config, ticket.ticket_id, reason, messages)
            _report_refusal(config, ticket.ticket_id, "merge", reason)
            return VerifyResult(
                ticket_id=ticket.ticket_id,
                passed=False,
                exit_code=exit_code,
                command=command,
                output=output,
                artifact=artifact,
                messages=messages,
            )

        gitops.run(config.project_root, ["merge", "--ff-only", merge_sha])
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry="\n".join(
                [f"integrated into {default_branch} | merge-commit: {merge_sha}", *detail]
            ),
            fm_updates={"integrated_sha": merge_sha},
            commit_message=f"kanban({ticket.ticket_id}): integrated into {default_branch}",
            timestamp=now,
        )
        messages.extend(result.messages)
        result.messages = messages
        return VerifyResult(
            ticket_id=ticket.ticket_id,
            passed=True,
            exit_code=0,
            command=command,
            output=output,
            artifact=artifact,
            transition=result,
            messages=messages,
        )


@_refusals_reported
def move(
    config: Config,
    ticket_id: str,
    target_column: str,
    *,
    reason: str,
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban move`` — the always-logged escape hatch."""
    if not reason.strip():
        raise GateError("--reason is required for a manual move")
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        result = transition(
            config,
            ticket.ticket_id,
            target_column,
            log_entry=(
                f"manual move {ticket.column} -> {target_column}: {reason.strip()}"
            ),
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *result.messages]
        return result


@_refusals_reported
def cleanup(
    config: Config,
    ticket_id: str,
    *,
    abandon: bool = False,
    reason: str = "",
    timestamp: datetime | None = None,
) -> TransitionResult:
    """``kahnban cleanup`` — remove junctions, worktree, and branch (§3.4)."""
    with board_lock(config) as lock_warnings:
        _require_board_branch(config)
        ticket = find_ticket(config, ticket_id)
        if ticket.column != config.done_column and not abandon:
            raise GateError(
                f"{ticket.ticket_id} is in {ticket.column}; cleanup applies to "
                f"{config.done_column} (override with --abandon --reason <why>)"
            )
        if abandon and not reason.strip():
            raise GateError("--abandon requires --reason")

        fields, _ = frontmatter.parse(ticket.text)
        junctions = _as_list(fields.get("junctions"))
        drop_lease(config, ticket.ticket_id)
        notes = worktree.teardown(
            config.project_root,
            ticket.ticket_id,
            junctions=junctions,
            force=abandon,
        )
        entry = "cleanup: " + "; ".join(notes)
        if abandon:
            entry = f"abandoned ({reason.strip()}) | " + entry
        result = transition(
            config,
            ticket.ticket_id,
            ticket.column,
            log_entry=entry,
            fm_updates={"branch": "", "worktree": "", "junctions": []},
            commit_message=f"kanban({ticket.ticket_id}): cleanup",
            timestamp=timestamp,
        )
        result.messages = [*lock_warnings, *notes, *result.messages]
        return result


# --- board scaffolding ------------------------------------------------------


def init_board(
    project_root: Path,
    *,
    prefix: str,
    columns: Sequence[str] = DEFAULT_COLUMNS,
    wip_limit: int = 3,
    validation_command: str = "",
    use_worktrees: bool = True,
    agentic: bool = False,
    commit: bool = True,
    timestamp: datetime | None = None,
) -> list[Path]:
    """``kahnban init`` — scaffold the Layer 0 storage contract and commit it."""
    root = Path(project_root).resolve()
    if not gitops.is_repo(root):
        raise ConfigError(f"{root} is not a git repository; run 'git init' first")
    config_path = root / CONFIG_RELATIVE
    if config_path.exists():
        raise ConfigError(f"board already initialized: {config_path}")

    payload = {
        "engine_min_version": __version__,
        "id_prefix": prefix.upper(),
        "board_root": "plans/tickets",
        "columns": list(columns),
        "done_column": columns[-1],
        "wip_limit": wip_limit,
        "use_worktrees": use_worktrees,
        "shared_caches": [],
        "validation_timeout_sec": 1800,
        "log_output_max_bytes": 65536,
        "required_headings": list(DEFAULT_REQUIRED_HEADINGS),
        "validation_command": validation_command,
        "require_proof": True,
        "require_review": True,
        "require_integration": True,
        "require_spec": False,
        "require_signed_approvals": True,
        "strict_hooks": True,
        "max_blast_radius_files": 3,
        "stale_after_days": 3,
        "allowed_commands": [],
        "design_doc_roots": ["plans"],
        "extensions": {},
        "ingest": {"heading_level": None, "section_aliases": {}},
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    written = [config_path]

    board_root = root / "plans" / "tickets"
    for column in [*columns, "archive"]:
        directory = board_root / column
        directory.mkdir(parents=True, exist_ok=True)
        keep = directory / ".gitkeep"
        write_text_atomic(keep, "")
        written.append(keep)

    template_source = Path(__file__).parent / "templates" / "ticket.md"
    template_target = board_root / TEMPLATE_NAME
    shutil.copyfile(template_source, template_target)
    written.append(template_target)

    if agentic:
        templates_dir = Path(__file__).parent / "templates"

        # 1. .agents/AGENTS.md
        agents_dir = root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agents_md = agents_dir / "AGENTS.md"
        shutil.copyfile(templates_dir / "agents.md", agents_md)
        written.append(agents_md)

        # 2. .agents/state/ACTIVE_SESSION.md
        state_dir = agents_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        active_sess = state_dir / "ACTIVE_SESSION.md"
        shutil.copyfile(templates_dir / "active_session.md", active_sess)

        # 3. .agents/specs/
        specs_dir = agents_dir / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        specs_keep = specs_dir / ".gitkeep"
        write_text_atomic(specs_keep, "")
        written.append(specs_keep)

        # 4. .agents/templates/
        agent_templates_dir = agents_dir / "templates"
        agent_templates_dir.mkdir(parents=True, exist_ok=True)
        for src_name, dst_name in (
            ("spec.md", "spec-template.md"),
            ("ticket.md", "ticket-template.md"),
            ("active_session.md", "active-session-template.md"),
            ("glossary.md", "glossary-template.md"),
            ("adr.md", "adr-template.md"),
        ):
            src_f = templates_dir / src_name
            dst_f = agent_templates_dir / dst_name
            if src_f.exists():
                shutil.copyfile(src_f, dst_f)
                written.append(dst_f)

        # 5. Root GLOSSARY.md
        glossary_file = root / "GLOSSARY.md"
        if not glossary_file.exists():
            shutil.copyfile(templates_dir / "glossary.md", glossary_file)
            written.append(glossary_file)

        # 6. Root ADR/
        adr_dir = root / "ADR"
        adr_dir.mkdir(parents=True, exist_ok=True)
        adr_keep = adr_dir / ".gitkeep"
        write_text_atomic(adr_keep, "")
        written.append(adr_keep)
        first_adr = adr_dir / "0001-record-architecture-decisions.md"
        if not first_adr.exists():
            shutil.copyfile(templates_dir / "adr.md", first_adr)
            written.append(first_adr)

        # 7. .agents/skills/ (Self-contained Matt Pocock engineering pipeline)
        from kahnban import skills
        skills.install_skills(root, harness="agents", source="bundled")
        skills_dst = agents_dir / "skills"
        if skills_dst.is_dir():
            for p in sorted(skills_dst.rglob("*")):
                if p.is_file():
                    written.append(p)

        # 8. ./learnings/ (Pattern-aggregating self-improvement queue)
        learnings_dir = root / "learnings"
        learnings_dir.mkdir(parents=True, exist_ok=True)
        learnings_archive = learnings_dir / "archive"
        learnings_archive.mkdir(parents=True, exist_ok=True)
        learnings_keep = learnings_dir / ".gitkeep"
        write_text_atomic(learnings_keep, "")
        written.append(learnings_keep)
        archive_keep = learnings_archive / ".gitkeep"
        write_text_atomic(archive_keep, "")
        written.append(archive_keep)

    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    additions = [
        entry
        for entry in (
            ".worktrees/",
            "plans/tickets/.artifacts/",
            "plans/tickets/.claim.lock",
            ".agents/state/",
            ".agents/handoffs/",
            HANDOFF_IN_WORKTREE,
            "__pycache__/",
            "*.pyc",
        )
        if entry not in existing
    ]
    if additions:
        prefix_text = existing if existing.endswith("\n") or not existing else existing + "\n"
        gitignore.write_text(
            prefix_text + "\n".join(additions) + "\n", encoding="utf-8", newline="\n"
        )
        written.append(gitignore)

    config = load_config(root, config_path, check_version=False)
    written.extend(sync(config, timestamp=timestamp))

    if commit:
        rel_paths = [_relative(config, path) for path in written]
        gitops.add(root, rel_paths)
        gitops.commit(root, f"kanban: initialize board ({prefix.upper()})", paths=rel_paths)
    return written
