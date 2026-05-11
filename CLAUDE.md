# CLAUDE.md — Task Manager

This file primes Claude Code on how to work in this repository.

## What this project is

An **AI-native Task Manager**. The user drives everything through Claude Code → MCP server → REST backend → SQLite. The MCP layer is what makes this AI-native: Claude discovers tools, resources, and prompts at session start and routes natural-language requests through them.

## Architecture

```
Claude Code  ──MCP/stdio──▶  mcp-server/server.py  ──HTTPS+X-API-Key──▶  backend (FastAPI)  ─▶  SQLite
```

**Hard rule:** never call the backend HTTP API directly from Claude. Always go through MCP tools or resources. The API key lives in the MCP server's environment; Claude never sees it.

## MCP surface

### Tools (mutating or by-id)
- `add_task(title, description?, status?, priority?, due_date?, tags?)` → creates a task
- `get_task(id)` → fetch one
- `get_all_tasks(status?, priority?, tag?, due_before?, due_after?)` → filtered list
- `update_task(id, patch)` → partial update
- `delete_task(id)` → delete

### Resources (read-only — prefer these for browsing)
- `tasks://all` — everything
- `tasks://completed` — `status=done`
- `tasks://today` — open tasks due today or overdue
- `tasks://in-progress` — `status=in_progress`

Use a resource when you want a list view or want to seed reasoning with current state. Use a tool when you need a specific id or any side effect.

### Prompts (slash commands)
- `/daily-plan` — builds today's plan from `tasks://today` + `tasks://in-progress`
- `/prioritize-tasks` — re-orders open tasks by overdue → priority → due-date

## Skills (in `.claude/skills/`)
- `/git-commit` — drafts a Conventional Commits message, optionally invokes `code-reviewer`, then commits.
- `/add-test` — generates a pytest skeleton for a function or module via the `test-writer` sub-agent.

## Sub-agents (in `.claude/agents/`)
- `code-reviewer` — read-only diff review (secrets, architecture, schema parity, error handling, tests). Invoke before commits.
- `test-writer` — writes pytest files following project conventions. Invoked by `/add-test`.

## Hooks (in `hooks/`, wired in `.claude/settings.json`)
- **PreToolUse** on `Edit|Write|MultiEdit` → `hooks/precheck_secrets.py` blocks edits that would commit a real secret. Allowlist: `dev-secret-123`, `os.getenv(...)`.
- **PostToolUse** on `Edit|Write|MultiEdit` → `hooks/post_edit.ps1` runs `ruff` + `black` on the touched `.py` file and `pytest` on the affected package.

You don't have to call these — Claude Code runs them deterministically.

## Development workflow

1. Activate the venv: `./.venv/Scripts/Activate.ps1` (Windows) or `source .venv/bin/activate`.
2. Edit code. The post-edit hook formats and tests automatically; trust it.
3. After adding a new public function, run `/add-test` to create test coverage.
4. Stage with `git add` (specific paths — never `git add .`), then run `/git-commit`.
5. To smoke-test the MCP server end-to-end: `npx @modelcontextprotocol/inspector python mcp-server/server.py`.

## Conventions

- **Python**: 3.11+, type hints required on public functions.
- **Style**: `ruff` + `black` (line length 100). The post-edit hook enforces both.
- **Tests**: `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`).
- **HTTP client (MCP side)**: always `httpx.AsyncClient`. Never `requests`. Never bypass `api_client.py` — that module is the single source of the API key.
- **Validation**: all enums (`status`, `priority`) live in `backend/app/models.py`; mirror them as `Literal` types in `mcp-server/tools/tasks_crud.py`.

## How to extend

- **New tool**: add a function to `mcp-server/tools/tasks_crud.py`, decorate inside `register(mcp)`. Add the matching backend endpoint in `backend/app/routers/tasks.py` if needed. Write tests in both packages.
- **New resource**: add a coroutine to `mcp-server/resources/task_resources.py`, register it inside `register(mcp)` with a `tasks://...` URI. **Resources may only call `api_get`.**
- **New prompt**: drop a file in `mcp-server/prompts/`, expose `register(mcp)`, wire it from `mcp-server/server.py`.
- **New skill / agent**: Markdown file in `.claude/skills/` or `.claude/agents/` with frontmatter (`name`, `description`, optionally `tools`).

## Do-not list

- ❌ Don't bypass MCP from inside Claude (no direct HTTP calls).
- ❌ Don't hardcode the API key. `os.getenv("API_KEY", "dev-secret-123")` is the only acceptable form.
- ❌ Don't commit `.env` (already in `.gitignore`).
- ❌ Don't add a mutating tool whose `register` path lives under `resources/`.
- ❌ Don't disable hooks (`--no-verify`, removing entries from `.claude/settings.json`) without explicit user approval.
