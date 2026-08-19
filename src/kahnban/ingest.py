"""Turn markdown plans into board tickets.

Kahnban's entry points all converge on :class:`kahnban.core.TicketDraft`:

* **ideation** — ``kahnban capture`` writes one draft per rough idea,
* **a plan document** — ``kahnban ingest plan.md`` splits it into one draft per
  work section (AI-generated plans included),
* **a feature spec** — ``kahnban ingest --per-file spec.md`` keeps one document
  as one ticket,
* **a single ticket** — ``kahnban new`` builds a draft from a title.

Two rules keep the conduit honest:

1. **Ingestion never fabricates readiness.** Everything lands in the backlog
   column with acceptance boxes unchecked, whatever the source claimed. Use
   ``--ready`` to run each ticket through the real refinement gate; only tickets
   that genuinely satisfy it advance.
2. **Ingestion is idempotent.** Every ticket records ``source_doc``,
   ``source_anchor``, and ``source_hash``. Re-ingesting the same plan skips what
   already exists and reports sections whose source text changed, rather than
   creating duplicates.
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kahnban import core, frontmatter

WHOLE_DOCUMENT_ANCHOR = "(whole-document)"

#: Labels recognized as ticket fields, whether written as a subsection heading
#: (``### Acceptance criteria``) or an inline label (``**Acceptance:**``).
DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "problem": (
        "problem",
        "why",
        "context",
        "background",
        "rationale",
        "goal",
        "objective",
        "summary",
        "description",
    ),
    "acceptance": (
        "acceptance criteria",
        "acceptance",
        "success criteria",
        "done when",
        "definition of done",
        "exit criteria",
        "deliverables",
    ),
    "blast_radius": (
        "blast radius",
        "files",
        "files touched",
        "files to change",
        "affected files",
        "touches",
        "scope",
    ),
    "notes": (
        "implementation notes",
        "notes",
        "implementation",
        "approach",
        "design",
        "steps",
        "plan",
    ),
    "validation": (
        "validation",
        "verification",
        "tests",
        "test plan",
        "how to test",
        "validate",
        "test command",
    ),
    "depends_on": (
        "depends on",
        "depends_on",
        "dependencies",
        "blocked by",
        "prerequisites",
        "requires",
    ),
    "design_docs": ("design docs", "design_docs", "references", "see also"),
}


class IngestError(core.KahnbanError):
    """A plan document could not be turned into tickets."""


@dataclass
class IngestOptions:
    heading_level: int | None = None
    section: str | None = None
    per_file: bool = False
    chain: bool = False
    owner: str = "unassigned"
    update: bool = False
    promote: bool = False
    aliases: Mapping[str, Sequence[str]] = field(
        default_factory=lambda: DEFAULT_ALIASES
    )


def aliases_for(config: core.Config) -> dict[str, tuple[str, ...]]:
    """Field aliases, extended by ``board.config.json -> ingest.section_aliases``.

    Adopters add their own vocabulary ("Tests to add", "Risk") without changing
    engine code; configured names extend the defaults rather than replacing them.
    """
    merged = {name: tuple(values) for name, values in DEFAULT_ALIASES.items()}
    configured = config.ingest.get("section_aliases") or {}
    if not isinstance(configured, Mapping):
        raise IngestError("ingest.section_aliases must be an object of field -> names")
    for field_name, names in configured.items():
        if field_name not in merged:
            raise IngestError(
                f"unknown ingest alias field '{field_name}'; expected one of: "
                + ", ".join(sorted(merged))
            )
        if isinstance(names, str):
            names = [names]
        merged[field_name] = tuple(dict.fromkeys([*merged[field_name], *names]))
    return merged


def options_for(config: core.Config, **overrides: object) -> IngestOptions:
    """Build options from config defaults plus explicit overrides."""
    heading_level = overrides.pop("heading_level", None)
    if heading_level is None:
        configured = config.ingest.get("heading_level")
        heading_level = int(configured) if configured else None
    return IngestOptions(
        heading_level=heading_level,
        aliases=aliases_for(config),
        **overrides,  # type: ignore[arg-type]
    )


@dataclass
class ExistingSource:
    ticket_id: str
    column: str
    source_hash: str


@dataclass
class IngestReport:
    source: str
    drafts: list[core.TicketDraft] = field(default_factory=list)
    created: list[core.TransitionResult] = field(default_factory=list)
    updated: list[core.TransitionResult] = field(default_factory=list)
    unchanged: list[tuple[str, str]] = field(default_factory=list)
    drifted: list[tuple[str, str]] = field(default_factory=list)
    promoted: list[str] = field(default_factory=list)
    not_promoted: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "dry_run": self.dry_run,
            "drafts": [
                {
                    "title": draft.title,
                    "source_anchor": draft.source_anchor,
                    "acceptance": len(draft.acceptance),
                    "blast_radius": draft.blast_radius,
                    "has_validation": bool(draft.validation),
                    "depends_on": draft.depends_on,
                    "blocked_on": draft.blocked_on,
                }
                for draft in self.drafts
            ],
            "created": [
                {"ticket_id": r.ticket_id, "path": r.path.as_posix()}
                for r in self.created
            ],
            "updated": [
                {"ticket_id": r.ticket_id, "path": r.path.as_posix()}
                for r in self.updated
            ],
            "unchanged": [
                {"source_anchor": anchor, "ticket_id": ticket}
                for anchor, ticket in self.unchanged
            ],
            "drifted": [
                {"source_anchor": anchor, "ticket_id": ticket}
                for anchor, ticket in self.drifted
            ],
            "promoted": list(self.promoted),
            "not_promoted": [
                {"ticket_id": ticket, "reason": reason}
                for ticket, reason in self.not_promoted
            ],
            "warnings": list(self.warnings),
        }


# --- document structure -----------------------------------------------------


@dataclass
class Heading:
    level: int
    title: str
    line: int


@dataclass
class Section:
    title: str
    level: int
    ancestors: list[str]
    lines: list[str]

    @property
    def anchor(self) -> str:
        parts = [core.slugify(part, max_length=40) for part in [*self.ancestors, self.title]]
        return "/".join(part for part in parts if part)[:120]

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip("\n")


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
#: ``Acceptance:``, ``**Acceptance:**``, ``- **Files:** a, b`` — group 1 is the
#: opening emphasis marker (so the closing one can be stripped off the value).
LABEL_PATTERN = re.compile(
    r"^\s*(?:[-*+]\s+)?(\*\*|__)?\s*([A-Za-z][A-Za-z /_-]{1,40}?)\s*(?:\*\*|__)?\s*:\s*(.*)$"
)
CHECKBOX_LINE = re.compile(r"^\s*[-*+]\s*\[( |x|X)\]\s*(.*)$")
BULLET_LINE = re.compile(r"^\s*[-*+]\s+(.*)$")
BACKTICK_SPAN = re.compile(r"`([^`]+)`")
FENCE_BLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)


def _alias_lookup(aliases: Mapping[str, Sequence[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field_name, names in aliases.items():
        for name in names:
            lookup[_normalize_label(name)] = field_name
    return lookup


def _normalize_label(text: str) -> str:
    cleaned = text.strip().strip("*_#").strip()
    cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", cleaned).strip().lower().rstrip(":")


def _match_key(text: str) -> str:
    """Loosen ``--section`` matching: dashes, case, and spacing all normalize.

    A plan written with an em dash still matches a hyphen typed on the command
    line, which is otherwise a maddening near-miss.
    """
    cleaned = re.sub(r"[‐-―−]", "-", text)
    cleaned = re.sub(r"[\s\-]+", " ", cleaned)
    return cleaned.strip().casefold()


def _strip_leading_enumeration(title: str) -> str:
    """``### 3.1 Add the widget`` -> ``Add the widget``.

    Only numbered prefixes are removed: ``Ticket one`` keeps its first word,
    while ``Phase 2 - do the thing`` and ``1. Do the thing`` lose theirs.
    """
    cleaned = re.sub(
        r"^(?:phase|step|task|ticket|item)\s+\d+[\w.]*\s*[-\u2014:]?\s*",
        "",
        title.strip(),
        flags=re.I,
    )
    cleaned = re.sub(r"^\d+(?:[.)]\d+)*[.):]?\s*[-\u2014:]?\s*", "", cleaned)
    return cleaned.strip() or title.strip()


def iter_headings(lines: Sequence[str]) -> list[Heading]:
    """Headings outside fenced code blocks (a plan's snippets contain ``#``)."""
    headings: list[Heading] = []
    fence: str | None = None
    for index, line in enumerate(lines):
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        match = HEADING_PATTERN.match(line)
        if match:
            headings.append(
                Heading(level=len(match.group(1)), title=match.group(2).strip(), line=index)
            )
    return headings


def choose_heading_level(
    headings: Sequence[Heading], lookup: Mapping[str, str]
) -> int | None:
    """The deepest heading level that looks like a list of work items.

    Alias headings (``Problem``, ``Validation``, …) never count, so a document
    whose tickets are level 2 with alias subsections at level 3 still resolves
    to level 2.
    """
    counts: dict[int, int] = {}
    for heading in headings:
        if _normalize_label(heading.title) in lookup:
            continue
        counts[heading.level] = counts.get(heading.level, 0) + 1
    if not counts:
        return None
    plural = [level for level, count in counts.items() if count >= 2]
    if plural:
        return max(plural)
    return min(counts)


def split_sections(
    text: str,
    *,
    heading_level: int | None = None,
    section: str | None = None,
    aliases: Mapping[str, Sequence[str]] = DEFAULT_ALIASES,
) -> tuple[list[Section], list[str]]:
    """Split a plan into one :class:`Section` per work item."""
    body = frontmatter.normalize_newlines(text)
    if body.startswith("---\n"):
        try:
            _, body = frontmatter.parse(body)
        except frontmatter.FrontmatterError:
            pass  # not a frontmatter document; treat the whole file as prose
    lines = body.split("\n")
    headings = iter_headings(lines)
    lookup = _alias_lookup(aliases)
    warnings: list[str] = []

    scope_start, scope_end = 0, len(lines)
    scope_ancestors: list[str] = []
    if section:
        wanted = _match_key(section)
        match = next(
            (h for h in headings if wanted in _match_key(h.title)),
            None,
        )
        if match is None:
            raise IngestError(f"no heading matching '{section}' in the document")
        scope_start = match.line + 1
        scope_end = next(
            (h.line for h in headings if h.line > match.line and h.level <= match.level),
            len(lines),
        )
        scope_ancestors = [match.title]
        headings = [h for h in headings if scope_start <= h.line < scope_end]

    level = heading_level or choose_heading_level(headings, lookup)
    if level is None:
        return [], ["no headings found; treating the document as a single ticket"]

    work = [h for h in headings if h.level == level]
    if not work:
        return [], [f"no level-{level} headings found in scope"]

    # A document title (the only heading at the shallowest level) is dropped from
    # anchors: retitling the document must not orphan every ingested ticket.
    level_counts: dict[int, int] = {}
    for heading in headings:
        level_counts[heading.level] = level_counts.get(heading.level, 0) + 1
    shallowest = min(level_counts)
    document_levels = {shallowest} if level_counts[shallowest] == 1 else set()

    sections: list[Section] = []
    for position, heading in enumerate(work):
        end = next(
            (h.line for h in headings if h.line > heading.line and h.level <= level),
            scope_end,
        )
        enclosing = [
            h.title
            for h in headings
            if h.level < level
            and h.line < heading.line
            and h.level not in document_levels
            and not any(
                other.level <= h.level and h.line < other.line < heading.line
                for other in headings
            )
        ]
        ancestors = [*scope_ancestors, *enclosing]
        sections.append(
            Section(
                title=heading.title,
                level=level,
                ancestors=ancestors,
                lines=lines[heading.line + 1 : end],
            )
        )
        if not sections[-1].text.strip():
            warnings.append(f"section '{heading.title}' has no content")
    return sections, warnings


# --- section -> draft -------------------------------------------------------


def _blocks(
    lines: Sequence[str], lookup: Mapping[str, str]
) -> list[tuple[str, list[str]]]:
    """Group a section's lines into ``(field, lines)`` blocks.

    A block starts at a subsection heading or an inline ``Label:`` line whose
    label is a known alias; anything before the first label belongs to
    ``problem``.
    """
    blocks: list[tuple[str, list[str]]] = [("problem", [])]
    fence: str | None = None
    for line in lines:
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            fence = marker if fence is None else (None if fence == marker else fence)
            blocks[-1][1].append(line)
            continue
        if fence is not None:
            blocks[-1][1].append(line)
            continue

        heading = HEADING_PATTERN.match(line)
        if heading:
            field_name = lookup.get(_normalize_label(heading.group(2)))
            if field_name:
                blocks.append((field_name, []))
            else:
                # Preserve unmapped structure inside the notes section.
                blocks.append(("notes", [f"### {heading.group(2).strip()}"]))
            continue

        label = LABEL_PATTERN.match(line)
        if label and not CHECKBOX_LINE.match(line):
            field_name = lookup.get(_normalize_label(label.group(2)))
            if field_name:
                remainder = label.group(3).strip()
                if label.group(1):
                    # ``**Files:** a, b`` leaves the closing ``**`` on the value.
                    remainder = remainder.removeprefix(label.group(1)).strip()
                blocks.append((field_name, [remainder] if remainder else []))
                continue
        blocks[-1][1].append(line)
    return [(name, content) for name, content in blocks if any(l.strip() for l in content)]


def _extract_paths(lines: Iterable[str]) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    ignored: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        bullet = BULLET_LINE.match(line)
        if bullet:
            stripped = bullet.group(1).strip()
        spans = BACKTICK_SPAN.findall(stripped)
        candidates = spans if spans else re.split(r"[,;]| and ", stripped)
        for candidate in candidates:
            token = candidate.strip().strip("`\"'").rstrip(".,;:")
            if not token:
                continue
            if " " in token and not spans:
                ignored.append(token)
                continue
            paths.append(token)
    return paths, ignored


def _extract_refs(lines: Iterable[str]) -> list[str]:
    refs: list[str] = []
    for line in lines:
        stripped = line.strip()
        bullet = BULLET_LINE.match(line)
        if bullet:
            stripped = bullet.group(1).strip()
        if not stripped or stripped.lower() in {"none", "n/a", "-"}:
            continue
        for candidate in re.split(r"[,;]| and ", stripped):
            token = candidate.strip().strip("`\"'").rstrip(".,;:")
            if token and token.lower() not in {"none", "n/a"}:
                refs.append(token)
    return refs


def _extract_command(lines: Sequence[str]) -> str:
    text = "\n".join(lines)
    fenced = FENCE_BLOCK.search(text + "\n")
    if fenced:
        return fenced.group(1).strip()
    for line in lines:
        spans = BACKTICK_SPAN.findall(line)
        if spans:
            return spans[0].strip()
    for line in lines:
        if line.strip():
            return line.strip()
    return ""


def draft_from_section(
    section: Section,
    *,
    source_doc: str,
    anchor: str | None = None,
    aliases: Mapping[str, Sequence[str]] = DEFAULT_ALIASES,
    owner: str = "unassigned",
) -> core.TicketDraft:
    """Build one draft from one plan section."""
    lookup = _alias_lookup(aliases)
    draft = core.TicketDraft(
        title=_strip_leading_enumeration(section.title),
        owner=owner,
        source_doc=source_doc,
        source_anchor=anchor or section.anchor,
        source_hash=source_hash(section),
    )
    problem_parts: list[str] = []
    notes_parts: list[str] = []

    for field_name, lines in _blocks(section.lines, lookup):
        if field_name == "problem":
            problem_parts.append("\n".join(lines).strip())
        elif field_name == "notes":
            notes_parts.append("\n".join(lines).strip())
        elif field_name == "acceptance":
            for line in lines:
                checkbox = CHECKBOX_LINE.match(line)
                bullet = BULLET_LINE.match(line)
                if checkbox:
                    draft.acceptance.append(checkbox.group(2).strip())
                elif bullet:
                    draft.acceptance.append(bullet.group(1).strip())
                elif line.strip():
                    draft.acceptance.append(line.strip())
        elif field_name == "blast_radius":
            paths, ignored = _extract_paths(lines)
            draft.blast_radius.extend(paths)
            for entry in ignored:
                notes_parts.append(f"- unparsed blast-radius entry: {entry}")
        elif field_name == "validation":
            if not draft.validation:
                draft.validation = _extract_command(lines)
        elif field_name == "depends_on":
            draft.unresolved_dependencies.extend(_extract_refs(lines))
        elif field_name == "design_docs":
            paths, _ = _extract_paths(lines)
            draft.design_docs.extend(paths)

    # Checkbox lines written directly under the section (no label) are criteria.
    if not draft.acceptance and problem_parts:
        remaining: list[str] = []
        for line in "\n".join(problem_parts).split("\n"):
            checkbox = CHECKBOX_LINE.match(line)
            if checkbox:
                draft.acceptance.append(checkbox.group(2).strip())
            else:
                remaining.append(line)
        problem_parts = ["\n".join(remaining)]

    draft.problem = "\n".join(part for part in problem_parts if part.strip()).strip()
    draft.notes = "\n\n".join(part for part in notes_parts if part.strip()).strip()
    return draft


def source_hash(section: Section) -> str:
    payload = f"{section.title.strip()}\n{section.text.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def parse_document(
    text: str,
    *,
    source_doc: str,
    options: IngestOptions | None = None,
) -> tuple[list[core.TicketDraft], list[str]]:
    """Parse a whole plan document into drafts."""
    settings = options or IngestOptions()
    if settings.per_file:
        lines = frontmatter.normalize_newlines(text).split("\n")
        headings = iter_headings(lines)
        title = headings[0].title if headings else Path(source_doc).stem
        start = headings[0].line + 1 if headings else 0
        whole = Section(title=title, level=1, ancestors=[], lines=lines[start:])
        draft = draft_from_section(
            whole,
            source_doc=source_doc,
            anchor=WHOLE_DOCUMENT_ANCHOR,
            aliases=settings.aliases,
            owner=settings.owner,
        )
        return [draft], []

    sections, warnings = split_sections(
        text,
        heading_level=settings.heading_level,
        section=settings.section,
        aliases=settings.aliases,
    )
    if not sections:
        fallback = IngestOptions(
            per_file=True, owner=settings.owner, aliases=settings.aliases
        )
        drafts, _ = parse_document(text, source_doc=source_doc, options=fallback)
        return drafts, warnings

    drafts = [
        draft_from_section(
            section,
            source_doc=source_doc,
            aliases=settings.aliases,
            owner=settings.owner,
        )
        for section in sections
    ]
    seen: dict[str, int] = {}
    for draft in drafts:
        count = seen.get(draft.source_anchor, 0)
        if count:
            warnings.append(
                f"duplicate section anchor '{draft.source_anchor}'; "
                f"disambiguated as '{draft.source_anchor}~{count}'"
            )
            draft.source_anchor = f"{draft.source_anchor}~{count}"
        seen[draft.source_anchor] = count + 1
    return drafts, warnings


