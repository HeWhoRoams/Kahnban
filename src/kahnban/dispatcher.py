"""Situational workflow dispatcher for Kahnban.

Evaluates board reality (columns, active worktrees, in-flight tickets, review status)
and resolves the exact deterministic next step, target ticket, specialized agent persona,
and complete execution prompt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter, handoff


@dataclass
class DispatchRecommendation:
    action: str  # review_and_gate, resume_worktree, claim_and_implement, spec_and_refine, harvest_learnings, idle
    assigned_role: str  # qa_reviewer, coder, spec_analyst, curator, none
    ticket_id: str | None = None
    ticket_title: str | None = None
    column: str | None = None
    worktree: str | None = None
    summary: str = ""
    command: str = ""
    prompt: str = ""
    baton: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_next_action(
    config: core.Config,
    *,
    preferred_role: str | None = None,
) -> DispatchRecommendation:
    """Analyze current board state and return the prioritized next operational handoff."""
    root = config.project_root

    # Priority 1: Check 4-verifying (Review / QA Gate)
    # Tickets here have passed machine verification and await QA / Standards Review before merge
    verifying_tickets = [
        t for t in core.iter_tickets(config) if t.column == config.verifying_column
    ]
    if verifying_tickets and (preferred_role in (None, "qa_reviewer", "reviewer")):
        target = verifying_tickets[0]
        baton = handoff.build_handoff_baton(
            config, target.ticket_id, stage="verification", assigned_role="qa_reviewer"
        )
        fields, body = frontmatter.parse(target.text)
        wt = str(fields.get("worktree") or "")
        return DispatchRecommendation(
            action="review_and_gate",
            assigned_role="qa_reviewer",
            ticket_id=target.ticket_id,
            ticket_title=str(fields.get('title') or target.ticket_id),
            column=target.column,
            worktree=wt,
            summary=f"Ticket {target.ticket_id} passed dual verification; ready for QA audit and merge.",
            command=f"git merge --no-ff ticket/{target.ticket_id} && kahnban done {target.ticket_id}",
            prompt=baton.next_action.get("prompt", ""),
            baton=baton.to_dict(),
        )

    # Priority 2: Check 3-in-progress (In-flight implementation or revision)
    in_progress_tickets = [
        t for t in core.iter_tickets(config) if t.column == config.in_progress_column
    ]
    if in_progress_tickets and (preferred_role in (None, "coder", "resume")) and (preferred_role != "claim"):
        target = in_progress_tickets[0]
        fields, body = frontmatter.parse(target.text)
        wt = str(fields.get("worktree") or "")

        # Check if this ticket was previously rejected by QA
        baton = handoff.read_handoff_baton(root, target.ticket_id)
        if not baton:
            baton = handoff.build_handoff_baton(
                config, target.ticket_id, stage="implementation", assigned_role="coder"
            )

        is_revision = bool(baton.verification_results.rejection_history)
        action_name = "revise_implementation" if is_revision else "resume_worktree"
        summary_text = (
            f"Ticket {target.ticket_id} was rejected by QA; address feedback in worktree."
            if is_revision
            else f"Ticket {target.ticket_id} is in-progress; drive TDD in worktree."
        )

        return DispatchRecommendation(
            action=action_name,
            assigned_role="coder",
            ticket_id=target.ticket_id,
            ticket_title=str(fields.get('title') or target.ticket_id),
            column=target.column,
            worktree=wt,
            summary=summary_text,
            command=f"kahnban verify {target.ticket_id}",
            prompt=baton.next_action.get("prompt", ""),
            baton=baton.to_dict(),
        )

    # Priority 3: Check 2-ready (Claim & Implement)
    ready_tickets = [
        t for t in core.iter_tickets(config) if t.column == config.ready_column
    ]
    if ready_tickets and (preferred_role in (None, "coder", "claim")):
        # Select first ticket with non-conflicting blast radius against in-progress
        active_radii = core.in_progress_radii(config)
        active_paths = [p for paths in active_radii.values() for p in paths]
        available = [
            t for t in ready_tickets
            if not core.radius_overlaps(
                core.parse_blast_radius(frontmatter.parse(t.text)[1]),
                active_paths
            )
        ]
        target = available[0] if available else ready_tickets[0]
        fields, body = frontmatter.parse(target.text)
        baton = handoff.build_handoff_baton(
            config, target.ticket_id, stage="implementation", assigned_role="coder"
        )
        return DispatchRecommendation(
            action="claim_and_implement",
            assigned_role="coder",
            ticket_id=target.ticket_id,
            ticket_title=str(fields.get('title') or target.ticket_id),
            column=target.column,
            worktree=f".worktrees/{target.ticket_id}",
            summary=f"Ticket {target.ticket_id} passed ready gate; claim into isolated worktree.",
            command=f"kahnban claim {target.ticket_id} --worktree --owner coder-agent",
            prompt=baton.next_action.get("prompt", ""),
            baton=baton.to_dict(),
        )

    # Priority 4: Check 1-refining or 0-backlog (Spec & Refine)
    refining_tickets = [
        t for t in core.iter_tickets(config) if t.column == config.refining_column
    ]
    backlog_tickets = [
        t for t in core.iter_tickets(config) if t.column == config.backlog_column
    ]
    intake_candidates = refining_tickets or backlog_tickets
    if intake_candidates and (preferred_role in (None, "spec_analyst")):
        target = intake_candidates[0]
        fields, body = frontmatter.parse(target.text)
        t_title = str(fields.get("title") or target.ticket_id)
        return DispatchRecommendation(
            action="spec_and_refine",
            assigned_role="spec_analyst",
            ticket_id=target.ticket_id,
            ticket_title=t_title,
            column=target.column,
            summary=f"Ticket {target.ticket_id} requires refinement and acceptance criteria.",
            command=f"kahnban ready {target.ticket_id}",
            prompt=(
                f"You are a Spec Analyst Agent. Refine {target.ticket_id}: '{t_title}'. "
                f"Define explicit ## Acceptance criteria (checkboxes), ## Blast radius (files), "
                f"and ## Validation commands (### Feature Tests and ### Regression Tests). "
                f"Run 'kahnban ready {target.ticket_id}' once complete."
            ),
        )

    # Priority 5: Check ./learnings/ (Continuous Learning Curator)
    try:
        from kahnban import learnings

        pending_learnings = learnings.list_learnings(root, include_archive=False)
        if pending_learnings and (preferred_role in (None, "curator")):
            count = len(pending_learnings)
            return DispatchRecommendation(
                action="harvest_learnings",
                assigned_role="curator",
                summary=f"{count} pending learning pattern(s) in ./learnings/ ready for structural promotion.",
                command="kahnban learnings list && /harvest-learnings",
                prompt=(
                    f"You are a Continuous Learning Curator. There are {count} active learning pattern(s). "
                    "Review them, promote resolved items to the appropriate escalation ladder tier, "
                    "and encode structural safeguards into codebase rules or tests."
                ),
            )
    except Exception:
        pass

    # Default: Idle / Board Clean
    return DispatchRecommendation(
        action="idle",
        assigned_role="none",
        summary="Board is idle. No pending tasks, review gates, or in-flight tickets.",
        command="kahnban status",
        prompt="The board is currently idle. You may capture new ideas via 'kahnban capture' or run 'kahnban lint'.",
    )
