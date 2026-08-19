"""Board configuration, ticket lookup, gates, and the single transition writer.

Everything that changes board state passes through :func:`transition`, which
performs the four mandatory steps of plan §2.2: frontmatter mutation, ``## Log``
append, ``git mv`` + commit **on the default branch**, and projection regen.

Failures always raise.  Nothing here swallows exceptions; the CLI and MCP server
translate raised errors into stderr text and exit codes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kahnban import __version__, frontmatter, gitops, status, worktree

LOCK_NAME = ".claim.lock"
LOCK_STALE_SECONDS = 300
ARTIFACT_DIR = ".artifacts"
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
    design_doc_roots: tuple[str, ...] = ("plans",)
    extensions: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    ingest: Mapping[str, object] = field(default_factory=dict)

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
        if gitops.is_repo(root):
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
        design_doc_roots=tuple(raw.get("design_doc_roots") or ("plans",)),
        extensions=dict(raw.get("extensions") or {}),
        ingest=dict(raw.get("ingest") or {}),
    )
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


def write_text(path: Path, text: str) -> None:
    path.write_text(frontmatter.normalize_newlines(text), encoding="utf-8", newline="\n")


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
    """Declared paths under ``## Blast radius``, normalized to forward slashes."""
    entries: list[str] = []
    for line in section(body, "Blast radius").split("\n"):
        stripped = line.strip()
        if not stripped.startswith(("-", "*")):
            continue
        item = stripped[1:].strip().strip("`").strip('"').strip("'").strip()
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


# --- locking ----------------------------------------------------------------