# --- idempotency and dependency wiring --------------------------------------


def existing_sources(config: core.Config) -> dict[tuple[str, str], ExistingSource]:
    """Map ``(source_doc, source_anchor)`` to the ticket that already covers it."""
    known: dict[tuple[str, str], ExistingSource] = {}
    for ticket in core.iter_tickets(config, include_archive=True):
        try:
            fields, _ = frontmatter.parse(ticket.text)
        except frontmatter.FrontmatterError:
            continue
        document = str(fields.get("source_doc") or "").strip()
        anchor = str(fields.get("source_anchor") or "").strip()
        if not document or not anchor:
            continue
        known[(_normalize_doc(document), anchor)] = ExistingSource(
            ticket_id=ticket.ticket_id,
            column=ticket.column,
            source_hash=str(fields.get("source_hash") or "").strip(),
        )
    return known


def _normalize_doc(value: str) -> str:
    return value.replace("\\", "/").strip().lstrip("./").lower()


def _title_index(config: core.Config) -> dict[str, str]:
    index: dict[str, str] = {}
    for ticket in core.iter_tickets(config, include_archive=True):
        try:
            fields, _ = frontmatter.parse(ticket.text)
        except frontmatter.FrontmatterError:
            continue
        title = str(fields.get("title") or "").strip()
        if title:
            index.setdefault(_normalize_label(title), ticket.ticket_id)
        anchor = str(fields.get("source_anchor") or "").strip()
        if anchor:
            index.setdefault(anchor.lower(), ticket.ticket_id)
        index.setdefault(ticket.ticket_id.lower(), ticket.ticket_id)
    return index


