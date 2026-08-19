"""Command-line entry point for Kahnban.

Exit codes are part of the contract: 0 success, 1 refusal or lint violation,
2 configuration or I/O error.  Long text (a problem statement, verification
evidence) always arrives by file path or stdin — never on argv, which breaks on
Windows command-line limits and quoting.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from kahnban import __version__, core, gitops, linter, worktree

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
    _report(core.done(_load(args), args.ticket_id, merge_commit=args.merge_commit))
    return EXIT_OK


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


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kahnban",
        description="Portable agentic Kanban workflow engine",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--project-root",
        help="repository root holding plans/board.config.json (default: discovered)",
    )
    parser.add_argument("--config", help="path to board.config.json")
    subparsers = parser.add_subparsers(dest="command")

    new = subparsers.add_parser("new", help="create a ticket in the backlog")
    new.add_argument("title")
    new.add_argument("--problem", help="short problem statement")
    new.add_argument(
        "--problem-file", help="file holding the problem statement ('-' for stdin)"
    )
    new.add_argument("--owner", default="unassigned")
    new.set_defaults(handler=cmd_new)

    ready = subparsers.add_parser("ready", help="refining -> ready (gated)")
    ready.add_argument("ticket_id")
    ready.set_defaults(handler=cmd_ready)

    claim = subparsers.add_parser("claim", help="ready -> in-progress (gated)")
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
    claim.add_argument("--reason", help="required with any override")
    claim.set_defaults(handler=cmd_claim)

    verify = subparsers.add_parser(
        "verify", help="run the ticket's validation command; in-progress -> verifying"
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

    done = subparsers.add_parser("done", help="verifying -> done (requires a merge)")
    done.add_argument("ticket_id")
    done.add_argument("--merge-commit", help="sha of the merge on the default branch")
    done.set_defaults(handler=cmd_done)

    move = subparsers.add_parser("move", help="escape hatch; always logged")
    move.add_argument("ticket_id")
    move.add_argument("column")
    move.add_argument("--reason", required=True)
    move.set_defaults(handler=cmd_move)

    cleanup = subparsers.add_parser(
        "cleanup", help="remove junctions, worktree, and branch"
    )
    cleanup.add_argument("ticket_id")
    cleanup.add_argument(
        "--abandon", action="store_true", help="clean up a ticket that is not done"
    )
    cleanup.add_argument("--reason", help="required with --abandon")
    cleanup.set_defaults(handler=cmd_cleanup)

    lint = subparsers.add_parser("lint", help="run board rules BL01-BL16")
    lint.add_argument("--json", action="store_true", help="machine-readable output")
    lint.add_argument(
        "--strict", action="store_true", help="promote WIP warnings to violations"
    )
    lint.set_defaults(handler=cmd_lint)

    sync = subparsers.add_parser("sync", help="regenerate STATUS.md and status.json")
    sync.set_defaults(handler=cmd_sync)

    status_command = subparsers.add_parser("status", help="column counts + lint summary")
    status_command.set_defaults(handler=cmd_status)

    init = subparsers.add_parser("init", help="scaffold the board in this repository")
    init.add_argument("--prefix", required=True, help="ticket id prefix, e.g. HOA")
    init.add_argument("--wip-limit", type=int, default=3)
    init.add_argument("--validation-command", help="default validation command")
    init.add_argument(
        "--no-worktrees", action="store_true", help="set use_worktrees to false"
    )
    init.set_defaults(handler=cmd_init)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_OK
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
