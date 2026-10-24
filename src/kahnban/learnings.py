"""Learnings queue and deduplicating pattern aggregator for Kahnban.

Provides a git-backed `./learnings/` directory where session friction, mistakes,
and architectural insights are staged. Enforces the Lauren Tan clustering principle:
near-duplicate mistakes are augmented into existing records (tracking occurrences,
escalating severity, and logging environmental gaps) rather than polluting the
workspace with redundant one-off files.
"""

from __future__ import annotations

import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter, gitops

LEARNINGS_DIR_NAME = "learnings"
ARCHIVE_DIR_NAME = "archive"

SEVERITY_RANKS = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _sanitize_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _unescape_cell(text: str) -> str:
    return (text or "").replace("\\|", "|").strip()


@dataclass
class OccurrenceRow:
    index: int
    ticket_session: str
    location: str
    trigger: str

    def to_markdown(self) -> str:
        clean_loc = _sanitize_cell(self.location)
        loc = f"`{clean_loc}`" if clean_loc and not clean_loc.startswith("`") else clean_loc
        return f"| #{self.index} | {_sanitize_cell(self.ticket_session) or '-'} | {loc or '-'} | {_sanitize_cell(self.trigger) or '-'} |"


@dataclass
class LearningRecord:
    id: str
    title: str
    status: str = "pending"  # pending | promoted | declined | archived
    occurrences: int = 1
    severity: str = "medium"  # low | medium | high | critical
    category: str = "convention"  # architecture | typing-lint | testing | convention
    target_paths: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    resolved: str | None = None
    escalation_level: str | None = None  # level-1 | level-2 | level-3 | level-4
    problem: str = ""
    occurrences_table: list[OccurrenceRow] = field(default_factory=list)
    systemic_diagnosis: str = ""
    proposed_remediation: str = ""
    file_path: Path | None = None

    def render_markdown(self) -> str:
        fm: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "occurrences": str(self.occurrences),
            "severity": self.severity,
            "category": self.category,
            "target_paths": [str(p).replace("\\", "/") for p in self.target_paths],
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "resolved": self.resolved or "",
            "escalation_level": self.escalation_level or "",
        }

        body_lines = [
            "### Problem / Friction Pattern",
            self.problem.strip() if self.problem else "No problem description recorded.",
            "",
            "### Occurrences & Environmental Gaps",
            "| Occurrence | Ticket / Session | Location | Trigger / Environmental Gap |",
            "| :--- | :--- | :--- | :--- |",
        ]

        if self.occurrences_table:
            for row in self.occurrences_table:
                body_lines.append(row.to_markdown())
        else:
            body_lines.append(f"| #1 | - | - | Initial observation |")

        body_lines.extend([
            "",
            "### Systemic Environmental Diagnosis",
            self.systemic_diagnosis.strip() if self.systemic_diagnosis else "Pending environmental investigation.",
            "",
            "### Proposed Structural Remediation",
            self.proposed_remediation.strip() if self.proposed_remediation else "- Pending remediation proposal.",
            "",
        ])

        return frontmatter.serialize(fm, "\n".join(body_lines))