def resolve_dependencies(
    drafts: Sequence[core.TicketDraft],
    identifiers: Sequence[str],
    *,
    known_titles: Mapping[str, str],
    chain: bool = False,
) -> list[str]:
    """Turn dependency references into ticket IDs; block what cannot resolve."""
    warnings: list[str] = []
    local: dict[str, str] = {}
    for ticket_id, draft in zip(identifiers, drafts):
        local[_normalize_label(draft.title)] = ticket_id
        local[draft.source_anchor.lower()] = ticket_id

    for position, (ticket_id, draft) in enumerate(zip(identifiers, drafts)):
        resolved: list[str] = []
        unresolved: list[str] = []
        for reference in draft.unresolved_dependencies:
            key = _normalize_label(reference)
            target = (
                local.get(key)
                or local.get(reference.lower())
                or known_titles.get(key)
                or known_titles.get(reference.lower())
            )
            if target and target != ticket_id:
                resolved.append(target)
            elif target == ticket_id:
                warnings.append(f"{ticket_id} lists itself as a dependency; ignored")
            else:
                unresolved.append(reference)
        if chain and position > 0:
            previous = identifiers[position - 1]
            if previous not in resolved:
                resolved.append(previous)
        draft.depends_on = list(dict.fromkeys(resolved))
        draft.unresolved_dependencies = unresolved
        if unresolved:
            # Honest failure mode: the ticket cannot pass the ready gate until a
            # human resolves the reference, and the reason is on the ticket.
            draft.blocked_on = "unresolved dependency: " + ", ".join(unresolved)
            warnings.append(
                f"{ticket_id} has unresolved dependencies "
                f"({', '.join(unresolved)}); recorded in blocked_on"
            )
    return warnings


