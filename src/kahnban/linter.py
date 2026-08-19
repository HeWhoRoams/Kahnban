"""Board lint rules BL01-BL17 (plan §4.4; BL17 covers ingest provenance).

Output is deliberately ASCII-only (``[OK]`` / ``[WARN]`` / ``[FAIL]``) so it
survives a cp1252 Windows console.  ``template.md`` is exempt from every rule and
``archive/`` is scanned only for ID uniqueness (BL03).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kahnban import core, frontmatter, gitops

RULES: dict[str, str] = {
    "BL01": "frontmatter parses, has an id, and uses no unsupported nesting",
    "BL02": "id matches <PREFIX>-<digits> and the filename starts with <ID>-",
    "BL03": "no duplicate ids across columns and archive",
    "BL04": "status matches the containing column",
    "BL05": "all required headings are present",
    "BL06": "ready and later: at least one acceptance checkbox",
    "BL07": "done: no unchecked checkboxes",
    "BL08": "in-progress and later: an owner is assigned",
    "BL09": "depends_on entries exist and are done from the ready column onward",
    "BL10": "extension field rules (enum, required_from, require_log_match)",
    "BL11": "referenced design_docs exist on disk",
    "BL12": "WIP limit respected",
    "BL13": "no extraneous files or subdirectories in column directories",
    "BL14": "in-progress: branch recorded in frontmatter",
    "BL15": "done: ticket branch merged into the default branch",
    "BL16": "no two in-progress tickets have overlapping blast radii",
    "BL17": "ingest provenance is unique and its source document exists",
}

VIOLATION = "violation"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    ticket: str = ""
    path: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "ticket": self.ticket,
            "path": self.path,
        }

    def render(self) -> str:
        marker = "[FAIL]" if self.severity == VIOLATION else "[WARN]"
        location = f" {self.ticket}" if self.ticket else ""
        origin = f" ({self.path})" if self.path else ""
        return f"{marker} {self.rule}{location}{origin}: {self.message}"


@dataclass
class LintResult:
    board_root: str = ""
    tickets_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    column_counts: dict[str, int] = field(default_factory=dict)

    @property
    def violations(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == VIOLATION]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def ok(self) -> bool:
        return not self.violations

    def add(
        self,
        rule: str,
        message: str,
        *,
        severity: str = VIOLATION,
        ticket: str = "",
        path: str = "",
    ) -> None:
        self.findings.append(
            Finding(
                rule=rule, severity=severity, message=message, ticket=ticket, path=path
            )
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "board_root": self.board_root,
            "tickets_checked": self.tickets_checked,
            "column_counts": self.column_counts,
            "violations": [f.as_dict() for f in self.violations],
            "warnings": [f.as_dict() for f in self.warnings],
        }


MERGE_COMMIT_PATTERN = re.compile(r"merge-commit:\s*([0-9a-fA-F]{7,40})")


def _relative(config: core.Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def lint(config: core.Config, *, strict: bool = False) -> LintResult:
    """Run every rule over the board; ``strict`` promotes WIP warnings."""
    result = LintResult(board_root=config.board_root)
    tickets = core.iter_tickets(config, include_archive=True)
    board_tickets = [t for t in tickets if t.column != "archive"]
    result.tickets_checked = len(board_tickets)
    result.column_counts = {
        column: sum(1 for t in tickets if t.column == column)
        for column in core.board_columns(config, include_archive=True)
    }

    parsed: dict[Path, tuple[Mapping[str, object], str]] = {}
    for ticket in tickets:
        location = _relative(config, ticket.path)
        try:
            fields, body = frontmatter.parse(ticket.text)
        except frontmatter.FrontmatterError as error:
            result.add("BL01", str(error), ticket=ticket.ticket_id, path=location)
            continue
        except OSError as error:
            result.add("BL01", f"cannot be read ({error})", path=location)
            continue
        if not str(fields.get("id") or "").strip():
            result.add(
                "BL01", "frontmatter has no 'id' key", ticket=ticket.ticket_id, path=location
            )
            continue
        parsed[ticket.path] = (fields, body)

    _check_duplicate_ids(config, result, tickets, parsed)

    for ticket in tickets:
        if ticket.path not in parsed:
            continue
        if ticket.column == "archive":
            continue  # archive is exempt from column invariants
        fields, body = parsed[ticket.path]
        _check_ticket(config, result, ticket, fields, body)

    _check_column_contents(config, result)
    _check_wip(config, result, strict=strict)
    _check_blast_radius_overlap(config, result, parsed)
    _check_provenance(config, result, tickets, parsed)
    return result


def _check_duplicate_ids(
    config: core.Config,
    result: LintResult,
    tickets: Sequence[core.Ticket],
    parsed: Mapping[Path, tuple[Mapping[str, object], str]],
) -> None:
    seen: dict[str, list[str]] = {}
    for ticket in tickets:
        identifier = ticket.ticket_id
        if ticket.path in parsed:
            frontmatter_id = str(parsed[ticket.path][0].get("id") or "").strip().upper()
            identifier = frontmatter_id or identifier
        seen.setdefault(identifier, []).append(
            f"{ticket.column}/{ticket.path.name}"
        )
    for identifier, locations in sorted(seen.items()):
        if len(locations) > 1:
            result.add(
                "BL03",
                "duplicate id in " + ", ".join(sorted(locations)),
                ticket=identifier,
            )


def _check_ticket(
    config: core.Config,
    result: LintResult,
    ticket: core.Ticket,
    fields: Mapping[str, object],
    body: str,
) -> None:
    location = _relative(config, ticket.path)
    identifier = str(fields.get("id") or ticket.ticket_id).strip().upper()

    def report(rule: str, message: str, severity: str = VIOLATION) -> None:
        result.add(rule, message, severity=severity, ticket=identifier, path=location)

    # BL02 — identity and filename agreement
    if not re.fullmatch(rf"{re.escape(config.id_prefix)}-\d+", identifier):
        report(
            "BL02",
            f"id '{identifier}' does not match {config.id_prefix}-<digits>",
        )
    if not ticket.path.name.startswith(f"{identifier}-"):
        report("BL02", f"filename does not start with '{identifier}-'")

    # BL04 — folders are the only status
    expected_status = config.status_for(ticket.column)
    actual_status = str(fields.get("status") or "").strip()
    if actual_status != expected_status:
        report(
            "BL04",
            f"status '{actual_status}' does not match column "
            f"'{ticket.column}' (expected '{expected_status}')",
        )

    # BL05 — required headings
    for heading in config.required_headings:
        if not core.has_section(body, heading):
            report("BL05", f"missing required heading '## {heading}'")

    checked, unchecked = core.checkboxes(body)
    at_or_after_ready = _at_or_after(config, ticket.column, config.ready_column)

    # BL06 / BL07 — acceptance criteria discipline
    if at_or_after_ready and checked + unchecked < 1:
        report("BL06", "no acceptance checkboxes from the ready column onward")
    if ticket.column == config.done_column and unchecked:
        report("BL07", f"{unchecked} unchecked checkbox(es) in a done ticket")

    # BL08 — ownership
    owner = str(fields.get("owner") or "").strip()
    if _at_or_after(config, ticket.column, config.in_progress_column):
        if not owner or owner.lower() == "unassigned":
            report("BL08", "no owner assigned")

    # BL09 — dependencies
    for dependency in core._as_list(fields.get("depends_on")):
        try:
            dependency_ticket = core.find_ticket(config, dependency)
        except core.KahnbanError:
            report("BL09", f"depends_on '{dependency}' does not exist")
            continue
        if at_or_after_ready and dependency_ticket.column != config.done_column:
            report(
                "BL09",
                f"depends_on '{dependency}' is in {dependency_ticket.column}, "
                f"not {config.done_column}",
            )

    # BL10 — extension fields
    for problem in core.extension_problems(config, fields, body, ticket.column):
        report("BL10", problem)

    # BL11 — design docs
    for document in core._as_list(fields.get("design_docs")):
        if not _design_doc_exists(config, document):
            report("BL11", f"design_docs entry '{document}' does not exist on disk")

    # BL14 — branch recorded while in progress
    if ticket.column == config.in_progress_column:
        if not str(fields.get("branch") or "").strip():
            report("BL14", "no branch recorded in frontmatter")

    # BL15 — done tickets are merged
    if ticket.column == config.done_column:
        _check_merged(config, report, identifier, fields, body)


def _at_or_after(config: core.Config, column: str, reference: str) -> bool:
    if column not in config.columns or reference not in config.columns:
        return False
    return config.is_at_or_after(column, reference)


def _design_doc_exists(config: core.Config, document: str) -> bool:
    relative = document.replace("\\", "/").strip("/")
    if not relative:
        return False
    candidates = [config.project_root / relative]
    candidates.extend(
        config.project_root / root / relative for root in config.design_doc_roots
    )
    return any(candidate.exists() for candidate in candidates)


def _check_merged(
    config: core.Config,
    report,
    identifier: str,
    fields: Mapping[str, object],
    body: str,
) -> None:
    if not gitops.is_repo(config.project_root):
        report("BL15", "not a git repository; merge check skipped", WARNING)
        return
    try:
        default_branch = gitops.default_branch(config.project_root)
    except gitops.GitError as error:
        report("BL15", f"cannot resolve the default branch ({error})", WARNING)
        return

    branch = str(fields.get("branch") or "").strip()
    recorded = MERGE_COMMIT_PATTERN.search(core.section(body, "Log"))

    if branch and gitops.branch_exists(config.project_root, branch):
        if not gitops.is_ancestor(config.project_root, branch, default_branch):
            report(
                "BL15",
                f"branch '{branch}' is not merged into '{default_branch}'",
            )
        return
    if recorded:
        sha = recorded.group(1)
        if not gitops.commit_exists(config.project_root, sha):
            report(
                "BL15",
                f"recorded merge-commit {sha} is not present in this clone; "
                "merge check skipped",
                WARNING,
            )
        elif not gitops.is_ancestor(config.project_root, sha, default_branch):
            report(
                "BL15",
                f"recorded merge-commit {sha} is not on '{default_branch}'",
            )
        return
    report(
        "BL15",
        "branch was cleaned up and no 'merge-commit: <sha>' Log entry was "
        "recorded; merge cannot be verified",
        WARNING,
    )


def _check_column_contents(config: core.Config, result: LintResult) -> None:
    for column in config.columns:
        directory = config.board_path / column
        if not directory.is_dir():
            result.add("BL13", f"column directory is missing: {column}", severity=WARNING)
            continue
        for entry in sorted(directory.iterdir()):
            location = _relative(config, entry)
            if entry.is_dir():
                result.add(
                    "BL13",
                    f"unexpected subdirectory in column {column}: {entry.name}",
                    path=location,
                )
                continue
            if entry.name == ".gitkeep" or entry.suffix.lower() == ".md":
                continue
            result.add(
                "BL13",
                f"extraneous non-markdown file in column {column}: {entry.name}",
                path=location,
            )


def _check_wip(config: core.Config, result: LintResult, *, strict: bool) -> None:
    directory = config.board_path / config.in_progress_column
    if not directory.is_dir():
        return
    count = sum(
        1
        for path in directory.glob("*.md")
        if path.name != core.TEMPLATE_NAME
    )
    if count > config.wip_limit:
        result.add(
            "BL12",
            f"{count} tickets in {config.in_progress_column} exceeds the WIP "
            f"limit of {config.wip_limit}",
            severity=VIOLATION if strict else WARNING,
        )


def _check_blast_radius_overlap(
    config: core.Config,
    result: LintResult,
    parsed: Mapping[Path, tuple[Mapping[str, object], str]],
) -> None:
    radii: list[tuple[str, list[str]]] = []
    for ticket in core.iter_tickets(config):
        if ticket.column != config.in_progress_column or ticket.path not in parsed:
            continue
        _, body = parsed[ticket.path]
        radii.append((ticket.ticket_id, core.parse_blast_radius(body)))

    for index, (left_id, left) in enumerate(radii):
        for right_id, right in radii[index + 1 :]:
            for mine, theirs in core.radius_overlaps(left, right):
                result.add(
                    "BL16",
                    f"blast radius '{mine}' overlaps {right_id} entry '{theirs}'",
                    ticket=left_id,
                )


def _check_provenance(
    config: core.Config,
    result: LintResult,
    tickets: Sequence[core.Ticket],
    parsed: Mapping[Path, tuple[Mapping[str, object], str]],
) -> None:
    """BL17 — two tickets must never claim the same plan section.

    A duplicated ``(source_doc, source_anchor)`` pair means a plan was ingested
    twice; the pair is what makes re-ingest idempotent.
    """
    claims: dict[tuple[str, str], list[str]] = {}
    for ticket in tickets:
        if ticket.path not in parsed:
            continue
        fields, _ = parsed[ticket.path]
        document = str(fields.get("source_doc") or "").strip()
        anchor = str(fields.get("source_anchor") or "").strip()
        location = _relative(config, ticket.path)
        if not document and not anchor:
            continue
        if bool(document) != bool(anchor):
            result.add(
                "BL17",
                "source_doc and source_anchor must be set together "
                f"(source_doc={document!r}, source_anchor={anchor!r})",
                severity=WARNING,
                ticket=ticket.ticket_id,
                path=location,
            )
            continue
        normalized = document.replace("\\", "/").strip().lstrip("./").lower()
        claims.setdefault((normalized, anchor), []).append(ticket.ticket_id)
        if not (config.project_root / document).exists():
            result.add(
                "BL17",
                f"source_doc '{document}' no longer exists; re-ingest cannot "
                "reconcile this ticket",
                severity=WARNING,
                ticket=ticket.ticket_id,
                path=location,
            )
    for (document, anchor), owners in sorted(claims.items()):
        if len(owners) > 1:
            result.add(
                "BL17",
                f"{len(owners)} tickets claim {document}#{anchor}: "
                + ", ".join(sorted(owners)),
                ticket=sorted(owners)[0],
            )


def render_text(result: LintResult) -> str:
    lines = [f"Kahnban board lint: {result.board_root}"]
    for finding in result.findings:
        lines.append(finding.render())
    counts = ", ".join(
        f"{column}={count}" for column, count in result.column_counts.items()
    )
    lines.append(f"Columns: {counts}")
    if result.ok and not result.warnings:
        lines.append(f"[OK] {result.tickets_checked} ticket(s), 0 violations")
    else:
        lines.append(
            f"[{'OK' if result.ok else 'FAIL'}] {result.tickets_checked} ticket(s), "
            f"{len(result.violations)} violation(s), {len(result.warnings)} warning(s)"
        )
    return "\n".join(lines) + "\n"


def render_json(result: LintResult) -> str:
    return json.dumps(result.as_dict(), indent=2, ensure_ascii=True) + "\n"