def parse_learning(file_path: Path) -> LearningRecord:
    """Parse a learning markdown file with YAML frontmatter."""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    metadata, body = frontmatter.parse(text)

    # Extract sections from body
    sections: dict[str, str] = {}
    current_sec = ""
    sec_lines: list[str] = []

    CANONICAL_SECTIONS = {
        "problem / friction pattern": "problem",
        "occurrences & environmental gaps": "occurrences",
        "systemic environmental diagnosis": "systemic",
        "proposed structural remediation": "remediation",
    }

    for line in body.splitlines():
        if line.startswith("### "):
            header_name = line[4:].strip().lower()
            matched_canonical = None
            for canon_key, canon_val in CANONICAL_SECTIONS.items():
                if header_name == canon_key or header_name == canon_val:
                    matched_canonical = canon_val
                    break
            if matched_canonical:
                if current_sec:
                    sections[current_sec] = "\n".join(sec_lines).strip()
                current_sec = matched_canonical
                sec_lines = []
            else:
                sec_lines.append(line)
        else:
            sec_lines.append(line)
    if current_sec:
        sections[current_sec] = "\n".join(sec_lines).strip()

    # Parse occurrences table
    table_text = ""
    for k, v in sections.items():
        if "occurrences" in k:
            table_text = v
            break

    occurrences_table: list[OccurrenceRow] = []
    if table_text:
        lines = table_text.splitlines()
        for line in lines:
            line_s = line.strip()
            if not line_s.startswith("|") or ":---" in line_s or "Occurrence" in line_s:
                continue
            # Split on unescaped pipe
            cols = [_unescape_cell(c) for c in re.split(r"(?<!\\)\|", line_s)[1:-1]]
            if len(cols) >= 4:
                idx_str = re.sub(r"[^\d]", "", cols[0])
                idx = int(idx_str) if idx_str else len(occurrences_table) + 1
                occurrences_table.append(
                    OccurrenceRow(
                        index=idx,
                        ticket_session=cols[1] if cols[1] != "-" else "",
                        location=cols[2].strip("`") if cols[2] != "-" else "",
                        trigger=cols[3] if cols[3] != "-" else "",
                    )
                )

    problem = ""
    for k, v in sections.items():
        if "problem" in k:
            problem = v
            break

    systemic = ""
    for k, v in sections.items():
        if "systemic" in k or "diagnosis" in k:
            systemic = v
            break

    remediation = ""
    for k, v in sections.items():
        if "proposed" in k or "remediation" in k:
            remediation = v
            break

    target_paths_raw = metadata.get("target_paths", [])
    if isinstance(target_paths_raw, str):
        target_paths = [target_paths_raw]
    else:
        target_paths = [str(p) for p in target_paths_raw]

    return LearningRecord(
        id=str(metadata.get("id", "")),
        title=str(metadata.get("title", file_path.stem)),
        status=str(metadata.get("status", "pending")),
        occurrences=int(metadata.get("occurrences", len(occurrences_table) or 1)),
        severity=str(metadata.get("severity", "medium")),
        category=str(metadata.get("category", "convention")),
        target_paths=target_paths,
        first_seen=str(metadata.get("first_seen", "")),
        last_seen=str(metadata.get("last_seen", "")),
        resolved=metadata.get("resolved") or None,
        escalation_level=metadata.get("escalation_level") or None,
        problem=problem,
        occurrences_table=occurrences_table,
        systemic_diagnosis=systemic,
        proposed_remediation=remediation,
        file_path=file_path,
    )


def recurring(project_root: Path) -> list[LearningRecord]:
    """Active learnings that came back (twice or more) or are critical: they need a structural fix."""
    return [
        record
        for record in list_learnings(project_root, include_archive=False)
        if record.occurrences >= 2 or record.severity == "critical"
    ]


def list_learnings(project_root: Path, include_archive: bool = False) -> list[LearningRecord]:
    """List all learning records in the project's ./learnings/ directory."""
    root = Path(project_root).resolve()
    learnings_dir = root / LEARNINGS_DIR_NAME
    if not learnings_dir.is_dir():
        return []

    records: list[LearningRecord] = []
    for f in sorted(learnings_dir.glob("*.md")):
        if f.is_file():
            try:
                rec = parse_learning(f)
                records.append(rec)
            except Exception as ex:
                sys.stderr.write(f"warning: failed to parse learning '{f}': {ex}\n")

    if include_archive:
        arch_dir = learnings_dir / ARCHIVE_DIR_NAME
        if arch_dir.is_dir():
            for f in sorted(arch_dir.glob("*.md")):
                if f.is_file():
                    try:
                        rec = parse_learning(f)
                        records.append(rec)
                    except Exception:
                        pass

    return records


def _slugify(text: str, max_len: int | None = 60) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    slug = cleaned.strip("-")
    if not slug:
        return "learning"
    return slug[:max_len].rstrip("-") if max_len else slug


