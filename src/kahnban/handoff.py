"""Standardized Relay Baton (HANDOFF.json) for autonomous cross-stage agent handoffs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter

HANDOFFS_DIR_NAME = ".agents/handoffs"
WORKTREE_HANDOFF_REL = core.HANDOFF_IN_WORKTREE


@dataclass
class QAContract:
    feature_test_command: str = ""
    regression_test_command: str = ""
    test_evidence_required: list[str] = field(default_factory=list)
    blast_radius_files: list[str] = field(default_factory=list)


@dataclass
class VerificationResults:
    feature_tests_passed: bool = False
    regression_tests_passed: bool = False
    feature_log: str | None = None
    regression_log: str | None = None
    rejection_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class HandoffBaton:
    version: str = "2.0"
    ticket_id: str = ""
    title: str = ""
    stage: str = "implementation"  # refinement, implementation, verification, closure
    assigned_role: str = "coder"  # spec_analyst, coder, qa_reviewer, integrator, curator
    harness: str = "auto"
    paths: dict[str, str] = field(default_factory=dict)
    qa_contract: QAContract = field(default_factory=QAContract)
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_results: VerificationResults = field(default_factory=VerificationResults)
    context: dict[str, Any] = field(default_factory=dict)
    next_action: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_handoff_path(project_root: Path, ticket_id: str) -> Path:
    return Path(project_root).resolve() / HANDOFFS_DIR_NAME / f"{ticket_id}.json"


def build_handoff_baton(
    config: core.Config,
    ticket_id: str,
    *,
    stage: str = "implementation",
    assigned_role: str = "coder",
    harness: str = "auto",
) -> HandoffBaton:
    """Build a structured relay baton from ticket markdown and board state."""
    ticket = core.find_ticket(config, ticket_id)
    fields, body = frontmatter.parse(ticket.text)

    # Extract acceptance criteria items
    criteria: list[str] = []
    raw_criteria = core.section(body, "Acceptance criteria")
    for line in raw_criteria.splitlines():
        match = core.CHECKBOX_PATTERN.match(line)
        if match:
            text = line[match.end():].strip()
            if text:
                criteria.append(text)

    # Extract blast radius
    blast_radius = core.parse_blast_radius(body)

    # Extract dual test commands
    try:
        feat_cmd, reg_cmd = core.parse_validation_commands(config, body)
    except core.GateError:
        feat_cmd = config.validation_command.strip()
        reg_cmd = config.regression_command.strip() or feat_cmd

    # Determine worktree path
    worktree_field = str(fields.get("worktree") or "").strip()
    worktree_path = (
        (config.project_root / worktree_field).resolve().as_posix()
        if worktree_field
        else ""
    )

    paths = {
        "project_root": config.project_root.resolve().as_posix(),
        "worktree_root": worktree_path,
        "ticket_file": ticket.path.resolve().as_posix(),
    }

    qa = QAContract(
        feature_test_command=feat_cmd,
        regression_test_command=reg_cmd,
        test_evidence_required=criteria,
        blast_radius_files=blast_radius,
    )

    # Generate role-tailored prompt and next command
    prompt = ""
    cmd = ""
    title = str(fields.get("title") or ticket.ticket_id)
    if assigned_role == "coder":
        cmd = f"kahnban claim {ticket_id} --worktree --owner coder-agent"
        prompt = (
            f"You are a specialized Coder Agent working on {ticket_id}: '{title}'. "
            f"Operate inside isolated worktree '{worktree_field or f'.worktrees/{ticket_id}'}'. "
            f"Follow TDD (Red -> Green -> Refactor). "
            f"Touch ONLY files in blast radius: {', '.join(blast_radius) or 'none declared'}. "
            f"Run feature tests: `{feat_cmd}`. "
            f"Ensure global regression tests pass: `{reg_cmd}`. "
            f"Commit everything, then run 'kahnban verify {ticket_id}'."
        )
    elif assigned_role == "qa_reviewer":
        cmd = f"kahnban approve {ticket_id} --reviewer qa-reviewer"
        prompt = (
            f"You are a QA Reviewer Agent auditing {ticket_id}: '{title}'. "
            f"Inspect the diff of branch 'ticket/{ticket_id}' against the default branch. "
            f"Verify all acceptance criteria are proven by high-fidelity tests. "
            f"Run `/unslop` and `/no-comments`. "
            f"If defects exist, run 'kahnban reject {ticket_id} --reviewer qa-reviewer -m \"<what to fix>\"'. "
            f"If it is sound, run '{cmd}'. Never merge or mark it done yourself."
        )
    elif assigned_role == "integrator":
        cmd = f"kahnban merge {ticket_id} && kahnban done {ticket_id}"
        prompt = (
            f"You are the Integrator for {ticket_id}: '{title}', which a reviewer approved. "
            f"Run 'kahnban merge {ticket_id}' from the project root: it merges onto the "
            f"current default branch, runs the tests on the result, and lands it only if "
            f"they pass. Then run 'kahnban done {ticket_id}'. If the merge is refused, run "
            f"'kahnban reject {ticket_id} --reviewer integrator -m \"<the failure>\"'."
        )
    elif assigned_role == "curator":
        cmd = f"kahnban done {ticket_id}"
        prompt = (
            f"You are a Continuous Learning Curator. Ticket {ticket_id} has been merged. "
            f"Run `/reflect` to mine session friction, cluster recurring patterns into ./learnings/, "
            f"and clean up the worktree via 'kahnban cleanup {ticket_id}'."
        )

    # Check existing baton for historical rejection records
    existing = read_handoff_baton(config.project_root, ticket_id)
    verification_results = (
        existing.verification_results if existing else VerificationResults()
    )

    return HandoffBaton(
        version="2.0",
        ticket_id=ticket_id,
        title=str(fields.get('title') or ticket.ticket_id),
        stage=stage,
        assigned_role=assigned_role,
        harness=harness,
        paths=paths,
        qa_contract=qa,
        acceptance_criteria=criteria,
        verification_results=verification_results,
        context={
            "column": ticket.column,
            "problem": core.section(body, "Problem") or str(fields.get("title") or ticket.ticket_id),
            "design_docs": [str(d) for d in fields.get("design_docs", [])]
            if isinstance(fields.get("design_docs"), list)
            else [],
        },
        next_action={"command": cmd, "prompt": prompt},
    )


def write_handoff_baton(
    project_root: Path,
    baton: HandoffBaton,
    *,
    worktree_dir: Path | None = None,
    write_root: bool = True,
) -> Path | None:
    """Atomically persist baton to .agents/handoffs/<ID>.json and worktree if present."""
    root = Path(project_root).resolve()
    target: Path | None = None
    data = baton.to_dict()
    content = json.dumps(data, indent=2, default=str)

    if write_root:
        target = get_handoff_path(root, baton.ticket_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        core.write_text_atomic(target, content)

    # Mirror into worktree if worktree directory exists
    if worktree_dir and Path(worktree_dir).is_dir():
        wt_target = Path(worktree_dir).resolve() / WORKTREE_HANDOFF_REL
        wt_target.parent.mkdir(parents=True, exist_ok=True)
        core.write_text_atomic(wt_target, content)
        if target is None:
            target = wt_target

    return target


def read_handoff_baton(project_root: Path, ticket_id: str) -> HandoffBaton | None:
    """Read existing handoff baton for ticket if present."""
    target = get_handoff_path(project_root, ticket_id)
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        qa_data = data.get("qa_contract", {})
        qa = QAContract(
            feature_test_command=qa_data.get("feature_test_command", ""),
            regression_test_command=qa_data.get("regression_test_command", ""),
            test_evidence_required=qa_data.get("test_evidence_required", []),
            blast_radius_files=qa_data.get("blast_radius_files", []),
        )
        vr_data = data.get("verification_results", {})
        vr = VerificationResults(
            feature_tests_passed=vr_data.get("feature_tests_passed", False),
            regression_tests_passed=vr_data.get("regression_tests_passed", False),
            feature_log=vr_data.get("feature_log"),
            regression_log=vr_data.get("regression_log"),
            rejection_history=vr_data.get("rejection_history", []),
        )
        return HandoffBaton(
            version=data.get("version", "2.0"),
            ticket_id=data.get("ticket_id", ticket_id),
            title=data.get("title", ""),
            stage=data.get("stage", "implementation"),
            assigned_role=data.get("assigned_role", "coder"),
            harness=data.get("harness", "auto"),
            paths=data.get("paths", {}),
            qa_contract=qa,
            acceptance_criteria=data.get("acceptance_criteria", []),
            verification_results=vr,
            context=data.get("context", {}),
            next_action=data.get("next_action", {}),
        )
    except Exception:
        return None


def record_rejection_feedback(
    project_root: Path,
    ticket_id: str,
    feedback: str,
    *,
    author: str = "qa_reviewer",
) -> HandoffBaton | None:
    """Record QA or Code Review rejection feedback into baton for the coder agent."""
    baton = read_handoff_baton(project_root, ticket_id)
    if not baton:
        return None
    entry = {
        "author": author,
        "feedback": feedback,
    }
    baton.verification_results.rejection_history.append(entry)
    baton.stage = "implementation"
    baton.assigned_role = "coder"

    # Update prompt to explicitly address rejection feedback
    baton.next_action["prompt"] = (
        f"QA / Review REJECTED ticket {ticket_id}. "
        f"Rejection Feedback: {feedback}. "
        f"Address the feedback inside your worktree, re-run feature tests, and verify."
    )
    wt_path = Path(baton.paths.get("worktree_root", "")) if baton.paths.get("worktree_root") else None
    write_handoff_baton(project_root, baton, worktree_dir=wt_path)
    return baton
