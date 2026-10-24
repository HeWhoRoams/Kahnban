"""Stdio JSON-RPC 2.0 MCP server exposing the board to agents.

Protocol invariants (plan §4.6):
* newline-delimited JSON-RPC 2.0 on stdio; stdout carries frames only,
* notifications (messages without ``id``) never receive a response,
* unknown requests answer ``-32601``; unparseable input answers ``-32700``
  with ``id: null``,
* all logging goes to stderr,
* project root resolution: ``--project-root`` argv, then
  ``KAHNBAN_PROJECT_ROOT``, then the working directory,
* tools call :mod:`kahnban.core` in-process — no subprocess round trips.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from kahnban import __version__, core, frontmatter, gitops, ingest, linter, session, worktree

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kahnban"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def log(message: str) -> None:
    """Diagnostics go to stderr; stdout is reserved for protocol frames."""
    print(f"[kahnban-mcp] {message}", file=sys.stderr, flush=True)


# --- tool definitions -------------------------------------------------------


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "kanban_board_status",
        "description": "Column counts plus a lint summary. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strict": {
                    "type": "boolean",
                    "description": "Promote WIP warnings to violations.",
                }
            },
        },
    },
    {
        "name": "kanban_ticket_get",
        "description": "Read one ticket: column, frontmatter, and full body.",
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": _string("Ticket id, e.g. HOA-007.")},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "kanban_ticket_new",
        "description": (
            "Create a ticket in the backlog column. Body sections may be filled "
            "in directly; acceptance criteria are always written unchecked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": _string("One-line outcome statement."),
                "problem": _string("Problem statement for the body."),
                "owner": _string("Optional owner; defaults to unassigned."),
                "acceptance": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Testable conditions, one per checkbox.",
                },
                "blast_radius": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files or directory prefixes this ticket owns.",
                },
                "notes": _string("Implementation notes."),
                "validation": _string("Command that exits non-zero on failure."),
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ticket ids that must be done first.",
                },
                "design_docs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to design documents that must exist.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "kanban_plan_ingest",
        "description": (
            "Turn a markdown plan document into backlog tickets, one per work "
            "section. Idempotent: re-ingesting skips sections already on the "
            "board and reports sections whose source text changed. Everything "
            "lands in the backlog with unchecked criteria; pass ready=true to "
            "run each ticket through the real refinement gate."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": _string("Plan document path, relative to the project root."),
                "dry_run": {
                    "type": "boolean",
                    "description": "Report what would be created without writing.",
                },
                "heading_level": {
                    "type": "integer",
                    "description": "Heading level marking a work item (auto-detected).",
                },
                "section": _string("Only ingest the subtree under this heading."),
                "per_file": {
                    "type": "boolean",
                    "description": "Treat the whole document as one ticket.",
                },
                "chain": {
                    "type": "boolean",
                    "description": "Make each ticket depend on the previous one.",
                },
                "update": {
                    "type": "boolean",
                    "description": "Refresh un-started tickets whose source changed.",
                },
                "ready": {
                    "type": "boolean",
                    "description": "Attempt the refinement gate after ingesting.",
                },
                "owner": _string("Owner for the created tickets."),
            },
            "required": ["path"],
        },
    },
    {
        "name": "kanban_capture",
        "description": (
            "Capture rough ideas as backlog tickets in a single commit - the "
            "ideation entry point."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ideas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One title per idea.",
                },
                "owner": _string("Owner for the created tickets."),
                "dry_run": {"type": "boolean"},
            },
            "required": ["ideas"],
        },
    },
    {
        "name": "kanban_ticket_ready",
        "description": "Move a refined ticket to the ready column (gated).",
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": _string("Ticket id.")},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "kanban_ticket_claim",
        "description": (
            "Claim a ready ticket into an isolated worktree. Refuses when the "
            "blast radius overlaps in-flight work."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "owner": _string("Agent or human name taking ownership."),
                "create_worktree": {
                    "type": "boolean",
                    "description": "Provision .worktrees/<ID>; defaults to true.",
                },
                "strict_wip": {"type": "boolean"},
                "force": {"type": "boolean"},
                "force_overlap": {"type": "boolean"},
                "reason": _string("Required with any override."),
            },
            "required": ["ticket_id", "owner"],
        },
    },
    {
        "name": "kanban_ticket_verify",
        "description": (
            "Run the ticket's validation command server-side and advance only on "
            "exit code 0. Returns the captured output and exit code."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "manual_evidence_path": _string(
                    "Evidence file for validation_class: visual-deferred tickets."
                ),
                "force_scope": {"type": "boolean"},
                "reason": _string("Required with any override."),
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "kanban_ticket_done",
        "description": "Move a verified ticket to done once its branch is merged.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "merge_commit": _string("Merge sha on the default branch."),
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "kanban_ticket_move",
        "description": "Escape hatch: move a ticket to any column with a logged reason.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "column": _string("Target column, e.g. 1-refining or archive."),
                "reason": _string("Why the manual move is needed."),
            },
            "required": ["ticket_id", "column", "reason"],
        },
    },
    {
        "name": "kanban_cleanup",
        "description": "Remove the ticket's junctions, worktree, and branch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "abandon": {"type": "boolean"},
                "reason": _string("Required with abandon."),
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "kanban_sync",
        "description": "Regenerate STATUS.md and status.json projections.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kanban_session_status",
        "description": "Inspect live cross-harness session state (ACTIVE_SESSION.md), in-progress tickets, and active worktrees.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inspect_live": {"type": "boolean", "description": "If true, also inspect live worktree git status."}
            },
        },
    },
    {
        "name": "kanban_session_get",
        "description": "Canonical alias for kanban_session_status. Inspect live cross-harness session state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inspect_live": {"type": "boolean", "description": "If true, also inspect live worktree git status."}
            },
        },
    },
    {
        "name": "kanban_next",
        "description": "Resolve the deterministic next action, target ticket, specialized persona, and pre-formatted prompt for autonomous agent relay.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["coder", "qa_reviewer", "reviewer", "integrator", "spec_analyst", "curator"],
                    "description": "Optional filter for a specific agent role",
                }
            },
        },
    },
    {
        "name": "kanban_ticket_approve",
        "description": (
            "Sign off a verified ticket as a reviewer other than its owner. Records the "
            "approved branch tip; done refuses on require_review boards without it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "reviewer": _string("Who is approving; must not be the owner."),
                "note": _string("Optional review note for the Log."),
            },
            "required": ["ticket_id", "reviewer"],
        },
    },
    {
        "name": "kanban_ticket_reject",
        "description": (
            "Send a verified ticket back to in-progress. The feedback is committed to "
            "the ticket's Log and every acceptance box is unticked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "feedback": _string("What has to be fixed."),
                "reviewer": _string("Who is rejecting (default: qa_reviewer)."),
            },
            "required": ["ticket_id", "feedback"],
        },
    },
    {
        "name": "kanban_ticket_merge",
        "description": (
            "Merge queue: merge the ticket branch onto the current default branch in a "
            "throwaway worktree, run the feature and regression tests on the result, "
            "and fast-forward the default branch only if they pass."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": _string("Ticket id.")},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "kanban_ticket_lease",
        "description": (
            "Renew your lease on an in-progress ticket, or take over one whose holder's "
            "lease expired. kanban_next skips tickets with a live lease."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "owner": _string("Who is working the ticket."),
                "minutes": {"type": "integer", "description": "Lease length."},
            },
            "required": ["ticket_id", "owner"],
        },
    },
    {
        "name": "kanban_ticket_escalate",
        "description": (
            "Park a ticket for a human by setting blocked_on; kanban_next skips it "
            "until a human runs kahnban unblock. Use it instead of guessing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket id."),
                "reason": _string("The question or decision the human must answer."),
            },
            "required": ["ticket_id", "reason"],
        },
    },
    {
        "name": "kanban_feedback",
        "description": "Alias of kanban_ticket_reject: send a verified ticket back to in-progress with feedback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Ticket ID being rejected (e.g. KB-001)"),
                "feedback": _string("Detailed explanation of rejection reasons and required fixes"),
                "author": _string("Author role recording feedback (default: qa_reviewer)"),
            },
            "required": ["ticket_id", "feedback"],
        },
    },
    {
        "name": "kanban_session_update",
        "description": "Atomically update .agents/state/ACTIVE_SESSION.md with active context, next commands, and blockers for cross-harness handoff.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": _string("Active ticket id being worked on (or active_ticket)"),
                "active_ticket": _string("Active ticket id being worked on"),
                "summary": _string("Summary of progress and current context (or context)"),
                "context": _string("Summary of progress and current context"),
                "status": _string("Session status (idle, in_progress, review, blocked)"),
                "harness": _string("Current AI harness name"),
                "blockers": _string("Failing test traces or blocker explanations"),
                "next_command": _string("Single immediate shell command to execute"),
                "next_commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered shell commands the incoming agent should execute immediately"
                },
                "modified_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicit list of modified files (overrides worktree auto-detection)"
                },
                "flush_from_worktree": {"type": "boolean", "description": "Whether to auto-detect modified files from the active worktree"}
            },
        },
    },
]


class Server:
    """One MCP session over a pair of text streams."""

    def __init__(
        self,
        project_root: Path,
        *,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self.project_root = project_root
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.initialized = False
        self.handlers: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": lambda params: {},
        }

    # --- transport ---------------------------------------------------------

    def serve_forever(self) -> int:
        log(f"serving board at {self.project_root}")
        for line in self.stdin:
            if not line.strip():
                continue
            self._handle_line(line)
        return 0

    def _handle_line(self, line: str) -> None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            self._send_error(None, PARSE_ERROR, f"parse error: {error}")
            return
        if isinstance(message, list):
            for item in message:
                self._dispatch(item)
            return
        self._dispatch(message)

    def _dispatch(self, message: Any) -> None:
        if not isinstance(message, dict):
            self._send_error(None, INVALID_REQUEST, "message must be a JSON object")
            return
        identifier = message.get("id")
        method = message.get("method")
        is_notification = "id" not in message

        if not isinstance(method, str):
            if is_notification:
                return  # notifications never get a response, valid or not
            self._send_error(identifier, INVALID_REQUEST, "missing 'method'")
            return
        if is_notification:
            log(f"notification: {method}")
            if method == "notifications/initialized":
                self.initialized = True
            return

        handler = self.handlers.get(method)
        if handler is None:
            self._send_error(identifier, METHOD_NOT_FOUND, f"unknown method: {method}")
            return
        params = message.get("params") or {}
        if not isinstance(params, Mapping):
            self._send_error(identifier, INVALID_PARAMS, "'params' must be an object")
            return
        try:
            self._send_result(identifier, handler(params))
        except _ToolInputError as error:
            self._send_error(identifier, INVALID_PARAMS, str(error))
        except Exception as error:  # surfaced to the client, logged locally
            log(f"{method} failed: {type(error).__name__}: {error}")
            self._send_error(
                identifier, INTERNAL_ERROR, f"{type(error).__name__}: {error}"
            )

    def _write(self, payload: Mapping[str, Any]) -> None:
        self.stdout.write(json.dumps(payload) + "\n")
        self.stdout.flush()

    def _send_result(self, identifier: Any, result: Mapping[str, Any]) -> None:
        self._write({"jsonrpc": "2.0", "id": identifier, "result": result})

    def _send_error(self, identifier: Any, code: int, message: str) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "id": identifier,
                "error": {"code": code, "message": message},
            }
        )

    # --- protocol methods --------------------------------------------------

    def _handle_initialize(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
        }

    def _handle_tools_list(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"tools": TOOL_SCHEMAS}

    def _handle_tools_call(self, params: Mapping[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            raise _ToolInputError("'name' is required")
        if not isinstance(arguments, Mapping):
            raise _ToolInputError("'arguments' must be an object")
        tool = TOOLS.get(name)
        if tool is None:
            raise _ToolInputError(f"unknown tool: {name}")
        role = core.worker_role()
        if role:  # a factory worker is held to its role on this surface too
            from kahnban import guard

            problem = guard.command_problem(role, TOOL_COMMANDS.get(name, name))
            if problem:
                return _content({"ok": False, "error": problem}, is_error=True)
        try:
            payload = tool(self.project_root, arguments)
        except (core.KahnbanError, gitops.GitError, worktree.WorktreeError) as error:
            # A refused gate is a tool-level error, not a protocol failure.
            return _content(
                {"ok": False, "error": f"{type(error).__name__}: {error}"},
                is_error=True,
            )
        return _content(payload)


class _ToolInputError(ValueError):
    """Bad tool arguments — reported as JSON-RPC ``-32602``."""


def _content(payload: Mapping[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}
        ],
        "isError": is_error,
    }


# --- tool implementations ---------------------------------------------------


def _config(project_root: Path) -> core.Config:
    return core.load_config(project_root)


def _require(arguments: Mapping[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _ToolInputError(f"'{key}' is required")
    return value.strip()


def _transition_payload(result: core.TransitionResult) -> dict[str, Any]:
    return {
        "ok": True,
        "ticket_id": result.ticket_id,
        "from_column": result.from_column,
        "to_column": result.to_column,
        "path": result.path.as_posix(),
        "commit": result.commit,
        "messages": result.messages,
    }


def tool_board_status(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    result = linter.lint(config, strict=bool(arguments.get("strict")))
    return {
        "ok": result.ok,
        "board_root": config.board_path.as_posix(),
        "column_counts": result.column_counts,
        "tickets_checked": result.tickets_checked,
        "violations": [finding.as_dict() for finding in result.violations],
        "warnings": [finding.as_dict() for finding in result.warnings],
    }


def tool_ticket_get(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    ticket = core.find_ticket(config, _require(arguments, "ticket_id"))
    text = ticket.text
    fields, body = frontmatter.parse(text)
    return {
        "ok": True,
        "ticket_id": ticket.ticket_id,
        "column": ticket.column,
        "path": ticket.path.as_posix(),
        "frontmatter": dict(fields),
        "blast_radius": core.parse_blast_radius(body),
        "body": body,
    }


def _string_list(arguments: Mapping[str, Any], key: str) -> list[str]:
    value = arguments.get(key) or []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence):
        raise _ToolInputError(f"'{key}' must be an array of strings")
    return [str(item) for item in value if str(item).strip()]


def tool_ticket_new(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    draft = core.TicketDraft(
        title=_require(arguments, "title"),
        problem=str(arguments.get("problem") or ""),
        owner=str(arguments.get("owner") or "unassigned"),
        acceptance=_string_list(arguments, "acceptance"),
        blast_radius=_string_list(arguments, "blast_radius"),
        notes=str(arguments.get("notes") or ""),
        validation=str(arguments.get("validation") or ""),
        depends_on=_string_list(arguments, "depends_on"),
        design_docs=_string_list(arguments, "design_docs"),
    )
    return _transition_payload(core.create_ticket(config, draft=draft))


def tool_plan_ingest(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    raw_path = Path(_require(arguments, "path"))
    document = raw_path if raw_path.is_absolute() else config.project_root / raw_path
    heading_level = arguments.get("heading_level")
    options = ingest.options_for(
        config,
        heading_level=int(heading_level) if heading_level else None,
        section=str(arguments["section"]) if arguments.get("section") else None,
        per_file=bool(arguments.get("per_file")),
        chain=bool(arguments.get("chain")),
        owner=str(arguments.get("owner") or "unassigned"),
        update=bool(arguments.get("update")),
        promote=bool(arguments.get("ready")),
    )
    report = ingest.ingest_document(
        config, document, options=options, dry_run=bool(arguments.get("dry_run"))
    )
    payload = report.as_dict()
    payload["ok"] = report.dry_run or not report.drifted
    payload["summary"] = ingest.render_report([report])
    return payload


def tool_capture(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    ideas = _string_list(arguments, "ideas")
    if not ideas:
        raise _ToolInputError("'ideas' must contain at least one title")
    report = ingest.capture(
        config,
        ideas,
        owner=str(arguments.get("owner") or "unassigned"),
        dry_run=bool(arguments.get("dry_run")),
    )
    payload = report.as_dict()
    payload["ok"] = True
    return payload


def tool_ticket_ready(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _transition_payload(
        core.ready(_config(project_root), _require(arguments, "ticket_id"))
    )


def tool_ticket_claim(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    create_worktree = arguments.get("create_worktree")
    result = core.claim(
        config,
        _require(arguments, "ticket_id"),
        _require(arguments, "owner"),
        create_worktree=True if create_worktree is None else bool(create_worktree),
        force=bool(arguments.get("force")),
        force_overlap=bool(arguments.get("force_overlap")),
        strict_wip=bool(arguments.get("strict_wip")),
        reason=str(arguments.get("reason") or ""),
    )
    payload = _transition_payload(result)
    payload["worktree"] = (
        config.project_root / ".worktrees" / result.ticket_id
    ).as_posix()
    return payload


def tool_ticket_verify(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    evidence = arguments.get("manual_evidence_path")
    result = core.verify(
        config,
        _require(arguments, "ticket_id"),
        manual_evidence=Path(evidence) if evidence else None,
        force_scope=bool(arguments.get("force_scope")),
        reason=str(arguments.get("reason") or ""),
    )
    payload: dict[str, Any] = {
        "ok": result.passed,
        "ticket_id": result.ticket_id,
        "passed": result.passed,
        "exit_code": result.exit_code,
        "command": result.command,
        "output": core._truncate(result.output, config.log_output_max_bytes),
        "artifact": result.artifact.as_posix() if result.artifact else None,
        "messages": result.messages,
    }
    if result.transition is not None:
        payload["transition"] = _transition_payload(result.transition)
    return payload


def tool_ticket_done(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    merge_commit = arguments.get("merge_commit")
    return _transition_payload(
        core.done(
            _config(project_root),
            _require(arguments, "ticket_id"),
            merge_commit=str(merge_commit) if merge_commit else None,
        )
    )


def tool_ticket_move(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _transition_payload(
        core.move(
            _config(project_root),
            _require(arguments, "ticket_id"),
            _require(arguments, "column"),
            reason=_require(arguments, "reason"),
        )
    )


def tool_cleanup(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _transition_payload(
        core.cleanup(
            _config(project_root),
            _require(arguments, "ticket_id"),
            abandon=bool(arguments.get("abandon")),
            reason=str(arguments.get("reason") or ""),
        )
    )


def tool_sync(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    written = core.sync(_config(project_root))
    return {"ok": True, "written": [path.as_posix() for path in written]}


def tool_session_status(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    current = session.read_session(project_root)
    inspect_live = bool(arguments.get("inspect_live", True))
    live = session.inspect_session(config) if inspect_live else {}

    return {
        "ok": True,
        "session_path": session.get_session_path(project_root).as_posix(),
        "has_active_session_file": current is not None,
        "current": {
            "last_updated": current.last_updated if current else "",
            "active_ticket": current.active_ticket if current else "",
            "active_worktree": current.active_worktree if current else "",
            "branch": current.branch if current else "",
            "agent_harness": current.agent_harness if current else "",
            "status": current.status if current else "",
            "context": current.context if current else "",
            "modified_files": current.modified_files if current else [],
            "blockers": current.blockers if current else "",
            "next_commands": current.next_commands if current else [],
        } if current else None,
        "live": live,
    }


def tool_session_update(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)

    ticket_id = arguments.get("ticket_id") or arguments.get("active_ticket")
    context = arguments.get("summary") or arguments.get("context")
    blockers = arguments.get("blockers")
    harness = arguments.get("harness") or arguments.get("agent_harness")
    status_text = arguments.get("status") or arguments.get("status_text")

    raw_next = arguments.get("next_commands") or arguments.get("next_command")
    if isinstance(raw_next, str):
        next_cmds = [raw_next] if raw_next.strip() else []
    elif isinstance(raw_next, list):
        next_cmds = [str(c) for c in raw_next]
    else:
        next_cmds = None

    raw_mods = arguments.get("modified_files")
    if isinstance(raw_mods, list):
        mods = [str(m) for m in raw_mods]
    elif arguments.get("flush_from_worktree", True) is False:
        mods = []
    else:
        mods = None

    session_update = session.SessionUpdate(
        ticket_id=str(ticket_id) if ticket_id is not None else None,
        agent_harness=str(harness) if harness is not None else None,
        status=str(status_text) if status_text is not None else None,
        context=str(context) if context is not None else None,
        blockers=str(blockers) if blockers is not None else None,
        next_commands=next_cmds,
        modified_files=mods,
    )
    state, written = session.sync_session(
        config,
        update=session_update,
    )
    return {
        "ok": True,
        "written": written.as_posix(),
        "active_ticket": state.active_ticket,
        "status": state.status,
    }


def tool_next(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    from kahnban import dispatcher
    config = _config(project_root)
    pref_role = arguments.get("role")
    rec = dispatcher.resolve_next_action(config, preferred_role=pref_role)
    return {
        "ok": True,
        "recommendation": rec.to_dict(),
    }


def tool_ticket_approve(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _transition_payload(
        core.approve(
            _config(project_root),
            _require(arguments, "ticket_id"),
            _require(arguments, "reviewer"),
            note=str(arguments.get("note") or ""),
        )
    )


def tool_ticket_reject(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    reviewer = arguments.get("reviewer") or arguments.get("author") or "qa_reviewer"
    return _transition_payload(
        core.reject(
            _config(project_root),
            _require(arguments, "ticket_id"),
            str(reviewer),
            _require(arguments, "feedback"),
        )
    )


def tool_ticket_lease(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    minutes = arguments.get("minutes")
    ticket_id = _require(arguments, "ticket_id")
    owner = _require(arguments, "owner")
    result = core.lease(
        _config(project_root), ticket_id, owner, minutes=int(minutes) if minutes else None
    )
    payload = _transition_payload(result) if result is not None else {"ok": True}
    payload.update({"ticket_id": ticket_id.upper(), "leased_by": owner})
    return payload


def tool_ticket_escalate(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _transition_payload(
        core.escalate(
            _config(project_root),
            _require(arguments, "ticket_id"),
            _require(arguments, "reason"),
        )
    )


def tool_ticket_merge(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    result = core.merge(config, _require(arguments, "ticket_id"))
    payload: dict[str, Any] = {
        "ok": result.passed,
        "ticket_id": result.ticket_id,
        "passed": result.passed,
        "exit_code": result.exit_code,
        "command": result.command,
        "output": core._truncate(result.output, config.log_output_max_bytes),
        "artifact": result.artifact.as_posix() if result.artifact else None,
        "messages": result.messages,
    }
    if result.transition is not None:
        payload["transition"] = _transition_payload(result.transition)
    return payload


TOOLS: dict[str, Callable[[Path, Mapping[str, Any]], dict[str, Any]]] = {
    "kanban_board_status": tool_board_status,
    "kanban_ticket_get": tool_ticket_get,
    "kanban_ticket_new": tool_ticket_new,
    "kanban_plan_ingest": tool_plan_ingest,
    "kanban_capture": tool_capture,
    "kanban_ticket_ready": tool_ticket_ready,
    "kanban_ticket_claim": tool_ticket_claim,
    "kanban_ticket_verify": tool_ticket_verify,
    "kanban_ticket_done": tool_ticket_done,
    "kanban_ticket_move": tool_ticket_move,
    "kanban_cleanup": tool_cleanup,
    "kanban_sync": tool_sync,
    "kanban_session_status": tool_session_status,
    "kanban_session_get": tool_session_status,
    "kanban_session_update": tool_session_update,
    "kanban_next": tool_next,
    "kanban_ticket_approve": tool_ticket_approve,
    "kanban_ticket_reject": tool_ticket_reject,
    "kanban_ticket_merge": tool_ticket_merge,
    "kanban_ticket_lease": tool_ticket_lease,
    "kanban_ticket_escalate": tool_ticket_escalate,
    "kanban_feedback": tool_ticket_reject,
}


# The CLI command each tool stands for, for the role check (see templates/roles.json).
TOOL_COMMANDS: dict[str, str] = {
    "kanban_board_status": "status",
    "kanban_ticket_get": "status",
    "kanban_ticket_new": "new",
    "kanban_plan_ingest": "ingest",
    "kanban_capture": "capture",
    "kanban_ticket_ready": "ready",
    "kanban_ticket_claim": "claim",
    "kanban_ticket_verify": "verify",
    "kanban_ticket_done": "done",
    "kanban_ticket_move": "move",
    "kanban_cleanup": "cleanup",
    "kanban_sync": "sync",
    "kanban_session_status": "session",
    "kanban_session_get": "session",
    "kanban_session_update": "session",
    "kanban_next": "next",
    "kanban_ticket_approve": "approve",
    "kanban_ticket_reject": "reject",
    "kanban_ticket_merge": "merge",
    "kanban_ticket_lease": "lease",
    "kanban_ticket_escalate": "escalate",
    "kanban_feedback": "reject",
}


def resolve_project_root(argv: Sequence[str] | None = None) -> Path:
    """``--project-root`` argv, then ``KAHNBAN_PROJECT_ROOT``, then cwd."""
    parser = argparse.ArgumentParser(prog="kahnban.mcp_server", add_help=False)
    parser.add_argument("--project-root")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    args, _ = parser.parse_known_args(argv)
    if args.show_help:
        print(__doc__ or "", file=sys.stderr)
    if args.project_root:
        return Path(args.project_root).resolve()
    from_env = os.environ.get("KAHNBAN_PROJECT_ROOT")
    if from_env:
        return Path(from_env).resolve()
    return Path.cwd().resolve()


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace", newline="\n")
            except (ValueError, OSError, TypeError):  # pragma: no cover
                pass
    return Server(resolve_project_root(argv)).serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
