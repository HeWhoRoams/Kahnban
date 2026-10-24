"""``kahnban run`` — the factory loop.

The board decides what happens next (:mod:`kahnban.dispatcher`). Workers — any
command configured under ``workers`` in board.config.json, typically a headless
coding agent — only do the judgment work: refine a ticket, implement it, review
it, turn a recurring learning into a fix ticket. Every gate (ready, claim, verify, merge, done) is run by this loop itself, so
a worker can neither skip one nor report success it did not earn.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kahnban import attempts, core, dispatcher, exit_checks, frontmatter, gitops, handoff, trust, worktree

CODER = "coder-agent"
INTEGRATOR = "integrator"
HEARTBEAT_SEC = 60


_NO_WORKER = (
    "no worker command for {role}: set 'workers' in board.config.json, e.g. "
    '{{"default": "claude -p --agent kahnban-{{role}} --permission-mode acceptEdits"}}'
)


class RunStop(core.KahnbanError):
    """The loop cannot continue (for example, no worker is configured)."""


@dataclass
class Step:
    number: int
    action: str
    ticket_id: str | None
    outcome: str


@dataclass
class RunResult:
    steps: list[Step] = field(default_factory=list)
    stopped: str = ""
    log_path: Path | None = None
    parked: list[str] = field(default_factory=list)  # tickets waiting for a human
    guard_refusals: int = 0  # tool calls the role guard blocked during this run


def _parked(config: core.Config) -> list[str]:
    parked: list[str] = []
    for ticket in core.iter_tickets(config):
        if ticket.column == config.done_column:
            continue
        try:
            blocked = str(frontmatter.parse(ticket.text)[0].get("blocked_on") or "").strip()
        except frontmatter.FrontmatterError:
            continue
        if blocked:
            parked.append(f"{ticket.ticket_id} ({blocked})")
    return parked


def run(
    config: core.Config,
    *,
    max_steps: int = 20,
    echo: Callable[[str], None] = print,
) -> RunResult:
    """Drive the board until it is idle, every open ticket is parked, or
    ``max_steps`` is reached. A ticket that comes back to the same action more
    than ``max_attempts`` times is escalated to a human and skipped."""
    if not config.workers:
        raise RunStop(_NO_WORKER.format(role="any role"))
    result = RunResult(log_path=_log_path(config))
    curated = False  # the curator gets one turn per run; then the board moves on
    for number in range(1, max_steps + 1):
        rec = dispatcher.resolve_next_action(config, skip_harvest=curated)
        if rec.action == "harvest_learnings":
            curated = True
            try:
                code, _ = _work(config, "curator", rec, config.project_root, result.log_path)
                outcome = f"curator turn finished (exit {code})"
            except RunStop:
                raise
            except core.KahnbanError as error:
                outcome = f"refused: {error}"
            result.steps.append(Step(number, rec.action, None, outcome))
            echo(f"[{number}] {rec.action}: {outcome}")
            continue
        if rec.action == "idle":
            result.parked = _parked(config)
            result.stopped = (
                f"nothing left the runner can do; {len(result.parked)} ticket(s) "
                "wait for a human"
                if result.parked
                else rec.summary
            )
            _guard_summary(result, echo)
            return result
        ticket = rec.ticket_id or ""
        entry = attempts.bump(config, rec.action, ticket, _progress(config, ticket))
        if entry.count > config.max_attempts:
            reason = (
                f"'{rec.action}' made no progress after {config.max_attempts} attempts; "
                f"last: {entry.last}"
            )
            core.escalate(config, ticket, reason[:300])
            outcome = f"escalated: {reason}"
        else:
            try:
                outcome = _step(config, rec, result.log_path)
            except RunStop:
                raise
            except (core.KahnbanError, gitops.GitError, worktree.WorktreeError) as error:
                outcome = f"refused: {error}"
        # One line, details kept: a refusal's paths are on its continuation lines.
        summary = " ".join(part.strip() for part in outcome.splitlines() if part.strip())
        attempts.note(config, rec.action, ticket, summary.replace('"', "'"))
        result.steps.append(Step(number, rec.action, rec.ticket_id, outcome))
        echo(f"[{number}] {rec.action} {ticket}: {summary[:400]}")
    result.stopped = f"stopped after {max_steps} steps"
    result.parked = _parked(config)
    _guard_summary(result, echo)
    return result


def guard_log_path(log: Path) -> Path:
    return log.with_name(log.name + ".guard")


def _guard_summary(result: RunResult, echo: Callable[[str], None]) -> None:
    path = guard_log_path(result.log_path) if result.log_path else None
    if path and path.is_file():
        result.guard_refusals = len(path.read_text(encoding="utf-8").splitlines())
        echo(f"the guard refused {result.guard_refusals} tool call(s); see {path}")


def _progress(config: core.Config, ticket_id: str) -> str:
    """What moves when a ticket makes progress: its column, branch tip and verified commit."""
    try:
        ticket = core.find_ticket(config, ticket_id)
        fields, _ = frontmatter.parse(ticket.text)
    except (core.KahnbanError, frontmatter.FrontmatterError):
        return ""
    tip = core.branch_tip(config, core.ticket_branch(fields, ticket.ticket_id))
    return f"{ticket.column}|{tip}|{fields.get('verified_sha') or ''}"


def _step(config: core.Config, rec: dispatcher.DispatchRecommendation, log: Path) -> str:
    ticket = rec.ticket_id or ""
    if rec.action == "merge_and_close":
        waiting = _await_human(config, ticket)
        return waiting or _merge_and_close(config, ticket)
    if rec.action == "claim_and_implement":
        core.claim(config, ticket, CODER, create_worktree=True)
        return _implement(config, rec, log)
    if rec.action in ("resume_worktree", "revise_implementation"):
        core.lease(config, ticket, CODER)
        return _implement(config, rec, log)
    if rec.action == "review_and_gate":
        code, _ = _work(config, "qa_reviewer", rec, config.project_root, log)
        reviewed = core.find_ticket(config, ticket)
        fields, _ = frontmatter.parse(reviewed.text)
        if reviewed.column == config.in_progress_column:
            return "rejected by the reviewer"
        if str(fields.get("reviewer") or "").strip():
            if config.require_signed_approvals:
                core.countersign(config, ticket)
            return f"approved by {fields.get('reviewer')}"
        return f"reviewer exited {code} without approving or rejecting"
    if rec.action == "spec_and_refine":
        if config.autonomy == core.Autonomy.ATTENDED and core.HumanGate.READY in config.human_gates:
            if not core.needs_human(config, core.find_ticket(config, ticket)):
                core.ready(config, ticket)
                return "confirmed by a human; passed the ready gate"
        code, _ = _work(config, "spec_analyst", rec, config.project_root, log)
        waiting = _await_human(config, ticket)
        if waiting:
            return waiting
        if core.find_ticket(config, ticket).column not in (
            config.backlog_column,
            config.refining_column,
        ):
            # A spec analyst may run 'kahnban ready' itself; the gate still decided.
            return f"refined (worker exit {code}); the worker ran the ready gate and it passed"
        core.ready(config, ticket)
        return f"refined (worker exit {code}) and passed the ready gate"
    raise RunStop(f"runner has no handler for action '{rec.action}'")


def _await_human(config: core.Config, ticket: str) -> str:
    """In an attended run, park the ticket at a human gate; '' when the gate is open."""
    gate = core.needs_human(config, core.find_ticket(config, ticket))
    if not gate:
        return ""
    reason = f"{handoff.ATTENDED_REASON} review {ticket}, then 'kahnban confirm {ticket}' to take the {gate} gate"
    core.escalate(config, ticket, reason)
    return f"paused for a human before {gate}: run 'kahnban confirm {ticket}'"


def _implement(config: core.Config, rec: dispatcher.DispatchRecommendation, log: Path) -> str:
    ticket = rec.ticket_id or ""
    tree = config.project_root / ".worktrees" / ticket
    if not tree.is_dir():
        core.drop_lease(config, ticket)
        raise core.GateError(f"{ticket} has no worktree; the runner only drives worktree tickets")
    try:
        code, _ = _work(
            config,
            "coder",
            rec,
            tree,
            log,
            heartbeat=lambda: core.write_lease(config, ticket, CODER),
        )
    finally:
        core.drop_lease(config, ticket)
    if core.find_ticket(config, ticket).column != config.in_progress_column:
        return f"worker exit {code}; ticket already moved on"
    result = core.verify(config, ticket)
    if result.passed:
        return f"worker exit {code}; verified"
    return f"worker exit {code}; verify failed (exit {result.exit_code})"


def _merge_and_close(config: core.Config, ticket: str) -> str:
    try:
        merged = core.merge(config, ticket)
    except core.GateError as error:
        core.reject(config, ticket, INTEGRATOR, f"merge refused: {error}")
        return f"merge refused and sent back: {error}"
    if not merged.passed:
        core.reject(
            config,
            ticket,
            INTEGRATOR,
            f"integration tests failed on the merged result (exit {merged.exit_code}); "
            f"see {merged.artifact}",
        )
        return f"integration tests failed (exit {merged.exit_code}); sent back"
    core.done(config, ticket)
    core.cleanup(config, ticket)
    attempts.clear(config, ticket)
    return "merged, integration-tested, done and cleaned up"


def _work(
    config: core.Config,
    role: str,
    rec: dispatcher.DispatchRecommendation,
    cwd: Path,
    log: Path,
    *,
    heartbeat: Callable[[], None] | None = None,
) -> tuple[int, str]:
    """Run the configured worker for ``role`` with the prompt on stdin.

    The prompt comes whole from :mod:`kahnban.roles` (via the dispatcher), so a
    worker is told exactly what its agent file and the guard hold it to.
    """
    template = config.workers.get(role) or config.workers.get("default")
    if not template:
        raise RunStop(_NO_WORKER.format(role=f"role '{role}'"))
    ticket = rec.ticket_id or ""
    if ticket:
        core.refresh_baton_strict(config, ticket, f"starting the {role}")
    exit_checks.reset_nudges(config, role, ticket)
    command = template.replace("{role}", role.replace("_", "-")).replace("{ticket}", ticket)
    env = {
        **{key: value for key, value in os.environ.items() if key != trust.KEY_ENV},
        "KAHNBAN_GUARD_LOG": str(guard_log_path(log)),
        "KAHNBAN_ROLE": role,
        "KAHNBAN_TICKET": ticket,
        "KAHNBAN_PROJECT_ROOT": str(config.project_root),
        "KAHNBAN_WORKTREE": str(cwd),
    }
    # The command comes from board.config.json (the adopter's own config), so a
    # shell is fine; the prompt goes over stdin, never argv.
    process = subprocess.Popen(
        command,
        shell=True,
        cwd=str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        start_new_session=os.name != "nt",
    )
    deadline = time.monotonic() + config.worker_timeout_sec
    pending: str | None = rec.prompt
    while True:
        try:
            output, _ = process.communicate(
                input=pending, timeout=min(HEARTBEAT_SEC, max(deadline - time.monotonic(), 0.1))
            )
            code = process.returncode
            break
        except subprocess.TimeoutExpired:
            pending = None
            if time.monotonic() >= deadline:
                _kill_tree(process)
                output, _ = process.communicate()
                output = (output or "") + f"\nTIMEOUT after {config.worker_timeout_sec}s"
                code = 124
                break
            if heartbeat:
                heartbeat()
    with log.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(
            f"\n=== {datetime.now().isoformat(timespec='seconds')} {role} {ticket} "
            f"exit={code} ===\n$ {command}\n{output or ''}\n"
        )
    if code == 124:
        raise core.KahnbanError(f"{role} worker timed out after {config.worker_timeout_sec}s")
    if code != 0:
        # A worker that ends its turn exits 0 even when the task went badly; a
        # non-zero exit is the command itself failing (auth, missing binary, bad
        # flag). That is not the ticket's fault, so stop instead of escalating it.
        tail = "\n".join(line for line in (output or "").splitlines() if line.strip())[-800:]
        raise RunStop(
            f"{role} worker command exited {code}; fix the worker setup and re-run "
            f"(full output in {log}):\n{tail}"
        )
    return code, output or ""


def _kill_tree(process: subprocess.Popen[str]) -> None:
    """Kill the worker and everything it started, and nothing else."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _log_path(config: core.Config) -> Path:
    directory = config.board_path / core.ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8", newline="\n")
    return directory / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
