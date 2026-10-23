"""Command-line entry point for Kahnban.

Exit codes are part of the contract: 0 success, 1 refusal or lint violation,
2 configuration or I/O error.  Long text (a problem statement, verification
evidence) always arrives by file path or stdin — never on argv, which breaks on
Windows command-line limits and quoting.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from kahnban import __version__, core, dispatcher, gitops, ingest, linter, session, skills, worktree

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_ERROR = 2


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - exotic consoles
                pass


def _load(args: argparse.Namespace) -> core.Config:
    return core.load_config(
        Path(args.project_root) if args.project_root else None,
        Path(args.config) if args.config else None,
    )


def _read_text_argument(inline: str | None, path: str | None) -> str | None:
    """Resolve inline text, a file path, or ``-`` for stdin."""
    if path:
        if path == "-":
            return sys.stdin.read()
        return Path(path).read_text(encoding="utf-8")
    return inline


def _report(result: core.TransitionResult) -> None:
    for message in result.messages:
        print(message)
    commit = f" (commit {result.commit[:8]})" if result.commit else ""
    print(
        f"[OK] {result.ticket_id}: {result.from_column} -> {result.to_column}{commit}"
    )
    print(f"     {result.path}")


# --- handlers ---------------------------------------------------------------


def cmd_new(args: argparse.Namespace) -> int:
    config = _load(args)
    problem = _read_text_argument(args.problem, args.problem_file)
    result = core.create_ticket(config, args.title, problem=problem, owner=args.owner)
    _report(result)
    return EXIT_OK


def cmd_ready(args: argparse.Namespace) -> int:
    _report(core.ready(_load(args), args.ticket_id))
    return EXIT_OK


def cmd_claim(args: argparse.Namespace) -> int:
    config = _load(args)
    create_worktree = None
    if args.worktree:
        create_worktree = True
    elif args.no_worktree:
        create_worktree = False
    result = core.claim(
        config,
        args.ticket_id,
        args.owner,
        create_worktree=create_worktree,
        force=args.force,
        force_overlap=args.force_overlap,
        strict_wip=args.strict_wip,
        local=getattr(args, "local", False),
        reason=args.reason or "",
    )
    _report(result)
    if args.worktree or (create_worktree is None and config.use_worktrees):
        print(f"     work inside {config.project_root / '.worktrees' / result.ticket_id}")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    config = _load(args)
    result = core.verify(
        config,
        args.ticket_id,
        manual_evidence=Path(args.manual_evidence) if args.manual_evidence else None,
        force_scope=args.force_scope,
        reason=args.reason or "",
    )
    for message in result.messages:
        print(message)
    print(f"$ {result.command}")
    if result.output.strip():
        print(result.output.rstrip("\n"))
    if result.artifact:
        print(f"     full output: {result.artifact}")
    if result.passed and result.transition is not None:
        _report(result.transition)
        return EXIT_OK
    print(
        f"[FAIL] {result.ticket_id}: validation exited {result.exit_code}; "
        "ticket stays in place and the attempt is logged",
        file=sys.stderr,
    )
    return EXIT_REFUSED


def cmd_done(args: argparse.Namespace) -> int:
    config = _load(args)
    _report(core.done(config, args.ticket_id, merge_commit=args.merge_commit))
    print(f"Learnings advisory: Ticket {args.ticket_id} completed. Run '/reflect' before 'kahnban cleanup' to capture patterns.")
    return EXIT_OK


def cmd_approve(args: argparse.Namespace) -> int:
    _report(core.approve(_load(args), args.ticket_id, args.reviewer, note=args.note or ""))
    return EXIT_OK


def cmd_reject(args: argparse.Namespace) -> int:
    message = _read_text_argument(args.message, args.message_file)
    if not message:
        raise core.GateError("pass the reasons with --message TEXT or --message-file FILE")
    _report(core.reject(_load(args), args.ticket_id, args.reviewer, message))
    return EXIT_OK


def cmd_merge(args: argparse.Namespace) -> int:
    result = core.merge(_load(args), args.ticket_id)
    for message in result.messages:
        print(message)
    print(f"$ {result.command}")
    if result.output.strip():
        print(result.output.rstrip("\n"))
    if result.artifact:
        print(f"     full output: {result.artifact}")
    if result.passed and result.transition is not None:
        _report(result.transition)
        return EXIT_OK
    print(
        f"[FAIL] {result.ticket_id}: integration tests exited {result.exit_code}; "
        "the default branch was not changed",
        file=sys.stderr,
    )
    return EXIT_REFUSED


def cmd_run(args: argparse.Namespace) -> int:
    from kahnban import runner

    config = _load(args)
    result = runner.run(config, max_steps=args.max_steps)
    marker = "[WARN]" if result.parked else "[OK]"
    print(f"{marker} {result.stopped} ({len(result.steps)} step(s))")
    for ticket in result.parked:
        print(f"     waiting for a human: {ticket}")
    if result.log_path and result.log_path.exists():
        print(f"     worker output: {result.log_path}")
    # Parked work is not success: exit non-zero so a cron job or CI step notices.
    return EXIT_REFUSED if result.parked else EXIT_OK


def cmd_lease(args: argparse.Namespace) -> int:
    result = core.lease(_load(args), args.ticket_id, args.owner, minutes=args.minutes)
    if result is not None:
        _report(result)
    print(f"[OK] {args.ticket_id.upper()} leased by {args.owner}")
    return EXIT_OK


def cmd_escalate(args: argparse.Namespace) -> int:
    _report(core.escalate(_load(args), args.ticket_id, args.reason))
    return EXIT_OK


def cmd_unblock(args: argparse.Namespace) -> int:
    _report(core.unblock(_load(args), args.ticket_id, args.reason))
    return EXIT_OK


def cmd_spec(args: argparse.Namespace) -> int:
    from kahnban import specs

    config = _load(args)
    action = args.spec_action or "list"
    if action == "new":
        print(f"[OK] drafted {specs.new_spec(config, args.title)}")
        return EXIT_OK
    if action == "approve":
        spec = specs.approve_spec(config, args.spec_id, args.by)
        print(f"[OK] {spec.spec_id} approved by {args.by}: {len(spec.requirements)} requirement(s) frozen")
        return EXIT_OK
    if action == "coverage":
        report = specs.coverage(config, args.spec_id)
        for requirement, tickets in report.covered.items():
            marker = "[OK]  " if tickets else "[FAIL]"
            print(f"{marker} {requirement}: {', '.join(tickets) or 'no ticket'}")
        for ticket_id, requirement in report.unknown:
            print(f"[FAIL] {ticket_id} covers {requirement}, which {report.spec.spec_id} does not have")
        if not report.spec.approved:
            print(f"[WARN] {report.spec.spec_id} is not approved yet")
        return EXIT_OK if report.complete else EXIT_REFUSED
    for spec in specs.iter_specs(config):
        status = "approved" if spec.frozen else str(spec.fields.get("status") or "draft")
        if spec.approved and not spec.frozen:
            status = "approved, requirements changed since"
        print(f"  {spec.spec_id} [{status}] {spec.fields.get('title', '')} ({len(spec.requirements)} requirement(s))")
    return EXIT_OK


def cmd_guard(args: argparse.Namespace) -> int:
    from kahnban import guard

    return guard.main()


def cmd_move(args: argparse.Namespace) -> int:
    _report(core.move(_load(args), args.ticket_id, args.column, reason=args.reason))
    return EXIT_OK


def cmd_cleanup(args: argparse.Namespace) -> int:
    _report(
        core.cleanup(
            _load(args),
            args.ticket_id,
            abandon=args.abandon,
            reason=args.reason or "",
        )
    )
    return EXIT_OK


def _ingest_options(
    config: core.Config, args: argparse.Namespace
) -> ingest.IngestOptions:
    return ingest.options_for(
        config,
        heading_level=args.heading_level,
        section=args.section,
        per_file=args.per_file,
        chain=args.chain,
        owner=args.owner,
        update=args.update,
        promote=args.ready,
    )


def cmd_ingest(args: argparse.Namespace) -> int:
    config = _load(args)
    paths: list[Path] = []
    for pattern in args.plan:
        candidate = Path(pattern)
        if candidate.is_file():
            paths.append(candidate)
            continue
        # glob.glob (not Path.glob) so absolute patterns work too.
        matches = sorted(
            found
            for found in (Path(item) for item in glob.glob(pattern, recursive=True))
            if found.is_file()
        )
        if not matches:
            raise ingest.IngestError(f"no plan document matched: {pattern}")
        paths.extend(matches)
    reports = ingest.ingest(
        config, paths, options=_ingest_options(config, args), dry_run=args.dry_run
    )
    if args.json:
        print(json.dumps([report.as_dict() for report in reports], indent=2))
    else:
        print(ingest.render_report(reports), end="")
    drifted = any(report.drifted for report in reports)
    return EXIT_REFUSED if drifted and not args.dry_run else EXIT_OK


def cmd_capture(args: argparse.Namespace) -> int:
    config = _load(args)
    ideas = list(args.idea)
    text = _read_text_argument(None, args.from_file)
    if text:
        ideas.extend(
            line.strip().lstrip("-*").strip()
            for line in text.splitlines()
            if line.strip()
        )
    if not ideas:
        raise core.GateError("no ideas given; pass titles or --from-file FILE")
    report = ingest.capture(config, ideas, owner=args.owner, dry_run=args.dry_run)
    print(ingest.render_report([report]), end="")
    return EXIT_OK


def cmd_lint(args: argparse.Namespace) -> int:
    result = linter.lint(_load(args), strict=args.strict)
    print(
        linter.render_json(result) if args.json else linter.render_text(result), end=""
    )
    return EXIT_OK if result.ok else EXIT_REFUSED


def cmd_sync(args: argparse.Namespace) -> int:
    for path in core.sync(_load(args)):
        print(f"[OK] wrote {path}")
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.project_root) if args.project_root else Path.cwd()
    written = core.init_board(
        root,
        prefix=args.prefix,
        wip_limit=args.wip_limit,
        validation_command=args.validation_command or "",
        use_worktrees=not args.no_worktrees,
        agentic=getattr(args, "agentic", False),
    )
    print(f"[OK] initialized board in {root} with prefix {args.prefix.upper()}")
    for path in written:
        print(f"     {path}")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    config = _load(args)
    result = linter.lint(config)
    counts = ", ".join(
        f"{column}={count}" for column, count in result.column_counts.items()
    )
    print(f"Board: {config.board_path}")
    print(f"Columns: {counts}")
    print(
        f"Lint: {len(result.violations)} violation(s), {len(result.warnings)} warning(s)"
    )
    return EXIT_OK if result.ok else EXIT_REFUSED




def cmd_session(args: argparse.Namespace) -> int:
    config = _load(args)
    root = config.project_root

    flush = getattr(args, "flush", False)
    ticket_arg = getattr(args, "ticket", None)
    note_arg = _read_text_argument(
        getattr(args, "note", None), getattr(args, "note_file", None)
    )
    cmd_arg = getattr(args, "next_cmd", None)
    blocker_arg = _read_text_argument(
        getattr(args, "blocker", None), getattr(args, "blocker_file", None)
    )

    if flush or ticket_arg or note_arg or cmd_arg or blocker_arg:
        next_cmds = [cmd_arg] if cmd_arg else None
        session_update = session.SessionUpdate(
            ticket_id=ticket_arg,
            branch=getattr(args, "branch", None),
            worktree=getattr(args, "worktree", None),
            agent_harness=getattr(args, "harness", None),
            status=getattr(args, "status", None),
            context=note_arg,
            blockers=blocker_arg,
            next_commands=next_cmds,
        )
        state, written = session.sync_session(
            config,
            update=session_update,
        )
        print(f"[OK] updated session state in {written}")
        return EXIT_OK

    current = session.read_session(root)
    if not current:
        inspected = session.inspect_session(config)
        print("Active Session: (no ACTIVE_SESSION.md found)")
        if inspected["in_progress_tickets"]:
            print("In-progress tickets from board:")
            for t in inspected["in_progress_tickets"]:
                print(f"  - {t['id']} ({t['owner']}) branch: {t['branch']} worktree: {t['worktree']}")
        else:
            print("Board is idle (no in-progress tickets).")
        return EXIT_OK

    print(f"Active Session: {current.active_ticket or '(none)'} [{current.status}]")
    print(f"  Harness:  {current.agent_harness}")
    print(f"  Worktree: {current.active_worktree or '-'}")
    print(f"  Branch:   {current.branch or '-'}")
    print(f"  Updated:  {current.last_updated}")
    if current.context:
        print(f"  Context:  {current.context}")
    if current.modified_files:
        print(f"  Modified: {len(current.modified_files)} file(s)")
        for f in current.modified_files[:5]:
            print(f"    - {f}")
        if len(current.modified_files) > 5:
            print(f"    ... and {len(current.modified_files) - 5} more")
    if current.blockers:
        print(f"  Blockers: {current.blockers}")
    if current.next_commands:
        print("  Next Command(s):")
        for cmd in current.next_commands:
            print(f"    $ {cmd}")
    inspected = session.inspect_session(config)
    dirty_delta = set(inspected.get("modified_files", [])) - set(current.modified_files)
    if dirty_delta:
        print(f"  Note: {len(dirty_delta)} unrecorded file change(s) in working tree; run with --flush to synchronize.")
    return EXIT_OK


def cmd_learnings(args: argparse.Namespace) -> int:
    from kahnban import learnings
    try:
        config = _load(args)
        root = config.project_root
    except core.ConfigError:
        root = Path(args.project_root).resolve() if getattr(args, 'project_root', None) else Path.cwd().resolve()
    action = getattr(args, "learnings_action", None) or "list"

    if action == "list":
        records = learnings.list_learnings(root, include_archive=getattr(args, "all", False))
        if not records:
            print("No learnings recorded in ./learnings/ (run '/reflect' or 'kahnban learnings capture').")
            return EXIT_OK
        label = "All Learnings (Active & Archived)" if getattr(args, "all", False) else "Active Learnings"
        print(f"{label} ({len(records)}):")
        for r in records:
            status_tag = f"[{r.status.upper()}]"
            occurrences_tag = f"({r.occurrences}x, {r.severity})"
            print(f"  - {r.id}: {r.title} {status_tag} {occurrences_tag} [cat: {r.category}]")
        return EXIT_OK

    if action == "show":
        records = learnings.list_learnings(root, include_archive=True)
        target = next((r for r in records if r.id.lower() == args.id.lower() or r.title.lower() == args.id.lower()), None)
        if not target:
            sys.stderr.write(f"Learning record '{args.id}' not found.\n")
            return EXIT_REFUSED
        print(target.render_markdown())
        return EXIT_OK

    if action == "capture":
        rec, is_new = learnings.capture_learning(
            root,
            title=args.title,
            problem=args.problem or "",
            ticket_id=args.ticket or "",
            location=args.location or "",
            trigger=args.trigger or "",
            category=args.category or "convention",
            severity=args.severity or "medium",
            target_paths=args.path or [],
            systemic_diagnosis=args.diagnosis or "",
            proposed_remediation=args.remediation or "",
        )
        if is_new:
            print(f"[OK] Created new learning {rec.id} ({rec.title}) in ./learnings/")
        else:
            print(f"[OK] Augmented existing pattern {rec.id} ({rec.title}) -> occurrences: {rec.occurrences}, severity: {rec.severity}")
        return EXIT_OK

    if action == "promote":
        try:
            raw_lvl = str(args.level).strip().lower()
            lvl = raw_lvl if raw_lvl.startswith("level-") else f"level-{raw_lvl}"
            rec = learnings.promote_learning(
                root,
                args.id,
                level=lvl,
                artifact=args.artifact,
                resolution_notes=args.notes or "",
            )
            print(f"[OK] Promoted {rec.id} ({rec.title}) to Level {args.level}. Moved to ./learnings/archive/")
            return EXIT_OK
        except Exception as ex:
            sys.stderr.write(f"Promotion failed: {ex}\n")
            return EXIT_REFUSED

    return EXIT_OK




def cmd_next(args: argparse.Namespace) -> int:
    config = _load(args)
    pref_role = getattr(args, "role", None)
    rec = dispatcher.resolve_next_action(config, preferred_role=pref_role)

    if getattr(args, "json", False):
        import json
        print(json.dumps(rec.to_dict(), indent=2, default=str))
        return EXIT_OK

    print(f"\n=== Kahnban Situational Next Action ===")
    print(f"Action:         {rec.action.upper()}")
    print(f"Assigned Role:  {rec.assigned_role}")
    if rec.ticket_id:
        print(f"Target Ticket:  {rec.ticket_id} ({rec.ticket_title or ''})")
    if rec.worktree:
        print(f"Worktree:       {rec.worktree}")
    print(f"Summary:        {rec.summary}")
    if rec.command:
        print(f"\nRecommended Command:\n  $ {rec.command}")
    if rec.prompt:
        print(f"\nAgent Bootstrap Prompt:\n  > {rec.prompt}")
    print("=======================================\n")
    return EXIT_OK


def cmd_feedback(args: argparse.Namespace) -> int:
    """Older name for ``reject``: feedback that does not move the ticket loops forever."""
    _report(core.reject(_load(args), args.ticket, args.author or "qa_reviewer", args.message))
    return EXIT_OK

def cmd_skills(args: argparse.Namespace) -> int:
    try:
        config = _load(args)
        root = config.project_root
    except core.ConfigError:
        root = Path(args.project_root).resolve() if getattr(args, "project_root", None) else Path.cwd().resolve()

    action = getattr(args, "skills_action", None)
    if action == "list":
        available = skills.list_skills(root)
        if not available:
            print("No skills found.")
            return EXIT_OK
        print("Available Agent Skills:")
        for sk in available:
            print(f"  - /{sk.name} [{sk.source}]")
            if sk.description:
                print(f"      {sk.description}")
        return EXIT_OK

    # install action (default)
    source = getattr(args, "source", "bundled") or "bundled"
    harness = getattr(args, "harness", "auto") or "auto"
    dry_run = getattr(args, "dry_run", False)

    res = skills.install_skills(
        root,
        harness=harness,
        source=source,
        dry_run=dry_run,
    )
    for msg in res.get("messages", []):
        print(f"  {msg}")
    print(f"[OK] installed {len(res['installed_skills'])} skill(s) from '{res['source']}':")
    for s in res["installed_skills"]:
        print(f"  - /{s}")
    print("Configured harness targets:")
    for h in res["configured_harnesses"]:
        print(f"  - {h}")
    return EXIT_OK


# --- parser -----------------------------------------------------------------


ROOT_HELP = "repository root holding plans/board.config.json (default: discovered)"
CONFIG_HELP = "path to board.config.json"


def _board_options() -> argparse.ArgumentParser:
    """Board-location flags, reusable in the subcommand position.

    ``argparse.SUPPRESS`` keeps an unspecified subcommand flag from clobbering a
    value already given before the subcommand, so both of these work and mean
    the same thing:

        kahnban --config plans/board.config.json lint
        kahnban lint --config plans/board.config.json
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project-root", default=argparse.SUPPRESS, help=ROOT_HELP)
    common.add_argument("--config", default=argparse.SUPPRESS, help=CONFIG_HELP)
    return common


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kahnban",
        description="Portable agentic Kanban workflow engine",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--project-root", help=ROOT_HELP)
    parser.add_argument("--config", help=CONFIG_HELP)
    board = _board_options()
    subparsers = parser.add_subparsers(dest="command")

    new = subparsers.add_parser(
        "new",
        parents=[board], help="create a ticket in the backlog")
    new.add_argument("title")
    new.add_argument("--problem", help="short problem statement")
    new.add_argument(
        "--problem-file", help="file holding the problem statement ('-' for stdin)"
    )
    new.add_argument("--owner", default="unassigned")
    new.set_defaults(handler=cmd_new)

    ready = subparsers.add_parser(
        "ready",
        parents=[board], help="refining -> ready (gated)")
    ready.add_argument("ticket_id")
    ready.set_defaults(handler=cmd_ready)

    claim = subparsers.add_parser(
        "claim",
        parents=[board], help="ready -> in-progress (gated)")
    claim.add_argument("ticket_id")
    claim.add_argument("--owner", required=True)
    claim.add_argument(
        "--worktree", action="store_true", help="force worktree provisioning"
    )
    claim.add_argument(
        "--no-worktree", action="store_true", help="skip worktree provisioning"
    )
    claim.add_argument(
        "--force", action="store_true", help="claim from a non-ready column"
    )
    claim.add_argument(
        "--force-overlap", action="store_true", help="claim despite a radius overlap"
    )
    claim.add_argument(
        "--strict-wip", action="store_true", help="fail instead of warn at the WIP limit"
    )
    claim.add_argument(
        "--local", action="store_true", help="skip pulling and pushing to origin remote"
    )
    claim.add_argument("--reason", help="required with any override")
    claim.set_defaults(handler=cmd_claim)

    verify = subparsers.add_parser(
        "verify",
        parents=[board], help="run the ticket's validation command; in-progress -> verifying"
    )
    verify.add_argument("ticket_id")
    verify.add_argument(
        "--manual-evidence",
        help="evidence file for validation_class: visual-deferred tickets",
    )
    verify.add_argument(
        "--force-scope", action="store_true", help="accept a diff outside the radius"
    )
    verify.add_argument("--reason", help="required with any override")
    verify.set_defaults(handler=cmd_verify)

    done = subparsers.add_parser(
        "done",
        parents=[board], help="verifying -> done (requires a merge)")
    done.add_argument("ticket_id")
    done.add_argument("--merge-commit", help="sha of the merge on the default branch")
    done.set_defaults(handler=cmd_done)

    approve = subparsers.add_parser(
        "approve",
        parents=[board], help="a reviewer other than the owner signs off a verified ticket")
    approve.add_argument("ticket_id")
    approve.add_argument("--reviewer", required=True, help="who is approving (not the owner)")
    approve.add_argument("--note", help="optional review note for the Log")
    approve.set_defaults(handler=cmd_approve)

    reject = subparsers.add_parser(
        "reject",
        parents=[board], help="send a verified ticket back to in-progress with the reasons")
    reject.add_argument("ticket_id")
    reject.add_argument("--reviewer", default="reviewer", help="who is rejecting")
    reject.add_argument("--message", "-m", help="what has to be fixed")
    reject.add_argument("--message-file", help="read the reasons from FILE, or - for stdin")
    reject.set_defaults(handler=cmd_reject)

    merge = subparsers.add_parser(
        "merge",
        parents=[board],
        help="merge onto the default branch, test the result, and land it only if green",
    )
    merge.add_argument("ticket_id")
    merge.set_defaults(handler=cmd_merge)

    run_parser = subparsers.add_parser(
        "run",
        parents=[board],
        help="drive the board with the configured workers until it is idle",
    )
    run_parser.add_argument("--max-steps", type=int, default=20, help="stop after N steps")
    run_parser.set_defaults(handler=cmd_run)

    lease_parser = subparsers.add_parser(
        "lease",
        parents=[board],
        help="renew your hold on an in-progress ticket, or take over an expired one",
    )
    lease_parser.add_argument("ticket_id")
    lease_parser.add_argument("--owner", required=True)
    lease_parser.add_argument("--minutes", type=int, help="lease length (default: lease_minutes)")
    lease_parser.set_defaults(handler=cmd_lease)

    escalate_parser = subparsers.add_parser(
        "escalate", parents=[board], help="park a ticket for a human (sets blocked_on)"
    )
    escalate_parser.add_argument("ticket_id")
    escalate_parser.add_argument("--reason", required=True, help="the question for the human")
    escalate_parser.set_defaults(handler=cmd_escalate)

    unblock_parser = subparsers.add_parser(
        "unblock", parents=[board], help="clear blocked_on once a human has answered"
    )
    unblock_parser.add_argument("ticket_id")
    unblock_parser.add_argument("--reason", required=True, help="what was decided")
    unblock_parser.set_defaults(handler=cmd_unblock)

    spec_parser = subparsers.add_parser(
        "spec", parents=[board], help="specs: draft, approve (the human gate), check coverage"
    )
    spec_sub = spec_parser.add_subparsers(dest="spec_action")
    spec_new = spec_sub.add_parser("new", help="draft the next SPEC-NNN in .agents/specs/")
    spec_new.add_argument("title")
    spec_approve = spec_sub.add_parser(
        "approve", help="approve a spec and freeze its requirements (a human decision)"
    )
    spec_approve.add_argument("spec_id")
    spec_approve.add_argument("--by", required=True, help="who approves it")
    spec_coverage = spec_sub.add_parser(
        "coverage", help="exit 1 unless every requirement is covered by a ticket"
    )
    spec_coverage.add_argument("spec_id")
    spec_sub.add_parser("list", help="list specs and their status")
    spec_parser.set_defaults(handler=cmd_spec)

    guard_parser = subparsers.add_parser(
        "guard", help="PreToolUse hook: keep a factory worker inside its role (reads stdin)"
    )
    guard_parser.set_defaults(handler=cmd_guard)

    move = subparsers.add_parser(
        "move",
        parents=[board], help="escape hatch; always logged")
    move.add_argument("ticket_id")
    move.add_argument("column")
    move.add_argument("--reason", required=True)
    move.set_defaults(handler=cmd_move)

    cleanup = subparsers.add_parser(
        "cleanup",
        parents=[board], help="remove junctions, worktree, and branch"
    )
    cleanup.add_argument("ticket_id")
    cleanup.add_argument(
        "--abandon", action="store_true", help="clean up a ticket that is not done"
    )
    cleanup.add_argument("--reason", help="required with --abandon")
    cleanup.set_defaults(handler=cmd_cleanup)

    ingest_command = subparsers.add_parser(
        "ingest",
        parents=[board], help="turn a markdown plan into backlog tickets (idempotent)",
        description=(
            "Split a plan document into one ticket per work section. Tickets "
            "always land in the backlog with acceptance boxes unchecked; use "
            "--ready to run each one through the real refinement gate."
        ),
    )
    ingest_command.add_argument("plan", nargs="+", help="plan file(s) or glob(s)")
    ingest_command.add_argument(
        "--dry-run", action="store_true", help="show what would be created"
    )
    ingest_command.add_argument(
        "--heading-level", type=int, help="heading level that marks a work item"
    )
    ingest_command.add_argument(
        "--section", help="only ingest the subtree under this heading"
    )
    ingest_command.add_argument(
        "--per-file", action="store_true", help="one ticket per document"
    )
    ingest_command.add_argument(
        "--chain",
        action="store_true",
        help="make each ticket depend on the previous one (sequential plans)",
    )
    ingest_command.add_argument(
        "--update",
        action="store_true",
        help="refresh un-started tickets whose source section changed",
    )
    ingest_command.add_argument(
        "--ready",
        action="store_true",
        help="attempt the refinement gate; tickets that fail stay in the backlog",
    )
    ingest_command.add_argument("--owner", default="unassigned")
    ingest_command.add_argument("--json", action="store_true")
    ingest_command.set_defaults(handler=cmd_ingest)

    capture = subparsers.add_parser(
        "capture",
        parents=[board], help="capture rough ideas as backlog tickets (one commit)"
    )
    capture.add_argument("idea", nargs="*", help="one title per idea")
    capture.add_argument(
        "--from-file", help="file with one idea per line ('-' for stdin)"
    )
    capture.add_argument("--owner", default="unassigned")
    capture.add_argument("--dry-run", action="store_true")
    capture.set_defaults(handler=cmd_capture)

    lint = subparsers.add_parser(
        "lint",
        parents=[board], help="run board rules BL01-BL16")
    lint.add_argument("--json", action="store_true", help="machine-readable output")
    lint.add_argument(
        "--strict", action="store_true", help="promote WIP warnings to violations"
    )
    lint.set_defaults(handler=cmd_lint)

    sync = subparsers.add_parser(
        "sync",
        parents=[board], help="regenerate STATUS.md and status.json")
    sync.set_defaults(handler=cmd_sync)

    status_command = subparsers.add_parser(
        "status",
        parents=[board], help="column counts + lint summary")
    status_command.set_defaults(handler=cmd_status)

    init = subparsers.add_parser(
        "init",
        parents=[board], help="scaffold the board in this repository")
    init.add_argument("--prefix", required=True, help="ticket id prefix, e.g. HOA")
    init.add_argument("--wip-limit", type=int, default=3)
    init.add_argument("--validation-command", help="default validation command")
    init.add_argument(
        "--no-worktrees", action="store_true", help="set use_worktrees to false"
    )
    init.add_argument(
        "--agentic", action="store_true", help="scaffold .agents/, templates, and ACTIVE_SESSION.md"
    )
    init.set_defaults(handler=cmd_init)

    for cmd_name in ("session", "handoff"):
        sp = subparsers.add_parser(
            cmd_name,
            parents=[board],
            help="inspect or update cross-harness session state (ACTIVE_SESSION.md)",
        )
        sp.add_argument("--flush", action="store_true", help="flush/resync state from live worktrees")
        sp.add_argument("--ticket", help="active ticket id")
        sp.add_argument("--worktree", help="active worktree path")
        sp.add_argument("--branch", help="active branch name")
        sp.add_argument("--harness", help="current AI harness (claude-code, chatgpt, antigravity, cursor)")
        sp.add_argument("--status", help="session status (idle, in_progress, review, blocked)")
        sp.add_argument("--note", help="context or progress note for handoff")
        sp.add_argument("--note-file", help="path to note file, or - for stdin")
        sp.add_argument("--blocker", help="failing test trace or blocker reason")
        sp.add_argument("--blocker-file", help="path to blocker file, or - for stdin")
        sp.add_argument("--next-cmd", help="immediate shell command for incoming agent")
        sp.set_defaults(handler=cmd_session)

    # Learnings parser
    learnings_parser = subparsers.add_parser(
        "learnings",
        parents=[board],
        help="manage project learnings queue and structural improvements",
    )
    learnings_sub = learnings_parser.add_subparsers(dest="learnings_action")

    l_list = learnings_sub.add_parser("list", help="list active learnings in ./learnings/")
    l_list.add_argument("--all", action="store_true", help="include archived learnings")
    l_list.set_defaults(handler=cmd_learnings)

    l_show = learnings_sub.add_parser("show", help="show details of a learning record")
    l_show.add_argument("id", help="learning ID (e.g. LRN-0001)")
    l_show.set_defaults(handler=cmd_learnings)

    l_capture = learnings_sub.add_parser("capture", help="capture a new learning or augment an existing pattern")
    l_capture.add_argument("--title", required=True, help="short descriptive pattern title")
    l_capture.add_argument("--problem", help="problem or friction description")
    l_capture.add_argument("--ticket", help="associated ticket ID (e.g. HOA-002)")
    l_capture.add_argument("--location", help="file and line location where observed")
    l_capture.add_argument("--trigger", help="trigger or symptom observed")
    l_capture.add_argument("--category", choices=["architecture", "typing-lint", "testing", "convention"], default="convention")
    l_capture.add_argument("--severity", choices=["low", "medium", "high", "critical"], default="medium")
    l_capture.add_argument("--path", action="append", help="target path(s) involved")
    l_capture.add_argument("--diagnosis", help="systemic environmental root cause")
    l_capture.add_argument("--remediation", help="proposed structural remediation")
    l_capture.set_defaults(handler=cmd_learnings)

    l_promote = learnings_sub.add_parser("promote", help="promote learning to structural defense and archive")
    l_promote.add_argument("id", help="learning ID to promote")
    l_promote.add_argument("--level", required=True, choices=["1", "2", "3", "4", "level-1", "level-2", "level-3", "level-4"], help="enforcement level applied (1-4 or level-1..4)")
    l_promote.add_argument("--notes", help="resolution and remediation notes")
    l_promote.add_argument(
        "--artifact",
        required=True,
        help="what now guards it: a lint rule (BL19), a path, a commit, or a ticket id",
    )
    l_promote.set_defaults(handler=cmd_learnings)

    learnings_parser.set_defaults(handler=cmd_learnings)

    # --- next (situational dispatcher)
    next_parser = subparsers.add_parser(
        "next",
        parents=[board],
        help="resolve deterministic next step, target ticket, and agent bootstrap prompt",
    )
    next_parser.add_argument("--json", action="store_true", help="output structured JSON baton")
    next_parser.add_argument(
        "--role",
        choices=["coder", "qa_reviewer", "reviewer", "integrator", "spec_analyst", "curator"],
        help="filter next action for a specific agent role",
    )
    next_parser.set_defaults(handler=cmd_next)

    # --- feedback (record review/QA rejection into handoff baton)
    fb_parser = subparsers.add_parser(
        "feedback",
        parents=[board],
        help="alias of 'reject': send a verified ticket back with feedback",
    )
    fb_parser.add_argument("ticket", help="ticket ID (e.g. KB-001)")
    fb_parser.add_argument("--message", "-m", required=True, help="rejection feedback explanation")
    fb_parser.add_argument("--author", default="qa_reviewer", help="author role recording feedback")
    fb_parser.set_defaults(handler=cmd_feedback)

    skills_parser = subparsers.add_parser(
        "skills",
        parents=[board],
        help="install, list, and configure Matt Pocock & PSTACK skills across AI harnesses",
    )
    skills_parser.add_argument(
        "--source",
        default="bundled",
        help="skill source: 'bundled' (default: Matt Pocock + PSTACK core), 'mattpocock', 'pstack', or 'pstack:<skill>'",
    )
    skills_parser.add_argument(
        "--harness",
        choices=["auto", "agents", "claude", "gemini", "cursor", "vscode", "hermes", "all"],
        default="auto",
        help="target AI harness: 'auto' (default: .agents/skills + detected harnesses), 'claude', 'gemini', 'cursor', 'all'",
    )
    skills_parser.add_argument("--dry-run", action="store_true", help="simulate without writing files")
    skills_sub = skills_parser.add_subparsers(dest="skills_action")

    inst_parser = skills_sub.add_parser("install", help="install skills into project and harnesses")
    inst_parser.add_argument(
        "--source",
        default="bundled",
        help="skill source: 'bundled' (default), 'mattpocock', 'pstack', or 'pstack:<skill>'",
    )
    inst_parser.add_argument(
        "--harness",
        choices=["auto", "agents", "claude", "gemini", "cursor", "vscode", "hermes", "all"],
        default="auto",
        help="target AI harness: 'auto' (default), 'claude', 'gemini', 'cursor', 'all'",
    )
    inst_parser.add_argument("--dry-run", action="store_true", help="simulate without writing files")
    inst_parser.set_defaults(handler=cmd_skills)

    list_parser = skills_sub.add_parser("list", help="list installed and available skills")
    list_parser.set_defaults(handler=cmd_skills)

    skills_parser.set_defaults(handler=cmd_skills)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_OK
    role = os.environ.get("KAHNBAN_ROLE", "").strip()
    if role and args.command != "guard":  # the hook itself runs with the role set
        from kahnban import guard

        command = args.command
        if command == "spec":
            command = f"spec {getattr(args, 'spec_action', None) or 'list'}"
        problem = guard.command_problem(role, command)
        if problem:
            print(f"[FAIL] {problem} (KAHNBAN_ROLE={role})", file=sys.stderr)
            return EXIT_REFUSED
    try:
        return int(args.handler(args))
    except core.ConfigError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return EXIT_ERROR
    except (core.KahnbanError, gitops.GitError, worktree.WorktreeError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return EXIT_REFUSED
    except OSError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