def _slug_matches(slug_a: str, slug_b: str) -> bool:
    """Check if two slugs match cleanly on exact equality or hyphen prefix boundaries."""
    if not slug_a or not slug_b:
        return False
    if slug_a == slug_b:
        return True
    return slug_a.startswith(slug_b + "-") or slug_b.startswith(slug_a + "-")




def _next_learning_id(learnings_dir: Path) -> str:
    highest = 0
    dirs_to_check = [learnings_dir, learnings_dir / ARCHIVE_DIR_NAME]
    for d in dirs_to_check:
        if d.is_dir():
            for f in d.glob("LRN-*.md"):
                match = re.match(r"^LRN-(\d+)", f.stem)
                if match:
                    val = int(match.group(1))
                    if val > highest:
                        highest = val
    return f"LRN-{highest + 1:04d}"


def find_matching_learning(
    records: list[LearningRecord],
    *,
    title: str,
    target_paths: list[str] | None = None,
    category: str = "",
) -> LearningRecord | None:
    """Find an existing learning record that matches the pattern for clustering."""
    norm_title = _slugify(title, max_len=None)
    norm_paths = set(str(p).replace("\\", "/").lower() for p in (target_paths or []))

    STOPWORDS = {
        "the", "and", "for", "with", "from", "when", "that", "this",
        "file", "error", "fail", "failed", "bug", "issue", "crash",
        "test", "code", "run", "add", "use", "using", "into", "over"
    }

    for rec in records:
        if rec.status != "pending":
            continue
        # Check boundary-aware slug matching without 60-character truncation collisions
        rec_slug = _slugify(rec.title, max_len=None)
        if _slug_matches(norm_title, rec_slug):
            return rec

        # Check overlapping target paths and same category with stopword filtering and similarity threshold
        if category and rec.category == category:
            rec_paths = set(str(p).replace("\\", "/").lower() for p in rec.target_paths)
            if norm_paths and rec_paths and (norm_paths & rec_paths):
                title_words = set(w for w in re.findall(r"\w+", title.lower()) if len(w) >= 3 and w not in STOPWORDS)
                rec_words = set(w for w in re.findall(r"\w+", rec.title.lower()) if len(w) >= 3 and w not in STOPWORDS)
                if title_words and rec_words:
                    overlap = title_words & rec_words
                    union = title_words | rec_words
                    jaccard = len(overlap) / len(union) if union else 0.0
                    if len(overlap) >= 2 or jaccard >= 0.4:
                        return rec

    return None


def capture_learning(
    project_root: Path,
    *,
    title: str,
    problem: str,
    ticket_id: str = "",
    location: str = "",
    trigger: str = "",
    category: str = "convention",
    severity: str = "medium",
    target_paths: list[str] | None = None,
    systemic_diagnosis: str = "",
    proposed_remediation: str = "",
    today: str | None = None,
) -> tuple[LearningRecord, bool]:
    """Capture a learning into ./learnings/, clustering into an existing record if found.

    Returns
    -------
    tuple[LearningRecord, bool]
        The captured/updated record, and a boolean is_new (True if new file created,
        False if an existing record was augmented).
    """
    root = Path(project_root).resolve()
    learnings_dir = root / LEARNINGS_DIR_NAME
    learnings_dir.mkdir(parents=True, exist_ok=True)
    (learnings_dir / ARCHIVE_DIR_NAME).mkdir(parents=True, exist_ok=True)

    today_str = today or datetime.date.today().isoformat()
    existing_records = list_learnings(root, include_archive=False)
    paths_in = [p.replace("\\", "/") for p in (target_paths or [])]

    matched = find_matching_learning(existing_records, title=title, target_paths=paths_in, category=category)

    if matched is not None and matched.file_path is not None:
        # Augment existing record
        matched.occurrences += 1
        matched.last_seen = today_str

        # Escalate severity if new occurrence is higher rank
        if SEVERITY_RANKS.get(severity, 2) > SEVERITY_RANKS.get(matched.severity, 2):
            matched.severity = severity

        # Merge target paths
        current_paths = set(matched.target_paths)
        for p in paths_in:
            if p not in current_paths:
                matched.target_paths.append(p)

        # Append occurrence row
        next_idx = len(matched.occurrences_table) + 1
        matched.occurrences_table.append(
            OccurrenceRow(
                index=next_idx,
                ticket_session=ticket_id,
                location=location,
                trigger=trigger or problem[:80],
            )
        )

        # Augment systemic diagnosis if new insights provided
        if systemic_diagnosis and systemic_diagnosis not in matched.systemic_diagnosis:
            matched.systemic_diagnosis += f"\n- Additional diagnosis ({today_str}): {systemic_diagnosis}"

        content = matched.render_markdown()
        core.write_text_atomic(matched.file_path, content)
        return matched, False

    # Mint new record
    new_id = _next_learning_id(learnings_dir)
    slug = _slugify(title) or "learning"
    target_file = learnings_dir / f"{new_id}-{slug}.md"

    initial_row = OccurrenceRow(
        index=1,
        ticket_session=ticket_id,
        location=location,
        trigger=trigger or "Initial occurrence",
    )

    rec = LearningRecord(
        id=new_id,
        title=title,
        status="pending",
        occurrences=1,
        severity=severity,
        category=category,
        target_paths=paths_in,
        first_seen=today_str,
        last_seen=today_str,
        resolved=None,
        escalation_level=None,
        problem=problem,
        occurrences_table=[initial_row],
        systemic_diagnosis=systemic_diagnosis or "Under investigation.",
        proposed_remediation=proposed_remediation or "- Propose Level 1-4 remediation.",
        file_path=target_file,
    )

    content = rec.render_markdown()
    core.write_text_atomic(target_file, content)
    return rec, True


