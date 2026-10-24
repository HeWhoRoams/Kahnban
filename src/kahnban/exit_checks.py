"""What a worker must have done before it may stop.

Each check answers one question about the board and the ticket's worktree: why this worker
cannot stop yet, or ``None``. ``guard --stop`` asks it when an agent tries to end its turn,
and the runner still checks the board itself after the worker exits.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from kahnban import attempts, core, frontmatter, gitops, learnings, roles
from kahnban.fsutil import exclusive, write_text_atomic

Check = Callable[[core.Config, "core.Ticket | None", dict, str, Mapping[str, str]], "str | None"]


def problem(role: str, env: Mapping[str, str]) -> str | None:
    """Why a worker in ``role`` may not stop yet, or None. Escalating is always a way out."""
    check = CHECKS.get(roles.role(role).get("exit", "")) if role in roles.workers() else None
    if check is None:
        return None
    config = core.load_config(Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve())
    wanted = env.get("KAHNBAN_TICKET", "")
    if not wanted:  # a board-wide role such as the curator
        return check(config, None, {}, "", env)
    ticket = core.find_ticket(config, wanted)
    fields, body = frontmatter.parse(ticket.text)
    if str(fields.get("blocked_on") or "").strip():
        return None
    return check(config, ticket, fields, body, env)


def _nudges(config: core.Config, role: str, ticket: str) -> Path:
    return attempts.artifact_dir(config) / f"stop-nudges-{role}-{ticket or 'board'}.count"


def spend_nudge(role: str, env: Mapping[str, str]) -> bool:
    """Use one of the worker's ``max_stop_nudges``; False once they are spent (the runner then decides)."""
    config = core.load_config(Path(env.get("KAHNBAN_PROJECT_ROOT", ".")).resolve())
    path = _nudges(config, role, env.get("KAHNBAN_TICKET", ""))
    with exclusive(path.with_suffix(".lock")):
        try:
            used = int(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            used = 0
        if used >= config.max_stop_nudges:
            return False
        write_text_atomic(path, str(used + 1))
        return True


def reset_nudges(config: core.Config, role: str, ticket: str) -> None:
    """Each worker the runner starts gets its full nudge budget."""
    path = _nudges(config, role, ticket)
    with exclusive(path.with_suffix(".lock")):
        path.unlink(missing_ok=True)


def committed_work(
    config: core.Config, ticket: core.Ticket, fields: dict, body: str, env: Mapping[str, str]
) -> str | None:
    """A coder leaves every change committed, inside the blast radius, with a commit on its branch."""
    if ticket is None:
        return None
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
    if ticket is not None and ticket.column == config.verifying_column and not str(fields.get("reviewer") or "").strip():
        return f"{ticket.ticket_id} is neither approved nor rejected. {roles.finish('qa_reviewer', ticket.ticket_id)}"
    return None


def ready_gate_passes(
    config: core.Config, ticket: core.Ticket, fields: dict, body: str, env: Mapping[str, str]
) -> str | None:
    """A spec analyst leaves the ticket in a state the ready gate accepts."""
    if ticket is None or ticket.column not in (config.backlog_column, config.refining_column):
        return None
    problems = core.ready_problems(config, ticket)
    if problems:
        return f"'kahnban ready {ticket.ticket_id}' would refuse it:\n" + "\n".join(
            f"  - {item}" for item in problems
        )
    return None


def learnings_processed(
    config: core.Config, ticket: core.Ticket | None, fields: dict, body: str, env: Mapping[str, str]
) -> str | None:
    """The curator stops once no recurring learning is left without a fix ticket."""
    left = learnings.recurring(config.project_root)
    if not left:
        return None
    return (
        f"{len(left)} recurring learning(s) still need a structural fix ticket: "
        + ", ".join(record.id for record in left)
        + ". File each with `kahnban new`, archive it, or stop only when none remain."
    )


CHECKS: dict[str, Check] = {
    "learnings_processed": learnings_processed,
    "committed_work": committed_work,
    "decision_recorded": decision_recorded,
    "ready_gate_passes": ready_gate_passes,
}