@contextmanager
def board_lock(config: Config, *, stale_seconds: int = LOCK_STALE_SECONDS):
    """Exclusive board lock covering gate checks through commit (§3.3)."""
    lock_path = config.board_path / LOCK_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    descriptor: int | None = None
    for attempt in (1, 2):
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                holder = lock_path.read_text(encoding="utf-8").strip()
            except OSError:
                age, holder = 0.0, "unknown"
            if attempt == 1 and age > stale_seconds:
                warnings.append(
                    f"broke stale board lock after {int(age)}s (held by {holder})"
                )
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            raise LockError(
                f"board is locked by another kahnban process ({holder}); "
                f"retry once it finishes"
            ) from None
    assert descriptor is not None
    try:
        os.write(
            descriptor,
            f"pid={os.getpid()} at={datetime.now().isoformat(timespec='seconds')}\n".encode(),
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


def collect_records(config: Config) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for ticket in iter_tickets(config):
        record = {
            "id": ticket.ticket_id,
            "title": "",
            "status": config.status_for(ticket.column),
            "owner": "",
            "branch": "",
            "worktree": "",
            "updated": "",
            "column": ticket.column,
        }
        try:
            fields, _ = frontmatter.parse(ticket.text)
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
        records.append(record)
    return records


def sync(config: Config, *, timestamp: datetime | None = None) -> list[Path]:
    """Regenerate both projections; returns the paths written."""
    return status.write(
        config.plans_dir,
        collect_records(config),
        config.columns,
        timestamp=timestamp or datetime.now(),
        project_name=config.project_root.name,
    )


# --- the single transition writer -------------------------------------------


def _relative(config: Config, path: Path) -> str:
    return Path(path).resolve().relative_to(config.project_root.resolve()).as_posix()


def _require_board_branch(config: Config) -> str:
    """Board commits land on the default branch, never a ticket branch (D2)."""
    default = gitops.default_branch(config.project_root)
    current = gitops.current_branch(config.project_root)
    if current != default:
        raise GateError(
            f"board state must be committed on the default branch '{default}' but "
            f"'{current}' is checked out in {config.project_root}. "
            "Run kahnban from the main worktree."
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
) -> TransitionResult:
    """Move a ticket and commit the board change on the default branch."""
    valid_targets = [*config.columns, "archive"]
    if target_column not in valid_targets:
        raise GateError(
            f"unknown target column '{target_column}'; expected one of: "
            + ", ".join(valid_targets)
        )
    ticket = find_ticket(config, ticket_id)
    _require_board_branch(config)
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
    gitops.add(config.project_root, [_relative(config, path) for path in paths])
    message = commit_message or (
        f"kanban({ticket.ticket_id}): {ticket.column} -> {target_column}"
    )
    sha = gitops.commit(config.project_root, message)

    return TransitionResult(
        ticket_id=ticket.ticket_id,
        from_column=ticket.column,
        to_column=target_column,
        path=destination,
        commit=sha,
    )


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
    gitops.add(
        config.project_root,
        [_relative(config, path) for path in (*written, *projections)],
    )
    if commit_message is None:
        if len(results) == 1:
            commit_message = f"kanban({results[0].ticket_id}): create -> {column}"
        else:
            commit_message = (
                f"kanban: create {len(results)} tickets -> {column} "
                f"({results[0].ticket_id}..{results[-1].ticket_id})"
            )
    sha = gitops.commit(config.project_root, commit_message)
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
    problems.extend(extension_problems(config, fields, body, target))

    if problems:
        raise GateError(
            f"{ticket.ticket_id} is not ready:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )
    return transition(
        config,
        ticket.ticket_id,
        target,
        log_entry=f"ready gate passed -> {target}",
        timestamp=timestamp,
    )


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


def claim(
    config: Config,
    ticket_id: str,
    owner: str,
    *,
    create_worktree: bool | None = None,
    force: bool = False,
    force_overlap: bool = False,
    strict_wip: bool = False,
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

        if remote:
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

        for attempt in (1, 2):
            info: worktree.WorktreeInfo | None = None
            updates: dict[str, object] = {"owner": owner.strip()}
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
            result = transition(
                config,
                ticket.ticket_id,
                target,
                log_entry=log_entry.rstrip(" |"),
                fm_updates=updates,
                timestamp=timestamp,
            )
            result.messages = list(messages)

            if not remote:
                return result
            try:
                gitops.push(config.project_root, "origin", default_branch)
                return result
            except gitops.GitError as error:
                _rollback_commit(config, result.commit)
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


def _diff_scope_problems(
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
    board_prefix = normalize_path_entry(config.board_root)
    offenders = [
        path
        for path in changed
        if not normalize_path_entry(path).startswith(board_prefix + "/")
        and not path_within(path, radius)
    ]
    return offenders, []


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
    with board_lock(config) as lock_warnings:
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
        offenders, notes = _diff_scope_problems(config, ticket, fields, radius)
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

        command = validation_command(config, body)
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

        started = datetime.now()
        try:
            # The validation block is an author-provided shell command line
            # (documented PowerShell wrapper form), so a shell is required here.
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=config.validation_timeout_sec,
            )
            exit_code = completed.returncode
            output = (completed.stdout or "") + (completed.stderr or "")
        except subprocess.TimeoutExpired as expired:
            exit_code = 124
            output = (
                f"TIMEOUT after {config.validation_timeout_sec}s\n"
                + (expired.stdout or "" if isinstance(expired.stdout, str) else "")
                + (expired.stderr or "" if isinstance(expired.stderr, str) else "")
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

        if exit_code == 0:
            entry = "\n".join([entry_lines[0] + f" -> {target}", *entry_lines[1:]])
            result = transition(
                config, ticket.ticket_id, target, log_entry=entry, timestamp=now
            )
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
        gitops.add(config.project_root, [_relative(config, ticket.path)])
        gitops.commit(
            config.project_root,
            f"kanban({ticket.ticket_id}): verify failed (exit {exit_code})",
        )
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
        problems: list[str] = []

        checked, unchecked = checkboxes(body)
        if checked + unchecked == 0:
            problems.append("'## Acceptance criteria' has no checkboxes")
        if unchecked:
            problems.append(f"{unchecked} acceptance criteria are still unchecked")

        default_branch = gitops.default_branch(config.project_root)
        branch = str(fields.get("branch") or "").strip() or worktree.branch_name(
            ticket.ticket_id
        )
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
            if not gitops.is_ancestor(config.project_root, branch, default_branch):
                problems.append(
                    f"branch '{branch}' is not merged into '{default_branch}'; "
                    "merge it or pass --merge-commit <sha>"
                )
            else:
                merge_note = (
                    f"merge-commit: {gitops.rev_parse(config.project_root, branch)}"
                )
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

        entry = f"done gate passed -> {config.done_column}"
        if merge_note:
            entry += f" | {merge_note}"
        result = transition(
            config,
            ticket.ticket_id,
            config.done_column,
            log_entry=entry,
            timestamp=timestamp,
        )
        result.messages = list(lock_warnings)
        return result


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
        result.messages = list(lock_warnings)
        return result


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
        result.messages = [*lock_warnings, *notes]
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
        keep.write_text("", encoding="utf-8")
        written.append(keep)

    template_source = Path(__file__).parent / "templates" / "ticket.md"
    template_target = board_root / TEMPLATE_NAME
    shutil.copyfile(template_source, template_target)
    written.append(template_target)

    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    additions = [
        entry
        for entry in (".worktrees/", "plans/tickets/.artifacts/", "plans/tickets/.claim.lock")
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
        gitops.add(root, [_relative(config, path) for path in written])
        gitops.commit(root, f"kanban: initialize board ({prefix.upper()})")
    return written
