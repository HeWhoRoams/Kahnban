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

from kahnban import __version__, core, frontmatter, gitops, linter, worktree

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
        "description": "Create a ticket in the backlog column.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": _string("One-line outcome statement."),
                "problem": _string("Optional problem statement for the body."),
                "owner": _string("Optional owner; defaults to unassigned."),
            },
            "required": ["title"],
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


def tool_ticket_new(project_root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    config = _config(project_root)
    result = core.create_ticket(
        config,
        _require(arguments, "title"),
        problem=arguments.get("problem"),
        owner=str(arguments.get("owner") or "unassigned"),
    )
    return _transition_payload(result)


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


TOOLS: dict[str, Callable[[Path, Mapping[str, Any]], dict[str, Any]]] = {
    "kanban_board_status": tool_board_status,
    "kanban_ticket_get": tool_ticket_get,
    "kanban_ticket_new": tool_ticket_new,
    "kanban_ticket_ready": tool_ticket_ready,
    "kanban_ticket_claim": tool_ticket_claim,
    "kanban_ticket_verify": tool_ticket_verify,
    "kanban_ticket_done": tool_ticket_done,
    "kanban_ticket_move": tool_ticket_move,
    "kanban_cleanup": tool_cleanup,
    "kanban_sync": tool_sync,
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