def _artifact_problem(root: Path, artifact: str) -> str | None:
    """None when ``artifact`` names something real, else why not."""
    if not artifact:
        return "--artifact is required: the lint rule, path, commit or ticket that now guards this"
    if re.fullmatch(r"BL\d{2}", artifact):
        from kahnban import linter

        return None if artifact in linter.RULES else f"lint rule {artifact} does not exist"
    if (root / artifact).exists():
        return None
    if re.fullmatch(r"[0-9a-fA-F]{7,40}", artifact) and gitops.is_repo(root):
        if gitops.commit_exists(root, artifact):
            return None
    try:
        core.find_ticket(core.load_config(root), artifact)
        return None
    except core.KahnbanError:
        pass
    return (
        f"artifact '{artifact}' does not exist: name a lint rule (BL19), a path in the "
        "repo, a commit, or a ticket id"
    )


def promote_learning(
    project_root: Path,
    learning_id: str,
    *,
    level: str,
    artifact: str,
    resolution_notes: str = "",
    today: str | None = None,
) -> LearningRecord:
    """Promote an actionable learning to resolved/promoted status and move to archive.

    ``artifact`` is the defence that now exists: a lint rule id, a path in the repo,
    a commit, or the ticket that will build it. A promotion without one is a note,
    and notes are what the ladder exists to replace.
    """
    root = Path(project_root).resolve()
    problem = _artifact_problem(root, artifact.strip())
    if problem:
        raise ValueError(problem)
    records = list_learnings(root, include_archive=False)
    target: LearningRecord | None = None
    for r in records:
        if r.id == learning_id or r.title.lower() == learning_id.lower():
            target = r
            break

    if target is None or target.file_path is None:
        raise ValueError(f"Learning record '{learning_id}' not found in active ./learnings/")

    today_str = today or datetime.date.today().isoformat()
    target.status = "promoted"
    target.resolved = today_str
    target.escalation_level = level
    target.proposed_remediation += (
        f"\n\n**Resolution ({today_str}, {level}):** {resolution_notes or 'promoted'} "
        f"(artifact: `{artifact.strip()}`)"
    )

    # Render updated markdown
    content = target.render_markdown()

    # Move to archive directory atomically
    archive_dir = root / LEARNINGS_DIR_NAME / ARCHIVE_DIR_NAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest_path = archive_dir / target.file_path.name

    # Write content to current location, then atomically replace to archive
    core.write_text_atomic(target.file_path, content)
    target.file_path.replace(dest_path)
    target.file_path = dest_path

    return target