# --- orchestration ----------------------------------------------------------


def ingest_document(
    config: core.Config,
    path: Path,
    *,
    options: IngestOptions | None = None,
    dry_run: bool = False,
    timestamp: datetime | None = None,
) -> IngestReport:
    """Ingest one plan document into the backlog (one commit, or a preview)."""
    settings = options or IngestOptions()
    document = Path(path)
    if not document.is_file():
        raise IngestError(f"plan document not found: {document}")
    try:
        source_doc = (
            document.resolve()
            .relative_to(config.project_root.resolve())
            .as_posix()
        )
    except ValueError:
        source_doc = document.as_posix()

    text = document.read_text(encoding="utf-8", errors="replace")
    drafts, warnings = parse_document(text, source_doc=source_doc, options=settings)
    report = IngestReport(source=source_doc, warnings=list(warnings), dry_run=dry_run)
    if not drafts:
        report.warnings.append("nothing to ingest")
        return report

    known = existing_sources(config)
    fresh: list[core.TicketDraft] = []
    refresh: list[tuple[str, core.TicketDraft]] = []
    for draft in drafts:
        match = known.get((_normalize_doc(source_doc), draft.source_anchor))
        if match is None:
            fresh.append(draft)
            continue
        if match.source_hash == draft.source_hash:
            report.unchanged.append((draft.source_anchor, match.ticket_id))
            continue
        if settings.update and match.column in (
            config.backlog_column,
            config.refining_column,
        ):
            refresh.append((match.ticket_id, draft))
        else:
            report.drifted.append((draft.source_anchor, match.ticket_id))

    report.drafts = fresh
    if not fresh and not refresh:
        return report

    identifiers = core.allocate_ids(config, len(fresh))
    report.warnings.extend(
        resolve_dependencies(
            fresh,
            identifiers,
            known_titles=_title_index(config),
            chain=settings.chain,
        )
    )
    for draft in fresh:
        draft.log_note = f"ingested from {source_doc}#{draft.source_anchor}"
    if dry_run:
        return report

    with core.board_lock(config) as lock_warnings:
        report.warnings.extend(lock_warnings)
        if fresh:
            report.created = core.create_tickets(
                config,
                fresh,
                identifiers=identifiers,
                timestamp=timestamp,
                commit_message=(
                    f"kanban: ingest {len(fresh)} ticket(s) from {source_doc}"
                ),
            )
        for ticket_id, draft in refresh:
            report.updated.append(
                core.update_ticket_body(
                    config,
                    ticket_id,
                    draft,
                    note=(
                        f"re-ingested from {source_doc}#{draft.source_anchor} "
                        f"(source_hash {draft.source_hash})"
                    ),
                    timestamp=timestamp,
                )
            )

    if settings.promote:
        _promote(config, report, timestamp=timestamp)
    return report


