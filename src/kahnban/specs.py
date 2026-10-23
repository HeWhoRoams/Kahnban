"""Specs: the approved statement of intent every ticket traces back to.

A spec is ``.agents/specs/SPEC-NNN-<slug>.md``. Its ``## Requirements`` section
lists one requirement per line, ``- R1: <statement>``. ``kahnban spec approve`` is
the human gate: it marks the spec approved and freezes the requirements
(``requirements_hash``). Tickets name their spec in ``spec:`` and the requirements
they satisfy in ``covers: [R1, R2]``; ``kahnban spec coverage`` and lint rule BL18
check that every requirement is covered and every citation is real.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kahnban import core, frontmatter, gitops

SPEC_DIR = Path(".agents") / "specs"
SPEC_ID = re.compile(r"^SPEC-(\d+)$")
REQUIREMENT = re.compile(r"^\s*[-*]\s*(R\d+)\s*[:.)]\s*(\S.*)$")
TEMPLATE = Path(__file__).parent / "templates" / "spec.md"


@dataclass
class Spec:
    spec_id: str
    path: Path
    fields: dict
    body: str
    requirements: dict[str, str] = field(default_factory=dict)
    duplicates: list[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return str(self.fields.get("status") or "").strip().lower() == "approved"

    @property
    def frozen(self) -> bool:
        """Approved and its requirements unchanged since approval."""
        frozen = str(self.fields.get("requirements_hash") or "").strip()
        return self.approved and frozen == requirements_hash(self.body)


def requirements_hash(body: str) -> str:
    text = core.section(body, "Requirements")
    lines = [line.strip() for line in text.split("\n") if REQUIREMENT.match(line)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def load_spec(path: Path) -> Spec:
    fields, body = frontmatter.parse(core.read_text(path))
    spec_id = str(fields.get("id") or "-".join(path.stem.split("-")[:2])).strip().upper()
    spec = Spec(spec_id, path, fields, body)
    for line in core.section(body, "Requirements").split("\n"):
        match = REQUIREMENT.match(line)
        if not match:
            continue
        requirement_id, text = match.group(1).upper(), match.group(2).strip()
        if requirement_id in spec.requirements:
            spec.duplicates.append(requirement_id)
        spec.requirements[requirement_id] = text
    return spec


def iter_specs(config: core.Config) -> list[Spec]:
    directory = config.project_root / SPEC_DIR
    if not directory.is_dir():
        return []
    return [load_spec(path) for path in sorted(directory.glob("SPEC-*.md"))]


def find_spec(config: core.Config, spec_id: str) -> Spec:
    wanted = spec_id.strip().upper()
    for spec in iter_specs(config):
        if spec.spec_id.upper() == wanted:
            return spec
    raise core.KahnbanError(f"spec {wanted} not found under {SPEC_DIR.as_posix()}/")


def new_spec(config: core.Config, title: str, *, timestamp: datetime | None = None) -> Path:
    """``kahnban spec new`` — scaffold the next SPEC-NNN as a draft and commit it."""
    if not title.strip():
        raise core.GateError("a spec needs a title")
    with core.board_lock(config):
        core._require_board_branch(config)
        numbers = [
            int(match.group(1))
            for spec in iter_specs(config)
            if (match := SPEC_ID.match(spec.spec_id.upper()))
        ]
        spec_id = f"SPEC-{max(numbers, default=0) + 1:03d}"
        path = config.project_root / SPEC_DIR / f"{spec_id}-{core.slugify(title)}.md"
        text = core.read_text(TEMPLATE).replace("SPEC-000", spec_id)
        text = text.replace("Replace with the feature's name", title.strip())
        text = text.replace("1970-01-01", (timestamp or datetime.now()).date().isoformat())
        path.parent.mkdir(parents=True, exist_ok=True)
        core.write_text(path, text)
        relative = path.relative_to(config.project_root).as_posix()
        gitops.add(config.project_root, [relative])
        gitops.commit(config.project_root, f"spec({spec_id}): draft", paths=[relative])
        return path


def approve_spec(
    config: core.Config, spec_id: str, approver: str, *, timestamp: datetime | None = None
) -> Spec:
    """``kahnban spec approve`` — the human gate: freeze the requirements."""
    if not approver.strip():
        raise core.GateError("--by is required: approving a spec is a human decision")
    with core.board_lock(config):
        core._require_board_branch(config)
        spec = find_spec(config, spec_id)
        if not spec.requirements:
            raise core.GateError(
                f"{spec.spec_id} has no requirements: list them under '## Requirements' "
                "as '- R1: <statement>'"
            )
        if spec.duplicates:
            raise core.GateError(
                f"{spec.spec_id} repeats requirement ids: {', '.join(sorted(set(spec.duplicates)))}"
            )
        text = core._apply_frontmatter(
            core.read_text(spec.path),
            {
                "status": "approved",
                "approved_by": approver.strip(),
                "approved": (timestamp or datetime.now()).date().isoformat(),
                "requirements_hash": requirements_hash(spec.body),
            },
        )
        core.write_text(spec.path, text)
        relative = spec.path.relative_to(config.project_root).as_posix()
        gitops.add(config.project_root, [relative])
        gitops.commit(
            config.project_root,
            f"spec({spec.spec_id}): approved by {approver.strip()}",
            paths=[relative],
        )
        return load_spec(spec.path)


def citations(fields: dict) -> tuple[str, list[str]]:
    """The ``spec:`` a ticket names and the requirement ids it ``covers:``."""
    return (
        str(fields.get("spec") or "").strip().upper(),
        [item.upper() for item in core._as_list(fields.get("covers"))],
    )


def ticket_problems(config: core.Config, fields: dict, *, require_approved: bool) -> list[str]:
    """What is wrong with a ticket's traceability (ready gate and BL18)."""
    spec_id, covers = citations(fields)
    if not spec_id:
        return ["names no spec: set 'spec: SPEC-NNN' and 'covers: [R1]'"]
    try:
        spec = find_spec(config, spec_id)
    except core.KahnbanError as error:
        return [str(error)]
    problems: list[str] = []
    if require_approved and not spec.approved:
        problems.append(f"{spec_id} is not approved; a human runs 'kahnban spec approve {spec_id}'")
    elif spec.approved and not spec.frozen:
        problems.append(f"{spec_id}'s requirements changed after approval; re-approve it")
    if not covers:
        problems.append(f"covers no requirement of {spec_id}: set 'covers: [R1]'")
    unknown = [item for item in covers if item not in spec.requirements]
    if unknown:
        problems.append(f"covers requirements {spec_id} does not have: {', '.join(unknown)}")
    return problems


@dataclass
class Coverage:
    spec: Spec
    covered: dict[str, list[str]]
    uncovered: list[str]
    unknown: list[tuple[str, str]]

    @property
    def complete(self) -> bool:
        return not self.uncovered and not self.unknown


def coverage(config: core.Config, spec_id: str) -> Coverage:
    """Which tickets cover which requirements of one spec (archived tickets do not count)."""
    spec = find_spec(config, spec_id)
    covered: dict[str, list[str]] = {item: [] for item in spec.requirements}
    unknown: list[tuple[str, str]] = []
    for ticket in core.iter_tickets(config):
        try:
            fields, _ = frontmatter.parse(ticket.text)
        except frontmatter.FrontmatterError:
            continue
        cited, covers = citations(fields)
        if cited != spec.spec_id.upper():
            continue
        for item in covers:
            if item in covered:
                covered[item].append(ticket.ticket_id)
            else:
                unknown.append((ticket.ticket_id, item))
    return Coverage(
        spec=spec,
        covered=covered,
        uncovered=[item for item, tickets in covered.items() if not tickets],
        unknown=unknown,
    )
