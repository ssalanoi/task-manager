# Task Manager — Complete Knowledge Base

> This document is a self-contained reference for the AI-native Task Manager project. It is designed to be uploaded to NotebookLM (or similar tools) and used as a single source of truth for questions about architecture, code organization, design decisions, workflows, and troubleshooting.

---

## Table of Contents

1. [Project Identity and Goal](#1-project-identity-and-goal)
2. [Glossary](#2-glossary)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Repository Layout](#4-repository-layout)
5. [Backend Layer (FastAPI + SQLModel + SQLite)](#5-backend-layer)
6. [MCP Server Layer (FastMCP)](#6-mcp-server-layer)
7. [Claude Code Integration (.claude directory)](#7-claude-code-integration)
8. [Hooks Layer (Deterministic Safety Net)](#8-hooks-layer)
9. [Data Flow Walkthroughs](#9-data-flow-walkthroughs)
10. [Configuration and Environment Variables](#10-configuration-and-environment-variables)
11. [Testing Strategy](#11-testing-strategy)
12. [Development Workflow](#12-development-workflow)
13. [Design Principles and Hard Rules](#13-design-principles-and-hard-rules)
14. [Extension Guide](#14-extension-guide)
15. [Troubleshooting](#15-troubleshooting)
16. [Frequently Asked Questions](#16-frequently-asked-questions)

---

## 1. Project Identity and Goal

**Name:** Task Manager (AI-native, MCP-based)

**One-line description:** A personal task manager driven entirely through natural language in Claude Code, with every operation flowing through a Model Context Protocol (MCP) server that wraps a typed REST backend.

**Primary user persona:** A developer who wants to manage tasks without leaving the terminal, using Claude as the interface. The user types things like "add a task to write the weekly report by Friday" and the system handles the rest.

**Why this project exists:** It is a reference implementation showing how to build an AI-native application — where the LLM is the primary user-facing interface, but the underlying business logic, validation, and persistence are not entrusted to the model. It demonstrates the MCP pattern, Claude Code skills/sub-agents/hooks, and a layered safety model.

**What it is NOT:** It is not a multi-user product, not a SaaS, not optimized for high throughput. SQLite is used for simplicity. There is no UI other than Claude Code and the FastAPI Swagger UI.

---

## 2. Glossary

| Term | Definition |
|---|---|
| **MCP** | Model Context Protocol. An open standard for connecting LLM hosts (Claude, Claude Code, Claude Desktop) to external tool servers. |
| **MCP server** | A process that exposes tools, resources, and prompts over stdio (JSON-RPC). In this project, `mcp-server/server.py`. |
| **FastMCP** | The Python SDK for building MCP servers (`pip install mcp`). Provides decorators `@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()`. |
| **Tool** | An MCP-exposed callable function that can have side effects (mutations) or perform by-id lookups. Tools have JSON schemas. |
| **Resource** | An MCP-exposed read-only URI (e.g. `tasks://overdue`) that returns data. Resources must never mutate state. |
| **Prompt** | An MCP-exposed text template that instructs Claude how to perform a task. Surfaced as `/<name>` slash command. |
| **Claude Code** | Anthropic's CLI/IDE coding assistant. Acts as the MCP host in this project. |
| **Skill** | A markdown file in `.claude/skills/` that defines a procedural workflow Claude can invoke as a slash command. |
| **Sub-agent** | A specialized Claude instance with a restricted tool set, defined in `.claude/agents/`, invoked via the Agent tool. |
| **Hook** | An external script run by Claude Code before or after specific tool calls (PreToolUse, PostToolUse). |
| **Conventional Commits** | A commit message format: `type(scope): subject`. Used throughout this repo. |
| **stdio transport** | The MCP transport where the server runs as a subprocess of the host and communicates via stdin/stdout. |
| **ApiError** | The exception type raised by the MCP `api_client.py` module on any non-2xx HTTP response. |
| **X-API-Key** | The HTTP header used to authenticate every call to the backend. Default dev value: `dev-secret-123`. |

---

## 3. High-Level Architecture

### Topology

```
┌──────────────┐  MCP/stdio   ┌────────────────┐  HTTPS+X-API-Key  ┌─────────────┐  SQL    ┌──────────┐
│ Claude Code  │ ───────────▶ │  MCP server    │ ─────────────────▶│  FastAPI    │ ──────▶ │ SQLite   │
│ (LLM host)   │              │  (FastMCP)     │                   │  backend    │         │ tasks.db │
└──────────────┘              └────────────────┘                   └─────────────┘         └──────────┘
   discovers                      6 tools                              REST CRUD              Tasks
   tools/resources/prompts        6 resources                                                  table
   at session start               3 prompts
```

### The Four Layers and Their Responsibilities

| Layer | Responsibility | Knows about |
|---|---|---|
| **Claude Code (LLM host)** | Natural-language parsing, decides which tool/resource to call | MCP tool schemas only |
| **MCP server** | Tool/resource/prompt registration, input validation, HTTP injection | API key, backend URL, tool schemas |
| **FastAPI backend** | REST CRUD, authentication, business validation, persistence | Database schema, validation rules |
| **SQLite** | Storage | Nothing about the rest |

### Why MCP Instead of Direct HTTP from Claude

1. **Secret hygiene:** The API key lives in the MCP server's environment. Claude never sees it. If Claude were prompt-injected, an attacker could not exfiltrate the key from the conversation context.
2. **Type safety at the LLM boundary:** Tools have JSON schemas, so Claude cannot call `add_task(priority="critical")` — the schema only allows `low|medium|high|urgent`.
3. **Automatic capability discovery:** When a session starts, Claude Code asks the MCP server for its tools/resources/prompts. The user does not need to teach Claude what is available.
4. **Portability:** The same MCP server runs in Claude Desktop, MCP Inspector, or any other MCP-compatible host. There is no Claude Code-specific code in `mcp-server/`.
5. **Defense in depth:** Resources are physically restricted to `api_get`-only (architectural rule, enforced by code review). This means a malformed prompt can never cause data mutation while the model is "just browsing."

### Communication Protocols

- **Claude Code ↔ MCP server:** JSON-RPC over stdio. The host starts the server as a subprocess and writes/reads on its stdin/stdout pipes.
- **MCP server ↔ backend:** HTTP/HTTPS using `httpx.AsyncClient`. Every request carries the `X-API-Key` header.
- **Backend ↔ SQLite:** SQLModel/SQLAlchemy ORM. Default file `./tasks.db`, overridable via `DATABASE_URL` env var.

---

## 4. Repository Layout

```
task-manager/
├── backend/                         # FastAPI + SQLModel + SQLite
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app, lifespan, /health
│   │   ├── models.py                # SQLModel Task + Status/Priority enums
│   │   ├── schemas.py               # Pydantic TaskCreate/Update/Read with validators
│   │   ├── db.py                    # engine, get_session, init_db
│   │   ├── auth.py                  # require_api_key dependency
│   │   └── routers/
│   │       └── tasks.py             # POST/GET/PUT/DELETE /tasks
│   └── tests/
│       ├── conftest.py              # StaticPool in-memory SQLite, dependency overrides
│       └── test_tasks_api.py        # 11 tests: 401, 422, 404, CRUD, filters
├── mcp-server/                      # FastMCP server
│   ├── server.py                    # entrypoint (stdio transport)
│   ├── api_client.py                # httpx.AsyncClient, X-API-Key injection, ApiError
│   ├── tools/
│   │   ├── __init__.py
│   │   └── tasks_crud.py            # 6 tools: add/get/update/delete/list/stats
│   ├── resources/
│   │   ├── __init__.py
│   │   └── task_resources.py        # 6 read-only URIs
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── daily_plan.py            # /daily-plan
│   │   ├── prioritize_tasks.py      # /prioritize-tasks
│   │   └── weekly_review.py         # /weekly-review
│   └── tests/
│       ├── test_tools.py
│       ├── test_tasks_crud.py       # 9 tests for add_task + get_task_stats
│       └── test_task_resources.py   # 8 tests for resources
├── .claude/                         # Claude Code project configuration
│   ├── settings.json                # Hook registration
│   ├── skills/
│   │   ├── git-commit.md            # /git-commit workflow
│   │   └── add-test.md              # /add-test workflow
│   ├── agents/
│   │   ├── code-reviewer.md         # Read-only diff reviewer
│   │   ├── test-writer.md           # Pytest generator
│   │   └── task-planner.md          # Backlog triage agent
│   └── commands/
│       ├── daily-plan.md            # Mirror of MCP prompt (for IDE plugin)
│       ├── prioritize-tasks.md
│       └── weekly-review.md
├── hooks/
│   ├── precheck_secrets.py          # PreToolUse — scan for hard-coded secrets
│   ├── post_edit.ps1                # PostToolUse (Windows) — ruff + black + pytest
│   └── post_edit.sh                 # PostToolUse (POSIX)
├── docs/
│   └── images/                      # Screenshots embedded in README
├── run_mcp.bat                      # Windows wrapper with full venv path
├── CLAUDE.md                        # Project conventions for Claude
├── README.md                        # Setup and usage
├── TESTING.md                       # End-to-end verification checklist
└── PROJECT_KNOWLEDGE_BASE.md        # This file
```

---

## 5. Backend Layer

**Stack:** Python 3.11+, FastAPI, SQLModel (Pydantic + SQLAlchemy), SQLite, Pydantic v2, uvicorn.

### 5.1 Entry Point — `backend/app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db import init_db
from .routers import tasks

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()           # SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(title="Task Manager API", version="0.1.0", lifespan=lifespan)

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}

app.include_router(tasks.router)
```

**Design notes:**
- Migrated from deprecated `@app.on_event("startup")` to `lifespan` async context manager (Pydantic v2 / FastAPI best practice).
- `/health` is intentionally unauthenticated for liveness checks.
- The `tasks` router carries the auth dependency, so all `/tasks/*` paths are protected automatically.

### 5.2 Database — `backend/app/db.py`

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)
```

- `check_same_thread=False` is required for SQLite + FastAPI threadpool.
- Default file `./tasks.db` is created on first start.
- Tests override the engine to use an in-memory SQLite via `StaticPool` (see Testing section).

### 5.3 Models — `backend/app/models.py`

Two enums plus one table.

```python
class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"

class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: TaskStatus = Field(default=TaskStatus.todo, index=True)
    priority: TaskPriority = Field(default=TaskPriority.medium, index=True)
    due_date: Optional[str] = Field(default=None, index=True)   # ISO YYYY-MM-DD as string
    tags_csv: str = Field(default="")                            # "tag1,tag2,tag3"
    created_at: datetime
    updated_at: datetime
```

**Design notes:**
- `due_date` is stored as an ISO string, not a `date` type, to keep SQLite portable and avoid timezone confusion in queries.
- Tags are stored as a single comma-separated string (`tags_csv`) to avoid a join table. The router converts to/from list on the wire.
- `created_at` and `updated_at` default to `datetime.now(timezone.utc)`.

### 5.4 Schemas — `backend/app/schemas.py`

Three Pydantic v2 models with field validators.

**`TaskCreate`** (used on POST):
- `title`: stripped, must not be empty after stripping
- `tags`: normalized to lowercase, deduplicated, max 10 tags × 32 chars each
- `due_date`: must parse as ISO date, **must be today or in the future** (POST only)

**`TaskUpdate`** (used on PUT):
- All fields optional
- `title`: same strip rule
- `tags`: same normalization
- `due_date`: parses as ISO date, **past dates allowed** (so you can log overdue work)

**`TaskRead`** (used on response):
- Returns tags as a list of strings (not CSV)
- Includes `created_at` and `updated_at`

**Why POST forbids past dates but PUT allows them:** A new task should always be in the future (otherwise why are you creating it?), but you may need to PUT an overdue task to record reality.

### 5.5 Authentication — `backend/app/auth.py`

```python
API_KEY_HEADER = "X-API-Key"

def require_api_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    expected = os.getenv("API_KEY", "dev-secret-123")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Missing or invalid API key")
```

- `secrets.compare_digest` is timing-safe (constant-time comparison).
- Single shared dev value `dev-secret-123` is on the allowlist of the secret-detection hook, so it can appear in code without being blocked.
- The router applies this as a `Depends` at the router level, protecting every endpoint inside `/tasks/*`.

### 5.6 Router — `backend/app/routers/tasks.py`

```python
router = APIRouter(prefix="/tasks", tags=["tasks"],
                   dependencies=[Depends(require_api_key)])
```

Endpoints:

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/tasks` | `TaskCreate` | `TaskRead` (201) |
| GET | `/tasks` | — query params | `List[TaskRead]` |
| GET | `/tasks/{id}` | — | `TaskRead` or 404 |
| PUT | `/tasks/{id}` | `TaskUpdate` (partial) | `TaskRead` |
| DELETE | `/tasks/{id}` | — | `{"deleted": true, "id": int}` |

**GET filters:**
- `status` — exact enum match
- `priority` — exact enum match
- `tag` — exact match against normalized tags (post-SQL Python filter, since tags are stored as CSV)
- `due_before` — `due_date < value` AND not null
- `due_after` — `due_date > value` AND not null

**Tag handling:** stored as CSV in `tags_csv`, exposed as `List[str]` in `TaskRead`. The `_to_read` and `_tags_to_csv` helpers do the conversion.

### 5.7 Backend Tests — `backend/tests/test_tasks_api.py` (11 tests)

Covers:
- 401 when API key missing
- 422 when title empty / due_date in past on POST
- CRUD happy paths
- 404 on get/update/delete missing id
- All filter combinations

**Critical conftest detail:**

```python
# backend/tests/conftest.py overrides the engine BEFORE app import
from sqlalchemy.pool import StaticPool
engine = create_engine("sqlite:///:memory:",
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
```

`StaticPool` makes every connection reuse the same in-memory database. Without it, `sqlite:///:memory:` creates a fresh DB per connection, and the test fails with "no such table: task" because the table was created on a different connection.

---

## 6. MCP Server Layer

**Stack:** Python 3.11+, FastMCP (`pip install mcp`), httpx, Pydantic v2.

### 6.1 Entry Point — `mcp-server/server.py`

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server.fastmcp import FastMCP
from prompts import daily_plan, prioritize_tasks, weekly_review
from resources import task_resources
from tools import tasks_crud

mcp = FastMCP(
    name="task-manager",
    instructions="Task Manager MCP. Use tools (add_task / update_task / ...)"
)

tasks_crud.register(mcp)
task_resources.register(mcp)
daily_plan.register(mcp)
prioritize_tasks.register(mcp)
weekly_review.register(mcp)

mcp.run(transport="stdio")
```

**Design notes:**
- The `sys.path.insert` trick lets the script run directly (`python mcp-server/server.py`) instead of as an installed package.
- Each submodule exposes a `register(mcp)` function instead of decorating a module-level FastMCP. This is dependency injection — it means tests can create their own `FastMCP(name="test")` and register only the parts under test.
- `instructions` is shown to Claude at session start as a usage hint.

### 6.2 HTTP Client — `mcp-server/api_client.py`

```python
class ApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"API {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail

async def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{os.getenv('API_BASE_URL', 'http://localhost:8000').rstrip('/')}{path}"
    headers = {"X-API-Key": os.getenv("API_KEY", "dev-secret-123"),
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.request(method, url, headers=headers, **kwargs)
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, resp.json().get("detail", resp.text))
    return resp.json() if resp.content else None

async def api_get(path, params=None):  ...
async def api_post(path, json_body):   ...
async def api_put(path, json_body):    ...
async def api_delete(path):            ...
```

**Hard architectural rule:** This is the **only** module in `mcp-server/` that imports `httpx`. Every tool and resource calls one of `api_get / api_post / api_put / api_delete`. The `code-reviewer` sub-agent verifies this on every commit. The reason: a single point where the API key is injected and a single place where HTTP errors are translated to `ApiError`.

### 6.3 Tools — `mcp-server/tools/tasks_crud.py`

Six tools, all async. They map 1:1 to backend endpoints except `get_task_stats`, which is computed client-side.

```python
Status = Literal["todo", "in_progress", "done"]
Priority = Literal["low", "medium", "high", "urgent"]

class _AddTaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Status = "todo"
    priority: Priority = "medium"
    due_date: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

def register(mcp: Any) -> None:
    @mcp.tool()
    async def get_task(id: int) -> dict: ...

    @mcp.tool()
    async def get_all_tasks(status=None, priority=None, tag=None,
                            due_before=None, due_after=None) -> dict: ...

    @mcp.tool()
    async def add_task(title, description=None, status="todo", priority="medium",
                       due_date=None, tags=None) -> dict:
        payload = _AddTaskInput(...).model_dump()
        return await api_post("/tasks", payload)

    @mcp.tool()
    async def update_task(id: int, patch: dict) -> dict: ...

    @mcp.tool()
    async def delete_task(id: int) -> dict: ...

    @mcp.tool()
    async def get_task_stats() -> dict:
        """Aggregate: total, by_status, by_priority, overdue."""
        all_tasks = await api_get("/tasks")
        today = date.today().isoformat()
        by_status = {"todo": 0, "in_progress": 0, "done": 0}
        by_priority = {"low": 0, "medium": 0, "high": 0, "urgent": 0}
        overdue = 0
        for t in all_tasks:
            by_status[t["status"]] += 1
            by_priority[t["priority"]] += 1
            if t.get("due_date") and t["due_date"] < today and t["status"] != "done":
                overdue += 1
        return {"total": len(all_tasks), "by_status": by_status,
                "by_priority": by_priority, "overdue": overdue}
```

**Two layers of validation:**
1. FastMCP auto-generates a JSON schema from the type hints (`Literal["low",...]`). Claude cannot send invalid values.
2. The private `_AddTaskInput` / `_UpdatePatch` Pydantic models validate again before HTTP. This catches Claude bypassing the schema (rare but possible if Claude crafts a custom JSON).

Then the backend validates a **third** time via its own Pydantic schemas.

**Tool listing (full signatures):**

| Tool | Signature | Backend call | Notes |
|---|---|---|---|
| `get_task` | `(id: int) -> dict` | GET /tasks/{id} | Single fetch |
| `get_all_tasks` | `(status?, priority?, tag?, due_before?, due_after?) -> dict` | GET /tasks | Returns `{"tasks": [...]}` |
| `add_task` | `(title, description?, status?, priority?, due_date?, tags?) -> dict` | POST /tasks | due_date must be today or future |
| `update_task` | `(id: int, patch: dict) -> dict` | PUT /tasks/{id} | Partial update |
| `delete_task` | `(id: int) -> dict` | DELETE /tasks/{id} | Returns `{"deleted": true, "id": id}` |
| `get_task_stats` | `() -> dict` | GET /tasks (then in-memory) | `{total, by_status, by_priority, overdue}` |

### 6.4 Resources — `mcp-server/resources/task_resources.py`

Six read-only resources. Each returns a JSON string when read.

```python
@mcp.resource("tasks://overdue", mime_type="application/json")
async def overdue_tasks() -> str:
    today = date.today().isoformat()
    rows = await api_get("/tasks", params={"due_before": today})
    open_rows = [r for r in rows
                 if r.get("status") != "done" and r.get("due_date") is not None]
    return json.dumps(open_rows, ensure_ascii=False, indent=2)
```

| URI | Content |
|---|---|
| `tasks://all` | All tasks |
| `tasks://completed` | `status=done` |
| `tasks://today` | `due_date <= today` AND `status != done` AND `due_date IS NOT NULL` |
| `tasks://in-progress` | `status=in_progress` |
| `tasks://overdue` | `due_date < today` AND `status != done` AND `due_date IS NOT NULL` |
| `tasks://high-priority` | `priority IN (urgent, high)` AND `status != done`, sorted urgent-first then by due_date |

**Hard architectural rule:** Resources call **only** `api_get`. They never invoke `api_post`/`put`/`delete`. The `code-reviewer` agent enforces this. This means a misbehaving prompt cannot mutate state while "browsing."

### 6.5 Prompts — `mcp-server/prompts/*.py`

Three prompts, each is just a long markdown template returned by a function.

| Prompt | Reads | Output |
|---|---|---|
| `daily-plan` | `tasks://today`, `tasks://in-progress` | Markdown plan: Must do / In progress / Stretch + Focus paragraph |
| `prioritize-tasks` | `tasks://all` | Ranked table + Rationale + Suggested deferrals |
| `weekly-review` | `tasks://completed`, `tasks://in-progress`, `tasks://overdue`, `tasks://all` | Four sections: Completed / In progress / Overdue / Recommended focus + Retrospective |

Pattern (all three are identical structurally):

```python
PROMPT_TEMPLATE = """\
You are an assistant helping the user plan their day.
Use the MCP **resources** (not tools) to read current task state:
  1. Read resource `tasks://today`
  2. ...
Then produce a markdown plan with these sections: ...
Do NOT call mutating tools.
"""

def register(mcp):
    @mcp.prompt(name="daily-plan", description="...")
    def daily_plan() -> str:
        return PROMPT_TEMPLATE
```

The prompt itself does not call anything. It is a template injected into the conversation. Claude reads it and follows the instructions, calling resources/tools as the prompt directs. The prompt always tells Claude to use **resources**, not tools, so it can never accidentally mutate state.

### 6.6 MCP Server Tests

- **`test_tools.py`** — broad smoke tests using an in-process FastMCP instance.
- **`test_tasks_crud.py`** — 9 tests for `add_task` (happy path, defaults, tags normalization, validation errors) and `get_task_stats` (mixed counts, empty list, no due dates, ApiError propagation).
- **`test_task_resources.py`** — 8 tests for `_overdue` and `_high_priority` (exclusion of done tasks, no due_date filtering, sort order, deduplication, ApiError propagation).

**Test pattern:**
```python
@pytest.fixture()
def server() -> FastMCP:
    mcp = FastMCP(name="test")
    tasks_crud.register(mcp)
    return mcp

async def test_happy_path(server):
    with patch("tools.tasks_crud.api_post", new=AsyncMock(return_value={"id": 42})):
        await server.call_tool("add_task", {"title": "Write report"})
        # assertions on the captured call
```

For resources, the private async functions are called directly:
```python
with patch("resources.task_resources.api_get", new=AsyncMock(return_value=tasks)):
    result = await _overdue()
```

`pytest-asyncio` is set to `asyncio_mode = "auto"` in `pyproject.toml`, so no `@pytest.mark.asyncio` decorator is needed.

---

## 7. Claude Code Integration

The `.claude/` directory configures Claude Code for this project. **None of these files are seen by the MCP server, the backend, or the Inspector** — they only exist for Claude Code.

### 7.1 Skills vs Commands vs Prompts vs Agents — The Critical Distinction

These four concepts overlap in surface (all look like slash commands or named workflows) but are very different.

| Concept | Lives in | Visibility | Who executes | Example |
|---|---|---|---|---|
| **MCP Prompt** | `mcp-server/prompts/*.py` | Main Claude Code CLI as `/mcp__task-manager__daily-plan` (not visible in IDE) | Claude follows the template | `/daily-plan` |
| **Project Command** | `.claude/commands/*.md` | Everywhere (CLI + IDE) as `/<name>` | Claude follows the markdown body | `/daily-plan` |
| **Skill** | `.claude/skills/*.md` | Everywhere as `/<name>` | Claude follows a step-by-step procedure | `/git-commit` |
| **Sub-agent** | `.claude/agents/*.md` | Invoked via Agent tool, not as slash command | A separate Claude instance with restricted tools | `code-reviewer` |

**Why duplicate MCP prompts as project commands?** The Claude Code IDE extension (VS Code, JetBrains) does not surface MCP prompts as slash commands. So each MCP prompt (`/daily-plan`, `/prioritize-tasks`, `/weekly-review`) is mirrored as a `.claude/commands/*.md` file with the same body. The result: `/daily-plan` works in the CLI AND the IDE.

### 7.2 Skills — `.claude/skills/`

Skills are **markdown files with frontmatter** that define a procedural workflow Claude executes when the user types the slash command.

**`/git-commit`** (`git-commit.md`):
1. Run `git diff --cached --stat` and `git diff --cached`. If nothing staged, ask the user and stop.
2. Run `git status --short` to confirm no unexpected unstaged changes.
3. (Optional) Delegate to the `code-reviewer` sub-agent. If it blocks, surface and stop.
4. Draft a Conventional Commits message: `type(scope): subject`. Types: `feat|fix|docs|refactor|test|chore|perf|build|ci`. Subject ≤72 chars, imperative mood.
5. Show the message and ask the user to confirm.
6. On confirm: `git commit -m "<subject>" -m "<body>"`. Never `--no-verify`, never `--amend` unless explicit.
7. Run `git log -1 --oneline` and report.

**`/add-test`** (`add-test.md`):
1. Parse the argument (`path/to/file.py::function_name` or `path/to/file.py`).
2. Read the target file. Identify public callables, signatures, async/sync, external deps.
3. Decide test file path (`backend/tests/` or `mcp-server/tests/`).
4. Delegate to the `test-writer` sub-agent with target path, test file path, and conventions.
5. Run `pytest -q <test_file>` and report.

Skills are **instructions to Claude itself**, not executable scripts. Claude reads the markdown body and follows it step by step.

### 7.3 Sub-Agents — `.claude/agents/`

A sub-agent is a separate Claude instance, spawned via the Agent tool, with:
- Its own conversation context (isolated from the main one)
- A restricted tool list specified in frontmatter
- A specific role described in the markdown body

**`code-reviewer`** (read-only):
- **Tools:** Read, Grep, Glob, Bash
- **No Write/Edit/MultiEdit** — physically cannot modify files
- **Checks:** Secret hygiene, architectural rule (HTTP only via `api_client`), schema parity, error handling, validators, test coverage, style
- **Output format:** `Verdict: APPROVE|REQUEST_CHANGES|BLOCK` + bulleted findings citing `file:line`

**`test-writer`** (can write):
- **Tools:** Read, Write, Edit, Bash, Grep, Glob
- **Generates:** pytest files following project conventions (`pytest-asyncio`, FastAPI `TestClient`, in-process FastMCP harness, `AsyncMock`)
- **Coverage per target:** happy path + edge case + error path

**`task-planner`** (MCP-aware):
- **Tools:** `get_all_tasks`, `get_task`, `get_task_stats` (MCP tools only — no file access)
- **Output:** A markdown execution plan with four buckets (Critical / Urgent / High-value / Backlog), blocker detection, suggested breakdowns

**Why sub-agents instead of just having the main Claude do it?**
- **Tool isolation:** `code-reviewer` literally cannot fix code surreptitiously because it has no write tools.
- **Context isolation:** A long review pass does not pollute the main conversation context.
- **Specialization:** Each sub-agent has a focused system prompt for its task.

### 7.4 Project Commands — `.claude/commands/`

Plain markdown files with a small frontmatter (`description:`). Body is the prompt body. Identical content to the corresponding MCP prompts, just packaged for IDE-level discoverability.

Three files:
- `daily-plan.md`
- `prioritize-tasks.md`
- `weekly-review.md`

### 7.5 settings.json

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "hooks": {
    "PreToolUse":  [{ "matcher": "Edit|Write|MultiEdit",
                      "hooks": [{ "type": "command",
                                  "command": "python hooks/precheck_secrets.py" }]}],
    "PostToolUse": [{ "matcher": "Edit|Write|MultiEdit",
                      "hooks": [{ "type": "command",
                                  "command": "powershell -NoProfile -ExecutionPolicy Bypass -File hooks/post_edit.ps1" }]}]
  }
}
```

This wires the two shell scripts in `hooks/` into Claude Code's lifecycle.

---

## 8. Hooks Layer

**Hooks are external scripts** that Claude Code runs before or after tool calls. They are NOT executed by Claude — Claude Code launches them and reads their exit code.

### 8.1 Why Hooks

Skills depend on the model remembering to do something. Hooks **physically enforce** behavior — they run every time regardless of what Claude does. If a hook exits with code 2, Claude Code blocks the tool call and shows the hook's stderr to Claude.

### 8.2 PreToolUse — `hooks/precheck_secrets.py`

Runs **before** any `Edit | Write | MultiEdit`. Reads the JSON payload from stdin (Claude Code provides it), extracts `tool_input.new_string`, `tool_input.content`, and any `edits[].new_string` for MultiEdit. Scans line-by-line for known secret patterns:

```python
PATTERNS = [
    ("api-key",     r"""(?i)\bapi[_-]?key\b\s*[:=]\s*["'][A-Za-z0-9_\-]{8,}["']"""),
    ("aws",         r"\bAKIA[0-9A-Z]{16}\b"),
    ("private-key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("bearer",      r"\bBearer\s+[A-Za-z0-9._\-]{20,}"),
    ("github-pat",  r"\bghp_[A-Za-z0-9]{30,}\b"),
    ("slack",       r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"),
]

ALLOWLIST_VALUES = {"dev-secret-123", "test-key-xyz"}

def _line_is_allowlisted(line):
    if any(token in line for token in ALLOWLIST_VALUES): return True
    if "os.getenv(" in line or "os.environ" in line: return True
    return False
```

**Exit codes:**
- `0` — no hits or allowlisted, proceed
- `2` — hit found, BLOCK the edit (prints `BLOCKED: potential secret detected. Use os.getenv(...) instead.` + offending line)

**Allowlist logic:**
- Any line containing `dev-secret-123` is allowed (the canonical dev value).
- Any line containing `os.getenv(` or `os.environ` is allowed (config plumbing).
- So `key = os.getenv("API_KEY", "dev-secret-123")` passes both checks.

### 8.3 PostToolUse — `hooks/post_edit.ps1` and `post_edit.sh`

Runs **after** any successful `Edit | Write | MultiEdit`. Two parallel implementations: PowerShell for Windows, Bash for POSIX. Both do the same thing:

1. Read the JSON payload from stdin.
2. Skip if the file is not `*.py`.
3. `cd` to repo root.
4. If `ruff` is on PATH: `ruff check --fix <file>`. Set `failed` flag on non-zero exit.
5. If `black` is on PATH: `black -q <file>`. Same.
6. If `pytest` is on PATH: pick the test root by source path (`backend/tests` or `mcp-server/tests`). Run `pytest -q <root>`. Same.
7. Exit `2` if any step failed, otherwise `0`.

**Effect:** Every Python edit triggers automatic linting, formatting, and tests for the affected package. Claude sees the output and is expected to fix any failure before continuing.

**Why this matters:** Without this hook, Claude might "forget" to run tests or format code. With it, the discipline is automatic and deterministic — it cannot be bypassed unless the user disables the hook.

---

## 9. Data Flow Walkthroughs

### 9.1 "Add a task" — User Says "Add a task to write the weekly report by Friday, high priority"

```
1. User types the sentence in Claude Code.
2. Claude (LLM) parses intent:
       title="write the weekly report"
       priority="high"
       due_date="2026-05-15" (next Friday)
3. Claude calls tool: mcp__task-manager__add_task(title, priority, due_date)
4. Claude Code sends JSON-RPC over stdio to the MCP server process.
5. MCP server (server.py) routes to the @mcp.tool() function add_task.
6. add_task constructs _AddTaskInput(...).model_dump() — Pydantic validates.
7. await api_post("/tasks", payload):
       - Builds URL: http://localhost:8000/tasks
       - Injects header: X-API-Key: dev-secret-123 (from env)
       - httpx.AsyncClient sends POST
8. FastAPI receives the request:
       - require_api_key checks header → OK
       - TaskCreate parses body, runs validators → due_date >= today OK, title stripped, tags normalized
       - create_task in router: new Task(...) → session.add → commit → refresh
       - _to_read(task) converts tags_csv "" to []
       - Returns TaskRead with status 201
9. httpx receives 201 + JSON body.
10. api_client returns parsed dict to add_task.
11. add_task returns dict to FastMCP.
12. FastMCP sends JSON-RPC response back over stdio.
13. Claude Code surfaces the result to Claude.
14. Claude composes the reply: "Created task #42, due 2026-05-15."
```

### 9.2 "What should I do today?" — User Says "What should I focus on today?"

```
1. Claude decides this is a /daily-plan invocation.
2. Claude reads MCP resource tasks://today.
3. MCP server's today_tasks() async function fires:
       - Computes tomorrow as ISO string
       - api_get("/tasks", params={"due_before": tomorrow})
       - Backend returns all tasks with due_date < tomorrow
       - Python post-filter excludes status=done and due_date=None
       - Returns JSON string
4. Claude reads tasks://in-progress similarly.
5. Claude follows the daily-plan template:
       - Sorts by priority
       - Groups: Must do today / In progress / Stretch
       - Writes Focus paragraph
6. Returns markdown to the user.
```

No mutations happened. No tools were called. Only resources.

### 9.3 "Commit my work" — User Runs /git-commit

```
1. Claude reads the skill file .claude/skills/git-commit.md.
2. Bash: git diff --cached --stat, git diff --cached, git status --short.
3. Claude analyzes the diff.
4. Claude invokes Agent tool with subagent_type=code-reviewer + the diff context.
5. code-reviewer agent (separate Claude with Read/Grep/Glob/Bash only):
       - Reads relevant files
       - Checks 7 categories (secrets, arch, schema parity, errors, validation, tests, style)
       - Returns verdict + findings
6. Main Claude surfaces the review.
7. If APPROVED or REQUEST_CHANGES non-blocking: drafts commit message
       feat(mcp): get_task_stats, 2 resources, weekly-review, task-planner

       - body line 1
       - body line 2

       Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
8. Asks user to confirm.
9. On "yes": git commit -m "..." (with HEREDOC for multi-line).
10. git log -1 --oneline confirms.
```

---

## 10. Configuration and Environment Variables

| Variable | Default | Used by | Purpose |
|---|---|---|---|
| `API_KEY` | `dev-secret-123` | Backend (auth.py), MCP (api_client.py) | Shared secret on `X-API-Key` header. **Must match on both sides.** |
| `API_BASE_URL` | `http://localhost:8000` | MCP (api_client.py) | Where the MCP server sends HTTP. |
| `DATABASE_URL` | `sqlite:///./tasks.db` | Backend (db.py) | Database connection string. Any SQLAlchemy URL works. |
| `MCP_TRANSPORT` | `stdio` | MCP (server.py) | Transport type. Only `stdio` is wired today. |

**Where they're set:**
- Backend terminal: `$env:API_KEY = "dev-secret-123"` then `uvicorn ...`
- MCP terminal: same `API_KEY` plus `$env:API_BASE_URL = "http://localhost:8000"` then `python mcp-server/server.py`
- `claude mcp add` command: passes both as `--env KEY=value` flags so Claude Code launches the subprocess with them

**`backend/.env.example`:** Template for a `.env` file. The actual `.env` is git-ignored.

---

## 11. Testing Strategy

### 11.1 Backend Tests (11 tests)

**Location:** `backend/tests/test_tasks_api.py`

**Approach:** FastAPI `TestClient` + dependency overrides.

**Conftest highlights:**
```python
# In-memory SQLite + StaticPool ensures one DB shared across connections
engine = create_engine("sqlite:///:memory:",
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)

# Override the app's engine before importing routes
import app.db
app.db.engine = engine

# Autouse fixture resets the DB between tests
@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    return {"X-API-Key": "dev-secret-123"}
```

**Coverage:**
- 401 when API key is missing or wrong
- 422 when title is empty
- 422 when due_date is in the past on POST
- 201 + roundtrip for create → get → update → delete
- 404 on get/update/delete missing id
- All filters (status, priority, tag, due_before, due_after)

### 11.2 MCP Server Tests

**Location:** `mcp-server/tests/`

**Approach:** Build an in-process `FastMCP(name="test")`, register only the module under test, stub HTTP via `AsyncMock`.

**Files:**

| File | Tests | Targets |
|---|---|---|
| `test_tools.py` | broad smoke tests | All CRUD tools |
| `test_tasks_crud.py` | 10 tests | `add_task` (6) + `get_task_stats` (4 including error path) |
| `test_task_resources.py` | 8 tests | `_overdue` (3 + error path) + `_high_priority` (3 + error path + dedup) |

**Test pattern for tools:**
```python
@pytest.fixture()
def server() -> FastMCP:
    mcp = FastMCP(name="test")
    tasks_crud.register(mcp)
    return mcp

async def test_happy_path(server):
    with patch("tools.tasks_crud.api_post", new=AsyncMock(return_value={"id": 42})):
        await server.call_tool("add_task", {"title": "X"})
        # introspect the mock
```

**Test pattern for resources:**
```python
async def test_overdue_excludes_done():
    tasks = [...]
    with patch("resources.task_resources.api_get", new=AsyncMock(return_value=tasks)):
        result = await _overdue()
    rows = json.loads(result)
    assert ...
```

**Coverage rule (per `test-writer` agent):** every public function gets happy path + edge case + error path (ApiError propagation, validation rejection, or empty input).

### 11.3 Running Tests

```bash
# Backend
pytest -q backend/tests
# Expected: 11 passed

# MCP server
pytest -q mcp-server/tests
# Expected: 22 passed (as of latest commit)
```

The PostToolUse hook runs the relevant suite automatically after every `.py` edit.

---

## 12. Development Workflow

### 12.1 Setup (Windows / PowerShell)

```powershell
git clone <repo> task-manager
cd task-manager
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -e ./backend[dev]
pip install -e ./mcp-server[dev]
Copy-Item backend\.env.example backend\.env
```

### 12.2 Run the Backend (terminal 1)

```powershell
.\.venv\Scripts\Activate.ps1
$env:API_KEY = "dev-secret-123"
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Verify: `http://localhost:8000/docs`, click Authorize, enter `dev-secret-123`.

### 12.3 Connect the MCP Server to Claude Code

```powershell
claude mcp add task-manager `
  --env API_KEY=dev-secret-123 `
  --env API_BASE_URL=http://localhost:8000 `
  -- C:/Work/task-manager/.venv/Scripts/python.exe C:/Work/task-manager/mcp-server/server.py
```

**Important:** Run from inside the project directory. Use the **full path** to the venv Python, otherwise Claude Code falls back to system Python which lacks the `mcp` package.

Verify: `claude mcp list` → `task-manager: ✓ Connected`.

### 12.4 Inner Loop

1. Activate venv.
2. Edit a `.py` file.
3. **Automatic:** PostToolUse hook runs `ruff --fix` + `black` + `pytest` on the affected package.
4. If you added a new public function: `/add-test path/to/file.py::name`.
5. `git add <specific-files>` (never `git add .` per CLAUDE.md).
6. `/git-commit` → drafts Conventional Commit, optionally invokes `code-reviewer`, commits on confirm.

### 12.5 Verify MCP Server with MCP Inspector (Windows quirk)

```powershell
$env:PATH = "C:\Work\task-manager\.venv\Scripts;" + $env:PATH
$env:API_KEY = "dev-secret-123"
$env:API_BASE_URL = "http://localhost:8000"
& "C:\Program Files\nodejs\npx.cmd" "@modelcontextprotocol/inspector" python "mcp-server/server.py"
```

Reason for the quirk: Inspector v0.21 mishandles Windows paths starting with `C:\` (the `\t` in `\task-manager` is interpreted as tab). Workaround: prepend venv to PATH and use `python` + relative path.

---

## 13. Design Principles and Hard Rules

### 13.1 The "Do Not" List (from CLAUDE.md)

1. **Never bypass MCP from inside Claude.** No direct HTTP calls.
2. **Never hard-code the API key.** `os.getenv("API_KEY", "dev-secret-123")` is the only acceptable form.
3. **Never commit `.env`.** Already gitignored.
4. **Never add a mutating tool to `resources/`.** Resources are read-only.
5. **Never disable hooks** (`--no-verify`, removing `.claude/settings.json` entries) without explicit user approval.

### 13.2 Architectural Invariants

- **Single source of API key:** `mcp-server/api_client.py`. No other module reads `API_KEY` or sets `X-API-Key`.
- **MCP is the only client of the backend.** No other code in this repo calls `httpx` or `requests`.
- **Resources call only `api_get`.** Mutations go through tools.
- **All enums (status, priority) are defined in `backend/app/models.py`** and mirrored as `Literal` types in `mcp-server/tools/tasks_crud.py`. Drift between them is a code-reviewer finding.

### 13.3 Validation Layers

Every input passes through **three** validators before hitting the database:

1. **MCP tool schema:** Auto-generated by FastMCP from type hints. Rejects wrong types and unknown enum values.
2. **MCP Pydantic model:** `_AddTaskInput`, `_UpdatePatch`. Bounds checks, defaults.
3. **Backend Pydantic schema:** `TaskCreate`, `TaskUpdate`. Business rules (title strip, due_date past-future, tag normalization, deduplication).

This is intentional defense in depth. Removing layer 2 would still work, but you would lose the early error path on the MCP side.

### 13.4 Style Conventions

- Python 3.11+, type hints required on public functions.
- `ruff` + `black` with line length 100. Enforced by post-edit hook.
- `pytest-asyncio` with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.
- HTTP client on MCP side: always `httpx.AsyncClient`, never `requests`.
- Conventional Commits everywhere. Scopes: `backend`, `mcp`, `hooks`, `skills`, `agents`, `docs`, `readme`.

---

## 14. Extension Guide

### 14.1 Adding a New Tool

1. Edit `mcp-server/tools/tasks_crud.py`.
2. Inside `register(mcp)`, add a new function decorated with `@mcp.tool()`.
3. Use `Literal[...]` for enum-like parameters.
4. Call `api_get / api_post / api_put / api_delete` — never `httpx` directly.
5. If a new backend endpoint is needed, add it to `backend/app/routers/tasks.py` plus a matching Pydantic schema in `backend/app/schemas.py`.
6. Add tests in `mcp-server/tests/test_tasks_crud.py` and (if backend changed) `backend/tests/test_tasks_api.py`.

### 14.2 Adding a New Resource

1. Edit `mcp-server/resources/task_resources.py`.
2. Write a private async helper (e.g. `_my_resource()`) that calls only `api_get`.
3. Inside `register(mcp)`, decorate a wrapper with `@mcp.resource("tasks://my-resource", mime_type="application/json")`.
4. Return a JSON string via `json.dumps(...)`.
5. Add tests in `mcp-server/tests/test_task_resources.py` — happy path, exclusion logic, ApiError propagation.

### 14.3 Adding a New Prompt

1. Create `mcp-server/prompts/my_prompt.py`.
2. Define `PROMPT_TEMPLATE = """..."""` with markdown instructions for Claude.
3. Expose `register(mcp)` that decorates a function with `@mcp.prompt(name="...", description="...")`.
4. Wire it in `mcp-server/server.py` (`from prompts import my_prompt` + `my_prompt.register(mcp)`).
5. (Optional, for IDE visibility) Mirror it as `.claude/commands/my-prompt.md`.

### 14.4 Adding a New Skill or Sub-Agent

1. Create a markdown file in `.claude/skills/` or `.claude/agents/`.
2. Frontmatter must include `name` and `description`. Agents also specify `tools: Read, Grep, ...`.
3. Body is the procedural instructions for Claude.
4. No code execution — these are Claude-side configurations.

---

## 15. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| MCP Inspector mangled path (`Worktask-manager...`) | Inspector v0.21 mishandles Windows paths starting with `C:\` | Prepend venv to `$env:PATH` and use `python` + relative path |
| `401 Missing or invalid API key` from MCP tools | `API_KEY` unset or mismatch | Set identical value in backend terminal AND `claude mcp add --env` |
| `tasks://today` returns empty array | No tasks have due_date today/past OR all are done | Add a task with `due_date` today via PUT (POST rejects past dates) |
| `claude mcp list` shows `Failed to connect` | Claude Code uses system Python without `mcp` | Pass full venv path: `C:/Work/task-manager/.venv/Scripts/python.exe` |
| `task-manager` missing from `/mcp` | `~/.claude.json` stores project key with `/` from `claude mcp add`, but Claude Code looks it up with `\` | Run `claude mcp add` from project directory. If persists, edit `.claude.json` and move `mcpServers` from forward-slash key to back-slash key |
| `/daily-plan` not recognized in IDE | IDE extension does not expose MCP prompts as slash commands | Use the mirrored `.claude/commands/` versions, or natural language |
| Pre-edit hook blocks a legitimate write | Pattern false positive | Use `os.getenv(...)`; the allowlist already covers it |
| `pytest` not invoked by post-edit hook | Dev tools missing from active venv | `pip install -e ./backend[dev] -e ./mcp-server[dev]` |
| New resource/tool not visible in `/mcp` | Current Claude Code session was started before the MCP server got the new code | Start a NEW chat session (existing sessions cache the tool list from session start) |
| Backend tests fail with "no such table: task" | conftest forgot to use `StaticPool` for in-memory SQLite | Ensure `poolclass=StaticPool` in `create_engine` and `app.db.engine = engine` before importing the app |

---

## 16. Frequently Asked Questions

### Q: Why MCP instead of letting Claude call the REST API directly?
**A:** Five reasons:
1. Secret hygiene — the API key never enters the LLM context.
2. Type-safe tools — JSON schemas prevent invalid enum values from ever reaching the wire.
3. Auto-discovery — Claude sees tools/resources/prompts at session start.
4. Portability — same server works in Claude Desktop, Inspector, any MCP host.
5. Defense in depth — resources are physically restricted to GET, so prompt injection can't mutate state.

### Q: Why is `due_date` stored as a string, not a `date` type?
**A:** Simplifies SQLite portability (SQLite has no native date type, just text). Comparisons on ISO strings (`YYYY-MM-DD`) are lexicographic-correct, so `due_date < today` works as expected.

### Q: Why are tags stored as CSV instead of in a separate table?
**A:** Simplicity over normalization. This is a personal task manager with small data, not a multi-user system. The Python-side post-filter in the `tag` query parameter is fast enough for thousands of tasks. If scale demanded it, a join table would be straightforward to add.

### Q: Why does the MCP server have its own Pydantic validation when the backend also validates?
**A:** Defense in depth. The MCP-side validation catches errors earlier (before HTTP) and gives Claude a more immediate, structured error. The backend validation is the final authority. Either layer can be tightened without weakening the other.

### Q: Why do prompts always instruct Claude to use resources, not tools?
**A:** Resources are physically read-only — calling `tasks://overdue` cannot mutate state, by architectural rule. Instructing the prompt to use resources adds a second safety layer: even if Claude misreads the intent of "/daily-plan", it cannot accidentally delete tasks while reading.

### Q: What's the difference between a skill and an MCP prompt?
**A:** A skill (`.claude/skills/`) is a workflow with steps that may include tool calls, sub-agent delegation, and user confirmation. An MCP prompt (`mcp-server/prompts/`) is just a markdown template returned by the server. Skills are richer (they can orchestrate); prompts are simpler (they're text). Skills are Claude Code-specific; MCP prompts work in any MCP host.

### Q: Why are there both PowerShell and Bash post-edit hooks?
**A:** The project was developed on Windows but designed to be cross-platform. `post_edit.ps1` is wired in `settings.json` because that's the dev environment; `post_edit.sh` is the POSIX mirror for contributors on Linux/macOS. They do exactly the same thing.

### Q: How do I add a new agent?
**A:** Create a markdown file in `.claude/agents/` with frontmatter (`name`, `description`, `tools`). The body is the system prompt for that agent. To invoke it from the main Claude, use the Agent tool with `subagent_type: "<agent-name>"`. Sub-agents have isolated context — pass them everything they need to know in the initial prompt.

### Q: Why does `task-planner` only have access to MCP tools, not file access?
**A:** It's a planning agent, not a coding agent. It reads tasks via `get_all_tasks` and `get_task_stats`, then writes a markdown plan back to the main conversation. Giving it Read/Write would be unnecessary surface area.

### Q: Can I run the backend without the MCP server?
**A:** Yes. The backend is a standalone FastAPI app. Open `http://localhost:8000/docs`, authorize with `dev-secret-123`, and you have full Swagger UI for CRUD.

### Q: Can I run the MCP server without Claude Code?
**A:** Yes. Use MCP Inspector: `npx @modelcontextprotocol/inspector python mcp-server/server.py`. Inspector opens a browser UI where you can call tools, read resources, and view prompts manually.

### Q: How do I add support for a new field on Task (e.g. `assignee`)?
**A:** Touch all three layers:
1. **Backend:** Add the column to `models.py` (`Task` SQLModel), add the field to `TaskCreate/Update/Read` in `schemas.py` (with any validators), filter it in the router if needed.
2. **MCP:** Add the parameter to `_AddTaskInput`, `_UpdatePatch`, and the tool signatures in `tasks_crud.py`.
3. **Tests:** Cover happy path and any new validation rule in both `backend/tests/` and `mcp-server/tests/`.
4. **Docs:** Update `CLAUDE.md` and `README.md` if the surface changed publicly.

### Q: Why is `code-reviewer` invoked manually from `/git-commit` instead of automatically?
**A:** Two reasons:
1. It's costly — code review uses tokens. For trivial commits (typo fix, doc update), it's overkill.
2. It's a recommendation, not a gate. The user has final say on whether to commit. Hard-gating would block legitimate fast-path commits.

### Q: What's the database migration story?
**A:** None. SQLModel auto-creates tables on `init_db()`. For schema changes, you would need to add Alembic or manually drop/recreate. Since this is a personal tool with disposable data, that's acceptable.

### Q: How does Claude know which tool to call for "show me overdue tasks"?
**A:** Two signals:
1. The `instructions` field on the FastMCP server says "use resources for browsing, tools for mutations."
2. The resource URI naming (`tasks://overdue`) is descriptive. Claude matches the user's intent to the closest URI semantically.

In practice, Claude usually reads `tasks://overdue` for this query. If the user said "delete all overdue tasks," Claude would read `tasks://overdue` first to get IDs, then call `delete_task` for each — never the other way around.

### Q: What happens if the MCP server crashes mid-session?
**A:** Claude Code surfaces a tool-call error. The user can run `claude mcp list` to see if it reconnected, or restart Claude Code. The state is fine — all persistence is in SQLite via the backend; the MCP server is stateless.

### Q: Where are recent commits visible?
**A:** `git log --oneline` shows the local history. Recent commits include:
- `feat(mcp): get_task_stats, 2 resources, weekly-review, task-planner`
- `docs(readme): translate to English and remove changelog`
- `docs(readme): align setup with verified workflow and add screenshots`
- `test(mcp): cover add_task happy path, defaults, and validation`

---

## Appendix A: Complete Tool/Resource/Prompt Catalog

### Tools (6)
| Name | Mutates | Backend |
|---|---|---|
| `add_task` | yes | POST /tasks |
| `get_task` | no | GET /tasks/{id} |
| `get_all_tasks` | no | GET /tasks |
| `update_task` | yes | PUT /tasks/{id} |
| `delete_task` | yes | DELETE /tasks/{id} |
| `get_task_stats` | no | GET /tasks + in-memory aggregation |

### Resources (6)
| URI | Filter |
|---|---|
| `tasks://all` | none |
| `tasks://completed` | status=done |
| `tasks://today` | open, due ≤ today, not null |
| `tasks://in-progress` | status=in_progress |
| `tasks://overdue` | due_date < today, not done, not null |
| `tasks://high-priority` | priority ∈ {urgent, high}, not done; sorted urgent-first then by due_date |

### Prompts (3)
| Name | Reads | Produces |
|---|---|---|
| `daily-plan` | today, in-progress | Day plan: Must do / In progress / Stretch + Focus |
| `prioritize-tasks` | all | Ranked table + Rationale + Suggested deferrals |
| `weekly-review` | completed, in-progress, overdue, all | Completed / In progress / Overdue / Recommended focus + Retrospective |

### Skills (2)
| Name | Function |
|---|---|
| `/git-commit` | Draft Conventional Commits message, optionally invoke code-reviewer, commit on confirm |
| `/add-test` | Generate pytest skeleton via test-writer sub-agent |

### Sub-agents (3)
| Name | Tools | Role |
|---|---|---|
| `code-reviewer` | Read, Grep, Glob, Bash | Independent diff review (read-only) |
| `test-writer` | Read, Write, Edit, Bash, Grep, Glob | Generate pytest files |
| `task-planner` | get_all_tasks, get_task, get_task_stats | Backlog triage and execution plan |

### Hooks (2)
| Trigger | Script | Purpose |
|---|---|---|
| PreToolUse on Edit/Write/MultiEdit | `precheck_secrets.py` | Block hard-coded secrets |
| PostToolUse on Edit/Write/MultiEdit | `post_edit.ps1` / `.sh` | ruff + black + pytest on touched .py |

---

## Appendix B: Quick Reference Commands

```powershell
# Setup
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -e ./backend[dev] -e ./mcp-server[dev]

# Run backend
$env:API_KEY = "dev-secret-123"
uvicorn app.main:app --reload --port 8000 --app-dir backend

# Run MCP server (debug)
$env:API_BASE_URL = "http://localhost:8000"
python mcp-server/server.py

# Register MCP with Claude Code
claude mcp add task-manager `
  --env API_KEY=dev-secret-123 `
  --env API_BASE_URL=http://localhost:8000 `
  -- C:/Work/task-manager/.venv/Scripts/python.exe C:/Work/task-manager/mcp-server/server.py

claude mcp list
claude mcp remove task-manager

# MCP Inspector
$env:PATH = "C:\Work\task-manager\.venv\Scripts;" + $env:PATH
& "C:\Program Files\nodejs\npx.cmd" "@modelcontextprotocol/inspector" python "mcp-server/server.py"

# Tests
pytest -q backend/tests       # 11 tests
pytest -q mcp-server/tests    # 22 tests

# Lint/format manually
ruff check --fix .
black .
```

---

*End of knowledge base. For specific verification scenarios, see `TESTING.md`. For project conventions enforced on Claude, see `CLAUDE.md`. For onboarding, see `README.md`.*
