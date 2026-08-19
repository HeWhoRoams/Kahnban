# MCP Client Registration

The server speaks newline-delimited JSON-RPC 2.0 over stdio, protocol version
`2024-11-05`. It logs to stderr only, so any client that treats stdout as the
protocol channel works unmodified.

Project root resolution order: `--project-root` argument, then
`KAHNBAN_PROJECT_ROOT`, then the process working directory. MCP-launched
processes rarely inherit a useful cwd — always pass `--project-root`.

## VS Code / GitHub Copilot — `.vscode/mcp.json`

```json
{
  "servers": {
    "kahnban": {
      "type": "stdio",
      "command": "py",
      "args": ["-3", "-m", "kahnban.mcp_server", "--project-root", "${workspaceFolder}"]
    }
  }
}
```

## Claude Code

```powershell
claude mcp add kahnban -- py -3 -m kahnban.mcp_server --project-root .
```

## Cursor / Windsurf — `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "kahnban": {
      "command": "py",
      "args": ["-3", "-m", "kahnban.mcp_server", "--project-root", "."]
    }
  }
}
```

## Cline / Roo — `cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "kahnban": {
      "command": "py",
      "args": ["-3", "-m", "kahnban.mcp_server", "--project-root", "${workspaceFolder}"],
      "env": {}
    }
  }
}
```

On non-Windows hosts replace `py -3` with `python3`.

## Tool surface

| Tool | Effect | Notes |
| :--- | :--- | :--- |
| `kanban_board_status` | Column counts + lint summary | read-only |
| `kanban_ticket_get` | Column, frontmatter, blast radius, body | read-only |
| `kanban_ticket_new` | Create a ticket in the backlog | body sections accepted |
| `kanban_plan_ingest` | Turn a markdown plan into tickets | idempotent; `dry_run`, `ready` |
| `kanban_capture` | Capture rough ideas as tickets | one commit |
| `kanban_ticket_ready` | Refining -> ready, gated | |
| `kanban_ticket_claim` | Ready -> in-progress, provisions the worktree | `create_worktree` defaults to true |
| `kanban_ticket_verify` | **Runs the validation command server-side** | returns exit code + captured output |
| `kanban_ticket_done` | Verifying -> done, requires a merge | |
| `kanban_ticket_move` | Any -> any | `reason` required |
| `kanban_cleanup` | Remove junctions, worktree, branch | |
| `kanban_sync` | Regenerate STATUS.md and status.json | |

A refused gate comes back as a tool result with `isError: true` and an
explanatory `error` string — not as a JSON-RPC error — so agents can read the
refusal and react. Protocol-level errors (`-32601`, `-32602`, `-32700`) mean the
request itself was malformed.
