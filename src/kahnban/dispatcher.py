"""Situational workflow dispatcher for Kahnban.

Evaluates board reality (columns, active worktrees, in-flight tickets, review status)
and resolves the exact deterministic next step, target ticket, specialized agent persona,
and complete execution prompt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter, handoff, roles


@dataclass
class DispatchRecommendation:
    action: str  # merge_and_close, review_and_gate, resume_worktree, claim_and_implement, spec_and_refine, harvest_learnings, idle
    assigned_role: str  # integrator, qa_reviewer, coder, spec_analyst, curator, none
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


def _is_open(ticket: core.Ticket) -> bool:
    """Not parked for a human (blocked_on) and parseable (lint reports the rest)."""
    try:
        fields, _ = frontmatter.parse(ticket.text)
    except frontmatter.FrontmatterError:
        return False
    return not str(fields.get("blocked_on") or "").strip()


def resolve_next_action(
    config: core.Config,
    *,
    preferred_role: str | None = None,
    skip_harvest: bool = False,
) -> DispatchRecommendation:
    """Analyze current board state and return the prioritized next operational handoff.

    ``skip_harvest`` lets the factory loop move on once its curator has had a turn.
    """
    root = config.project_root
    open_tickets = [t for t in core.iter_tickets(config) if _is_open(t)]

    # Priority 1: 4-verifying. Unapproved tickets go to a reviewer; approved ones
    # go to the integrator, who lands them through the merge queue.
    verifying_tickets = [t for t in open_tickets if t.column == config.verifying_column]
    for target in verifying_tickets:
        fields, body = frontmatter.parse(target.text)
        approved = bool(str(fields.get("reviewer") or "").strip())
        if approved and preferred_role not in (None, "integrator"):
            continue
        if not approved and preferred_role not in (None, "qa_reviewer", "reviewer"):
            continue
        role = "integrator" if approved else "qa_reviewer"
        baton = handoff.build_handoff_baton(
            config,
            target.ticket_id,
            stage="closure" if approved else "verification",
            assigned_role=role,
        )
        return DispatchRecommendation(
            action="merge_and_close" if approved else "review_and_gate",
            assigned_role=role,
            ticket_id=target.ticket_id,
            ticket_title=str(fields.get('title') or target.ticket_id),
            column=target.column,
            worktree=str(fields.get("worktree") or ""),
            summary=(
                f"Ticket {target.ticket_id} is approved; merge it through the queue and close it."
                if approved
                else f"Ticket {target.ticket_id} passed verification; review it, then approve or reject."
            ),
            command=baton.next_action.get("command", ""),
            prompt=baton.next_action.get("prompt", ""),
            baton=baton.to_dict(),
        )

    # Priority 2: 3-in-progress tickets nobody holds a live lease on: their worker
    # finished, crashed or was rejected, so another coder can pick them up.
    in_progress_tickets = [
        t for t in open_tickets
        if t.column == config.in_progress_column and not core.live_lease(config, t.ticket_id)
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
            command=f"kahnban lease {target.ticket_id} --owner coder-agent",
            prompt=baton.next_action.get("prompt", ""),
            baton=baton.to_dict(),
        )

    # Priority 3: a mistake that recurred (or is critical) is fixed structurally
    # before new work starts and runs into it again. One-off learnings wait.
    # list_learnings already tolerates a missing directory and reports unreadable files.
    from kahnban import learnings

    recurring = learnings.recurring(root)
    if recurring and not skip_harvest and preferred_role in (None, "curator"):
        count = len(recurring)
        return DispatchRecommendation(
            action="harvest_learnings",
            assigned_role="curator",
            summary=f"{count} recurring learning pattern(s) in ./learnings/ need a structural fix.",
            command="kahnban learnings list && /harvest-learnings",
            prompt=roles.prompt(
                "curator",
                facts=[
                    "Recurring patterns: "
                    + ", ".join(f"{r.id} ({r.occurrences}x, {r.severity})" for r in recurring)
                ],
            ),
        )

    # Priority 4: Check 2-ready (Claim & Implement)
    ready_tickets = [t for t in open_tickets if t.column == config.ready_column]
    # Only tickets whose blast radius is free: an overlapping claim would be refused.
    active_radii = core.in_progress_radii(config)
    active_paths = [p for paths in active_radii.values() for p in paths]
    available = [
        t for t in ready_tickets
        if not core.radius_overlaps(
            core.parse_blast_radius(frontmatter.parse(t.text)[1]),
            active_paths
        )
    ]
    if available and (preferred_role in (None, "coder", "claim")):
        target = available[0]
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

    # Priority 5: Check 1-refining or 0-backlog (Spec & Refine)
    refining_tickets = [t for t in open_tickets if t.column == config.refining_column]
    backlog_tickets = [t for t in open_tickets if t.column == config.backlog_column]
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
            prompt=roles.prompt(
                "spec_analyst",
                ticket=target.ticket_id,
                title=t_title,
                facts=[f"Ticket file: {core._relative(config, target.path)}"],
            ),
        )

    # Default: Idle / Board Clean
    return DispatchRecommendation(
        action="idle",
        assigned_role="none",
        summary="Board is idle. No pending tasks, review gates, or in-flight tickets.",
        command="kahnban status",
        prompt="The board is currently idle. You may capture new ideas via 'kahnban capture' or run 'kahnban lint'.",
    )
