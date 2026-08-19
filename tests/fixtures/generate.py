"""Author the lint fixture boards under ``tests/fixtures``.

The fixtures are committed static files; this script is the tool that wrote them
and the way to regenerate them after a rule change:

    py -3 tests/fixtures/generate.py

Layout (plan §8):
    clean-board/            lints with zero violations (LF)
    clean-board-crlf/       identical content, CRLF endings
    violations/BL01 … BL16  one minimal board per rule
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
COLUMNS = [
    "0-backlog",
    "1-refining",
    "2-ready",
    "3-in-progress",
    "4-verifying",
    "5-done",
]
BASE_CONFIG = {
    "engine_min_version": "0.1.0",
    "id_prefix": "TST",
    "board_root": "plans/tickets",
    "columns": COLUMNS,
    "done_column": "5-done",
    "wip_limit": 3,
    "use_worktrees": True,
    "shared_caches": [],
    "validation_timeout_sec": 60,
    "log_output_max_bytes": 65536,
    "required_headings": [
        "Problem",
        "Acceptance criteria",
        "Blast radius",
        "Implementation notes",
        "Validation",
        "Log",
    ],
    "validation_command": "git --version",
    "design_doc_roots": ["plans"],
    "extensions": {},
}


def ticket(
    ticket_id: str,
    *,
    column: str,
    title: str = "Example ticket",
    status: str | None = None,
    owner: str = "unassigned",
    branch: str = "",
    depends_on: tuple[str, ...] = (),
    design_docs: tuple[str, ...] = (),
    blocked_on: str = "",
    blast_radius: tuple[str, ...] = ("src/example.py",),
    acceptance: tuple[str, ...] = ("- [ ] behaves as described",),
    headings: tuple[str, ...] = (
        "Problem",
        "Acceptance criteria",
        "Blast radius",
        "Implementation notes",
        "Validation",
        "Log",
    ),
    extra_frontmatter: tuple[str, ...] = (),
    log: tuple[str, ...] = ("- 2026-08-18 10:00 - created -> 0-backlog",),
) -> str:
    head, separator, tail = column.partition("-")
    derived = tail if separator and head.isdigit() else column
    lines = [
        "---",
        f"id: {ticket_id}",
        f"title: {title}",
        f"status: {status if status is not None else derived}",
        f"owner: {owner}",
        f'branch: "{branch}"',
        'worktree: ""',
        "created: 2026-08-18",
        "updated: 2026-08-18",
        'legacy_id: ""',
        "design_docs: [" + ", ".join(design_docs) + "]",
        "depends_on: [" + ", ".join(depends_on) + "]",
        f'blocked_on: "{blocked_on}"',
        "junctions: []",
        *extra_frontmatter,
        "---",
        "",
    ]
    sections: dict[str, list[str]] = {
        "Problem": ["The documented behavior gap."],
        "Acceptance criteria": list(acceptance),
        "Blast radius": [f"- `{item}`" for item in blast_radius] or ["- `src/none.py`"],
        "Implementation notes": ["- Reuse the existing helper."],
        "Validation": ["```", "git --version", "```"],
        "Log": list(log),
    }
    for heading in headings:
        lines.append(f"## {heading}")
        lines.extend(sections[heading])
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def board(
    name: str,
    tickets: dict[str, tuple[str, str]],
    *,
    config_overrides: dict | None = None,
    extra_files: dict[str, str] | None = None,
    extra_dirs: tuple[str, ...] = (),
    crlf: bool = False,
) -> Path:
    """Materialize one fixture board. ``tickets`` maps 'column/name.md' -> text."""
    root = FIXTURES / name
    if root.exists():
        shutil.rmtree(root)
    config = dict(BASE_CONFIG)
    config.update(config_overrides or {})

    def write(relative: str, text: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = text.replace("\n", "\r\n") if crlf else text
        path.write_text(payload, encoding="utf-8", newline="")

    write("plans/board.config.json", json.dumps(config, indent=2) + "\n")
    for column in [*config["columns"], "archive"]:
        write(f"plans/tickets/{column}/.gitkeep", "")
    for relative, text in tickets.items():
        write(f"plans/tickets/{relative}", text)
    for relative, text in (extra_files or {}).items():
        write(relative, text)
    for relative in extra_dirs:
        (root / relative).mkdir(parents=True, exist_ok=True)
        write(f"{relative}/.gitkeep", "")
    return root


def clean_tickets() -> dict[str, tuple[str, str]]:
    return {
        "0-backlog/TST-001-capture-idea.md": ticket(
            "TST-001", column="0-backlog", title="Capture the idea"
        ),
        "1-refining/TST-002-research-shape.md": ticket(
            "TST-002", column="1-refining", title="Research the shape"
        ),
        "2-ready/TST-003-ready-for-pickup.md": ticket(
            "TST-003",
            column="2-ready",
            title="Ready for cold pickup",
            depends_on=("TST-006",),
            design_docs=("plans/DESIGN.md",),
            blast_radius=("src/ready.py",),
        ),
        "3-in-progress/TST-004-claimed-work.md": ticket(
            "TST-004",
            column="3-in-progress",
            title="Claimed work",
            owner="agent-a",
            branch="ticket/TST-004",
            blast_radius=("src/claimed.py",),
        ),
        "4-verifying/TST-005-awaiting-review.md": ticket(
            "TST-005",
            column="4-verifying",
            title="Awaiting review",
            owner="agent-b",
            branch="ticket/TST-005",
            blast_radius=("src/verifying.py",),
            acceptance=("- [x] behaves as described",),
        ),
        "5-done/TST-006-merged-work.md": ticket(
            "TST-006",
            column="5-done",
            title="Merged work",
            owner="agent-a",
            branch="ticket/TST-006",
            blast_radius=("src/done.py",),
            acceptance=("- [x] behaves as described",),
            log=(
                "- 2026-08-18 10:00 - created -> 0-backlog",
                "- 2026-08-18 12:00 - done gate passed -> 5-done",
            ),
        ),
        "archive/TST-000-superseded.md": ticket(
            "TST-000", column="archive", title="Superseded idea", status="archive"
        ),
    }


def build_all() -> list[Path]:
    written: list[Path] = []
    design_doc = {"plans/DESIGN.md": "# Design\n"}

    written.append(
        board("clean-board", clean_tickets(), extra_files=design_doc)
    )
    written.append(
        board("clean-board-crlf", clean_tickets(), extra_files=design_doc, crlf=True)
    )

    # BL01 — unparseable frontmatter (nested mapping).
    written.append(
        board(
            "violations/BL01",
            {
                "0-backlog/TST-001-nested-frontmatter.md": ticket(
                    "TST-001",
                    column="0-backlog",
                    extra_frontmatter=("metadata:", "  nested: value"),
                )
            },
        )
    )

    # BL02 — frontmatter id disagrees with the filename.
    written.append(
        board(
            "violations/BL02",
            {
                "0-backlog/TST-007-filename-mismatch.md": ticket(
                    "TST-7", column="0-backlog"
                )
            },
        )
    )

    # BL03 — the same id in two columns.
    written.append(
        board(
            "violations/BL03",
            {
                "0-backlog/TST-003-first-home.md": ticket("TST-003", column="0-backlog"),
                "1-refining/TST-003-second-home.md": ticket(
                    "TST-003", column="1-refining"
                ),
            },
        )
    )

    # BL04 — status contradicts the folder.
    written.append(
        board(
            "violations/BL04",
            {
                "0-backlog/TST-001-status-drift.md": ticket(
                    "TST-001", column="0-backlog", status="ready"
                )
            },
        )
    )

    # BL05 — a required heading is missing.
    written.append(
        board(
            "violations/BL05",
            {
                "0-backlog/TST-001-missing-heading.md": ticket(
                    "TST-001",
                    column="0-backlog",
                    headings=(
                        "Problem",
                        "Acceptance criteria",
                        "Blast radius",
                        "Validation",
                        "Log",
                    ),
                )
            },
        )
    )

    # BL06 — ready with no acceptance checkbox.
    written.append(
        board(
            "violations/BL06",
            {
                "2-ready/TST-001-no-checkboxes.md": ticket(
                    "TST-001",
                    column="2-ready",
                    acceptance=("- prose instead of a checkbox",),
                )
            },
        )
    )

    # BL07 — done with an unchecked box.
    written.append(
        board(
            "violations/BL07",
            {
                "5-done/TST-001-unchecked-done.md": ticket(
                    "TST-001",
                    column="5-done",
                    owner="agent-a",
                    branch="ticket/TST-001",
                    acceptance=("- [x] first", "- [ ] second"),
                    log=(
                        "- 2026-08-18 10:00 - created -> 0-backlog",
                        "- 2026-08-18 12:00 - merge-commit: 0123456789abcdef",
                    ),
                )
            },
        )
    )

    # BL08 — in progress with nobody owning it.
    written.append(
        board(
            "violations/BL08",
            {
                "3-in-progress/TST-001-unowned.md": ticket(
                    "TST-001",
                    column="3-in-progress",
                    owner="unassigned",
                    branch="ticket/TST-001",
                )
            },
        )
    )

    # BL09 — a missing dependency and an unfinished one.
    written.append(
        board(
            "violations/BL09",
            {
                "0-backlog/TST-001-dependency.md": ticket("TST-001", column="0-backlog"),
                "2-ready/TST-002-depends-badly.md": ticket(
                    "TST-002",
                    column="2-ready",
                    depends_on=("TST-001", "TST-900"),
                    blast_radius=("src/other.py",),
                ),
            },
        )
    )

    # BL10 — extension field required from the ready column is absent.
    written.append(
        board(
            "violations/BL10",
            {
                "2-ready/TST-001-missing-extension.md": ticket(
                    "TST-001", column="2-ready"
                )
            },
            config_overrides={
                "extensions": {
                    "validation_class": {
                        "enum": ["headless-verified", "visual-deferred"],
                        "required_from": "2-ready",
                    }
                }
            },
        )
    )

    # BL11 — design_docs points at a file that does not exist.
    written.append(
        board(
            "violations/BL11",
            {
                "0-backlog/TST-001-missing-doc.md": ticket(
                    "TST-001", column="0-backlog", design_docs=("plans/GONE.md",)
                )
            },
        )
    )

    # BL12 — more in-progress tickets than the WIP limit allows.
    written.append(
        board(
            "violations/BL12",
            {
                "3-in-progress/TST-001-first.md": ticket(
                    "TST-001",
                    column="3-in-progress",
                    owner="agent-a",
                    branch="ticket/TST-001",
                    blast_radius=("src/first.py",),
                ),
                "3-in-progress/TST-002-second.md": ticket(
                    "TST-002",
                    column="3-in-progress",
                    owner="agent-b",
                    branch="ticket/TST-002",
                    blast_radius=("src/second.py",),
                ),
            },
            config_overrides={"wip_limit": 1},
        )
    )

    # BL13 — a stray file and a stray subdirectory inside a column.
    written.append(
        board(
            "violations/BL13",
            {"0-backlog/TST-001-tidy.md": ticket("TST-001", column="0-backlog")},
            extra_files={"plans/tickets/0-backlog/notes.txt": "scratch\n"},
            extra_dirs=("plans/tickets/0-backlog/scratch",),
        )
    )

    # BL14 — in progress without a recorded branch.
    written.append(
        board(
            "violations/BL14",
            {
                "3-in-progress/TST-001-no-branch.md": ticket(
                    "TST-001", column="3-in-progress", owner="agent-a", branch=""
                )
            },
        )
    )

    # BL15 — done while the ticket branch is not merged.  The test materializes
    # this board inside a git repo and creates ticket/TST-001 unmerged.
    written.append(
        board(
            "violations/BL15",
            {
                "5-done/TST-001-unmerged.md": ticket(
                    "TST-001",
                    column="5-done",
                    owner="agent-a",
                    branch="ticket/TST-001",
                    acceptance=("- [x] behaves as described",),
                )
            },
        )
    )

    # BL16 — two in-progress tickets sharing a blast radius.
    written.append(
        board(
            "violations/BL16",
            {
                "3-in-progress/TST-001-owns-ui.md": ticket(
                    "TST-001",
                    column="3-in-progress",
                    owner="agent-a",
                    branch="ticket/TST-001",
                    blast_radius=("src/ui/",),
                ),
                "3-in-progress/TST-002-owns-ui-panel.md": ticket(
                    "TST-002",
                    column="3-in-progress",
                    owner="agent-b",
                    branch="ticket/TST-002",
                    blast_radius=("src/ui/panel.py",),
                ),
            },
        )
    )
    return written


if __name__ == "__main__":
    for path in build_all():
        print(path.relative_to(FIXTURES.parent).as_posix())
