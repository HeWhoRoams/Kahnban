"""What a worker must have done before it may stop.

Each check answers one question about the board and the ticket's worktree: why this worker
cannot stop yet, or ``None``. ``guard --stop`` asks it when an agent tries to end its turn,
and the runner still checks the board itself after the worker exits.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from kahnban import attempts, core, frontmatter, gitops, learnings, roles
from kahnban.fsutil import exclusive, write_text_atomic


@dataclass(frozen=True)
class ExitContext:
    """What a check may look at: the board, the worker's environment and its ticket (none for the curator)."""

    config: core.Config
    env: Mapping[str, str]
    ticket: core.Ticket | None = None
    fields: Mapping[str, object] = field(default_factory=dict)
    body: str = ""


Check = Callable[[ExitContext], "str | None"]


def needs_ticket(check: Callable[[ExitContext, core.Ticket], str | None]) -> Check:
    """Turn a check on one ticket into a check that has nothing to say when the worker has none."""

    @functools.wraps(check)
    def guarded(ctx: ExitContext) -> str | None:
        return None if ctx.ticket is None else check(ctx, ctx.ticket)

    return guarded


def problem(role: str, env: Mapping[str, str]) -> str | None:
    """Why a worker in ``role`` may not stop yet, or None. Escalating is always a way out."""
    if role not in roles.workers():
        return None
    name = roles.role(role).get("exit", "")
    check = CHECKS.get(name)
    if check is None:
        raise core.KahnbanError(f"role '{role}' names exit check '{name}', which does not exist")
    config = core.load_config(core.project_root_from_env(env))
    wanted = env.get(core.ENV_TICKET, "")
    if not wanted:  # a board-wide role such as the curator
        return check(ExitContext(config, env))
    ticket = core.find_ticket(config, wanted)
    fields, body = frontmatter.parse(ticket.text)
    if str(fields.get("blocked_on") or "").strip():
        return None
    return check(ExitContext(config, env, ticket, fields, body))


def _nudges(config: core.Config, role: str, ticket: str) -> Path:
    return attempts.artifact_dir(config) / f"stop-nudges-{role}-{ticket or 'board'}.count"


def spend_nudge(role: str, env: Mapping[str, str]) -> bool:
    """Use one of the worker's ``max_stop_nudges``; False once they are spent (the runner then decides)."""
    config = core.load_config(core.project_root_from_env(env))
    path = _nudges(config, role, env.get(core.ENV_TICKET, ""))
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


@needs_ticket
def committed_work(ctx: ExitContext, ticket: core.Ticket) -> str | None:
    """A coder leaves every change committed, inside the blast radius, with a commit on its branch."""
    tree = Path(ctx.env.get(core.ENV_WORKTREE, "")).resolve()
    branch = core.ticket_branch(ctx.fields, ticket.ticket_id)
    try:
        core.require_clean_tip(ctx.config, tree, branch)
    except core.GateError as error:
        return str(error)
    offenders, _ = core.diff_scope_problems(ctx.config, ticket, ctx.fields, core.parse_blast_radius(ctx.body))
    if offenders:
        return f"{branch} changes files outside the blast radius: {', '.join(offenders)}"
    default = gitops.default_branch(ctx.config.project_root)
    ahead = gitops.run(tree, ["rev-list", "--count", f"{default}..HEAD"]).stdout.strip()
    if ahead == "0":
        return f"{branch} has no commits yet: finish the work and commit it, or escalate"
    return None


@needs_ticket
def decision_recorded(ctx: ExitContext, ticket: core.Ticket) -> str | None:
    """A reviewer approves or rejects before stopping."""
    undecided = ticket.column == ctx.config.verifying_column and not str(ctx.fields.get("reviewer") or "").strip()
    if undecided:
        return f"{ticket.ticket_id} is neither approved nor rejected. {roles.finish(roles.QA_REVIEWER, ticket.ticket_id)}"
    return None


@needs_ticket
def ready_gate_passes(ctx: ExitContext, ticket: core.Ticket) -> str | None:
    """A spec analyst leaves the ticket in a state the ready gate accepts."""
    if ticket.column not in (ctx.config.backlog_column, ctx.config.refining_column):
        return None
    problems = core.ready_problems(ctx.config, ticket)
    if problems:
        return f"'kahnban ready {ticket.ticket_id}' would refuse it:\n" + "\n".join(
            f"  - {item}" for item in problems
        )
    return None


def learnings_processed(ctx: ExitContext) -> str | None:
    """The curator stops once no recurring learning is left without a fix ticket."""
    left = learnings.recurring(ctx.config.project_root)
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