def _promote(
    config: core.Config, report: IngestReport, *, timestamp: datetime | None
) -> None:
    """Run freshly ingested tickets through the real refinement gate."""
    for result in [*report.created, *report.updated]:
        ticket = core.find_ticket(config, result.ticket_id)
        if ticket.column == config.refining_column:
            pass
        elif ticket.column == config.backlog_column:
            core.move(
                config,
                result.ticket_id,
                config.refining_column,
                reason="ingested plan section entering refinement",
                timestamp=timestamp,
            )
        else:
            continue
        try:
            core.ready(config, result.ticket_id, timestamp=timestamp)
        except core.KahnbanError as error:
            report.not_promoted.append((result.ticket_id, str(error)))
            continue
        report.promoted.append(result.ticket_id)


def ingest(
    config: core.Config,
    paths: Sequence[Path],
    *,
    options: IngestOptions | None = None,
    dry_run: bool = False,
    timestamp: datetime | None = None,
) -> list[IngestReport]:
    """Ingest one or more plan documents, in order."""
    if not paths:
        raise IngestError("at least one plan document is required")
    return [
        ingest_document(
            config, path, options=options, dry_run=dry_run, timestamp=timestamp
        )
        for path in paths
    ]


def capture(
    config: core.Config,
    ideas: Sequence[str],
    *,
    owner: str = "unassigned",
    timestamp: datetime | None = None,
    dry_run: bool = False,
) -> IngestReport:
    """``kahnban capture`` — one backlog ticket per rough idea, one commit."""
    drafts = [
        core.TicketDraft(title=idea.strip(), owner=owner, log_note="captured")
        for idea in ideas
        if idea.strip()
    ]
    report = IngestReport(source="(capture)", drafts=drafts, dry_run=dry_run)
    if not drafts:
        report.warnings.append("no ideas to capture")
        return report
    if dry_run:
        return report
    with core.board_lock(config) as lock_warnings:
        report.warnings.extend(lock_warnings)
        report.created = core.create_tickets(
            config,
            drafts,
            timestamp=timestamp,
            commit_message=f"kanban: capture {len(drafts)} idea(s)",
        )
    return report


