"""``kahnban init``: scaffold the board's storage contract and commit it."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from kahnban import __version__, gitops
from kahnban.config import (
    CONFIG_RELATIVE,
    DEFAULT_COLUMNS,
    DEFAULT_REQUIRED_HEADINGS,
    ConfigError,
    load_config,
)
from kahnban.core import HANDOFF_IN_WORKTREE, TEMPLATE_NAME, relative_path, sync
from kahnban.fsutil import write_text_atomic


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
        rel_paths = [relative_path(config, path) for path in written]
        gitops.add(root, rel_paths)
        gitops.commit(root, f"kanban: initialize board ({prefix.upper()})", paths=rel_paths)
    return written
