"""What a worker must have done before it may stop.

Each check answers one question about the board and the ticket's worktree: why this worker
cannot stop yet, or ``None``. ``guard --stop`` asks it when an agent tries to end its turn,
and the runner still checks the board itself after the worker exits.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from kahnban import core, frontmatter, gitops

Check = Callable[[core.Config, core.Ticket, dict, str, Mapping[str, str]], "str | None"]


def problem(role: str, env: Mapping[str, str]) -> str | None:
    """Why a worker in ``role`` may not stop yet, or None. Escalating is always a way out."""
    check = CHECKS.get(role)
    if check is None:
        return None
    config = core.load_config(Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve())
    ticket = core.find_ticket(config, env.get("KAHNBAN_TICKET", ""))
    fields, body = frontmatter.parse(ticket.text)
    if str(fields.get("blocked_on") or "").strip():
        return None
    return check(config, ticket, fields, body, env)


def committed_work(
    config: core.Config, ticket: core.Ticket, fields: dict, body: str, env: Mapping[str, str]
) -> str | None:
    """A coder leaves every change committed, inside the blast radius, with a commit on its branch."""
    tree = Path(env.get("KAHNBAN_WORKTREE", "")).resolve()
    branch = core.ticket_branch(fields, ticket.ticket_id)
    try:
        core.require_clean_tip(config, tree, branch)
    except core.GateError as error:
        return str(error)
    offenders, _ = core.diff_scope_problems(config, ticket, fields, core.parse_blast_radius(body))
    if offenders:
        return f"{branch} changes files outside the blast radius: {', '.join(offenders)}"
    default = gitops.default_branch(config.project_root)
    ahead = gitops.run(tree, ["rev-list", "--count", f"{default}..HEAD"]).stdout.strip()
    if ahead == "0":
        return f"{branch} has no commits yet: finish the work and commit it, or escalate"
    return None


def decision_recorded(
    config: core.Config, ticket: core.Ticket, fields: dict, body: str, env: Mapping[str, str]
) -> str | None:
    """A reviewer approves or rejects before stopping."""
    from kahnban import roles

    if ticket.column == config.verifying_column and not str(fields.get("reviewer") or "").strip():
        return f"{ticket.ticket_id} is neither approved nor rejected. {roles.finish('qa_reviewer', ticket.ticket_id)}"
    return None


def ready_gate_passes(
    config: core.Config, ticket: core.Ticket, fields: dict, body: str, env: Mapping[str, str]
) -> str | None:
    """A spec analyst leaves the ticket in a state the ready gate accepts."""
    if ticket.column not in (config.backlog_column, config.refining_column):
        return None
    problems = core.ready_problems(config, ticket)
    if problems:
        return f"'kahnban ready {ticket.ticket_id}' would refuse it:\n" + "\n".join(
            f"  - {item}" for item in problems
        )
    return None


CHECKS: dict[str, Check] = {
    "coder": committed_work,
    "qa_reviewer": decision_recorded,
    "spec_analyst": ready_gate_passes,
}
