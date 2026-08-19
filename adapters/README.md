# Adapters — adopting Kahnban in a repository

Layer 1 (this engine) is installed once per machine. Layer 0 (the board) and
Layer 2 (client configs) are committed per repository. Nothing in this directory
is engine code — these are the files you copy into an adopter repo.

## 1. Install the engine

```powershell
py -3 -m pip install -e C:\Github\Kahnban          # local development, editable
py -3 -m pip install git+https://<remote>/Kahnban  # pinned by tag in CI
```

Adopter repositories contain **no copied engine code**. `board.config.json`
carries `engine_min_version`; every entry point refuses to run against an older
engine and prints the upgrade command.

## 2. Scaffold the board

```powershell
cd C:\github\<adopter>
kahnban init --prefix HOA
```

This creates `plans/board.config.json`, the column tree with `.gitkeep` files,
`plans/tickets/template.md`, the `.gitignore` entries for `.worktrees/`,
`plans/tickets/.artifacts/`, and `plans/tickets/.claim.lock`, then writes the
first projections and commits everything.

Tune `plans/board.config.json` afterwards:

| Key | Purpose |
| :--- | :--- |
| `wip_limit` | Tickets allowed in `3-in-progress` (warning; `--strict-wip` to hard fail) |
| `use_worktrees` | Default for `claim` |
| `shared_caches` | Heavy dirs junctioned into each worktree, e.g. `[".godot"]` |
| `validation_command` | Fallback when a ticket has no fenced `## Validation` block |
| `validation_timeout_sec` | Kill a hung validation run (default 1800) |
| `log_output_max_bytes` | Log truncation budget; full output lands in `.artifacts/` |
| `required_headings` | Headings BL05 enforces |
| `design_doc_roots` | Where BL11 resolves `design_docs` entries |
| `extensions` | Repo-specific frontmatter fields (`enum`, `required_from`, `when`) |

## 3. Wire the agent contract and MCP clients

- Copy [AGENTS.md](AGENTS.md) into the repo's `AGENTS.md` / `CLAUDE.md` /
  `.cursorrules`.
- Register the MCP server using [MCP.md](MCP.md).

## 4. Gate the test runner on board lint

Insert at the top of `tools/run_all_tests.ps1` (or the CI workflow):

```powershell
Write-Host "=== Validating Kahnban Board ===" -ForegroundColor Cyan
& py -3 -m kahnban lint --config plans\board.config.json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Kanban board lint failed. Resolve violations before running test suites."
    exit 1
}
```

Lint exit codes: `0` clean, `1` violations, `2` configuration or I/O error.
The lint gate never invokes `verify`, so a ticket whose validation command runs
the suite cannot recurse.