# --- reporting --------------------------------------------------------------


def console_safe(text: str) -> str:
    """Make source-derived text printable on the caller's console.

    Plan documents contain emoji and typographic dashes; ticket files keep them
    verbatim (they are written as UTF-8), but a cp1252 console cannot encode
    them, so the *rendered report* is downgraded to whatever stdout accepts.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        return text.encode(encoding, "replace").decode(encoding, "replace")
    except LookupError:  # pragma: no cover - unknown codec name
        return text.encode("ascii", "replace").decode("ascii")


def render_report(reports: Sequence[IngestReport]) -> str:
    lines: list[str] = []
    for report in reports:
        prefix = "[DRY-RUN] " if report.dry_run else ""
        lines.append(f"{prefix}Source: {console_safe(report.source)}")
        for draft in report.drafts:
            status = "would create" if report.dry_run else "drafted"
            lines.append(f"  - {status}: {console_safe(draft.title)}")
            lines.append(f"      anchor: {console_safe(draft.source_anchor)}")
            lines.append(
                f"      acceptance: {len(draft.acceptance)}"
                f" | blast radius: {len(draft.blast_radius)}"
                f" | validation: {'yes' if draft.validation else 'no'}"
            )
            if draft.depends_on:
                lines.append(f"      depends_on: {', '.join(draft.depends_on)}")
            if draft.blocked_on:
                lines.append(f"      blocked_on: {console_safe(draft.blocked_on)}")
        for result in report.created:
            lines.append(
                f"  [OK] created {result.ticket_id}: "
                f"{console_safe(result.path.name)}"
            )
        for result in report.updated:
            lines.append(f"  [OK] refreshed {result.ticket_id} from changed source")
        for anchor, ticket in report.unchanged:
            lines.append(f"  [OK] unchanged {ticket} ({console_safe(anchor)})")
        for anchor, ticket in report.drifted:
            lines.append(
                f"  [WARN] source changed for {ticket} "
                f"({console_safe(anchor)}); re-run with --update or "
                "reconcile by hand"
            )
        for ticket in report.promoted:
            lines.append(f"  [OK] {ticket} passed the ready gate")
        for ticket, reason in report.not_promoted:
            first = reason.split("\n")[0]
            lines.append(f"  [WARN] {ticket} stayed back: {console_safe(first)}")
        for warning in report.warnings:
            lines.append(f"  [WARN] {console_safe(warning)}")
        counts = (
            f"{len(report.created)} created, {len(report.updated)} refreshed, "
            f"{len(report.unchanged)} unchanged, {len(report.drifted)} drifted"
        )
        if report.dry_run:
            counts = f"{len(report.drafts)} would be created, {counts}"
        lines.append(f"  {counts}")
    return "\n".join(lines) + "\n"
