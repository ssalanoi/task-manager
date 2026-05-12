# Task Manager — End-to-End Verification Checklist

A complete set of natural-language prompts and CLI commands to exercise every layer of the system: tools, resources, prompts, skills, sub-agents, hooks, and backend validation.

Copy any prompt into the Claude Code chat (or the `claude` CLI terminal) to run the corresponding check. Estimated total runtime: **10–15 minutes**.

---

## Prerequisites

1. Backend running:
   ```powershell
   cd C:\Work\task-manager
   .\.venv\Scripts\Activate.ps1
   $env:API_KEY = "dev-secret-123"
   uvicorn app.main:app --reload --port 8000 --app-dir backend
   ```
2. MCP server registered in Claude Code (`claude mcp list` shows `task-manager: Connected`).
3. Project opened in Claude Code from `C:\Work\task-manager`.

---

## 1. Tools — CRUD operations

### `add_task` — create
```
Add a task "Write spec for new module" with priority urgent, due 2026-05-15, tags: docs, sprint
```
```
Create three tasks: buy milk (low), call doctor (medium, due 2026-05-12), prepare presentation (high, due 2026-05-20)
```

### `get_all_tasks` — list with filters
```
Show me all tasks
```
```
Show only tasks with status in_progress
```
```
Show tasks with priority urgent or high
```
```
Show tasks tagged "docs"
```
```
Show tasks due before 2026-05-15
```

### `get_task` — by id
```
Show task with id=1
```

### `update_task` — modify
```
Mark task 1 as done
```
```
Move task 2 to in_progress
```
```
Change task 3 priority to urgent and push due date to 2026-05-18
```
```
Add tag "review" to task 1
```

### `delete_task` — remove
```
Delete task 5
```

### `get_task_stats` — aggregate health-check
```
Show me task statistics
```
```
How many tasks are overdue?
```
→ Expect a JSON object with `total`, `by_status` (todo/in_progress/done counts), `by_priority` (low/medium/high/urgent counts), and `overdue` count.

---

## 2. Resources — read-only URIs

```
Read the resource tasks://all
```
```
Read tasks://completed — show me what's done
```
```
Read tasks://today — what's due or overdue
```
```
Read tasks://in-progress — what's actively being worked on
```
```
Show me all overdue tasks
```
→ Uses `tasks://overdue` — returns non-done tasks with `due_date` strictly before today.
```
Show me high-priority tasks
```
→ Uses `tasks://high-priority` — returns non-done tasks with `priority=urgent` or `priority=high`, sorted urgent-first then by due_date.

**Read-only protection check:**
```
Using only resources (not tools), set task 1 status to done
```
→ Claude should refuse or explain that resources cannot mutate state.

---

## 3. Prompts — MCP-defined

### In Claude Code CLI terminal:
```
/daily-plan
/prioritize-tasks
/weekly-review
```

### Equivalent custom slash commands (work everywhere):
```
/daily-plan
/prioritize-tasks
/weekly-review
```

### Natural-language fallback (any interface):
```
Build me today's plan
```
```
Rank all open tasks by priority with rationale
```
```
Give me a weekly review
```
→ `/weekly-review` returns a 4-section report: **Completed**, **In Progress**, **Overdue**, **Recommended focus for next week** with a retrospective paragraph.

---

## 4. Skills — user-invoked workflows

### `/git-commit`
Make a real code change first, then stage it:
```powershell
# edit a file, e.g. README.md
git add README.md
```
Then in Claude Code:
```
/git-commit
```
→ The skill drafts a Conventional Commits message, optionally invokes the `code-reviewer` sub-agent, and creates the commit on confirmation.

### `/add-test`
```
/add-test mcp-server/tools/tasks_crud.py::add_task
```
→ Delegates to the `test-writer` sub-agent and writes a pytest skeleton.

---

## 5. Sub-agents — delegated work

### `code-reviewer`
```
Run the code-reviewer agent on the current git diff
```
or
```
Use the code-reviewer agent to audit backend/app/routers/tasks.py for security and error-handling issues
```

### `test-writer`
```
Use the test-writer agent to generate tests for get_all_tasks in mcp-server/tools/tasks_crud.py — cover the happy path, status filtering, and the empty-result case
```

### `task-planner`
```
Plan my week
```
```
What should I work on next?
```
→ The agent calls `get_task_stats` and `get_all_tasks`, then outputs a triage table with four buckets: **Critical** (overdue urgent), **This week** (high-priority with near due dates), **High-value** (high priority, flexible deadline), **Backlog**. It also flags tasks that are too broad and suggests breaking them down.

---

## 6. Hooks — automatic, deterministic

### Pre-edit hook (`hooks/precheck_secrets.py`)

**Test A — should be blocked.** Ask Claude:
> *Create a file `test_leak.py` at the project root that assigns a hard-coded production-looking API key string (a literal like `sk-prod-` followed by 16+ random alphanumerics) to a top-level `API_KEY` variable.*

→ The hook must exit non-zero and Claude Code must surface a blocking message. The file is **not** written.

**Test B — should pass (allowlisted pattern).** Ask Claude:
> *Create a file `test_safe.py` that reads `API_KEY` via `os.getenv("API_KEY", "dev-secret-123")`.*

→ The hook must allow the write; the file is created.

> **Note:** the test prompts above are intentionally phrased in prose so this file itself does not trip the hook when Claude reads/edits it.

### Post-edit hook (`hooks/post_edit.ps1`)

Triggered automatically after any `Edit` / `Write` on a `.py` file:
```
Add a function `def hello(): return "world"` to backend/app/main.py
```
→ After the edit, the hook chain runs:
1. `ruff check --fix` on the file
2. `black` formatting
3. `pytest` for the affected package

Hook output is streamed back to the chat.

---

## 7. End-to-end scenario (all layers)

Run as a single conversation:

```
1. Add 5 tasks with mixed priorities and due dates (include some dated yesterday to test overdue handling)
2. Show me task statistics                              ← get_task_stats
3. Read tasks://overdue — should contain yesterday's items
4. Read tasks://high-priority — should list urgent/high tasks sorted by urgency
5. /prioritize-tasks — produce a ranked table
6. Plan my week                                         ← task-planner agent
7. Move the highest-priority task to in_progress
8. Read tasks://in-progress — should now include that task
9. Mark it done
10. Read tasks://completed — it should appear there
11. /weekly-review — report should reflect completed + remaining work
12. /daily-plan — today's plan should reflect the new state
13. Delete all completed tasks
```

---

## 8. Negative tests — input validation & auth

### Backend validation
```
Add a task with an empty title
```
→ Expect HTTP 422 surfaced as an MCP error.

```
Add a task with due_date 2024-01-01 (in the past)
```
→ Expect a validation error (POST forbids past dates).

### API key mismatch
In the terminal hosting the MCP server, temporarily replace the API key env var with an obviously invalid value (e.g. set `API_KEY` to `bad-value`), restart the server, then in Claude Code:
```
Show me all tasks
```
→ Expect a 401-derived MCP error.

### Missing resource
```
Show task with id=99999
```
→ Expect a 404 Task not found error.

---

## Verification matrix

| Capability | Verified by |
|---|---|
| Tools (CRUD) | add → get → update → delete sequence |
| Tool filters | get_all_tasks with status / priority / tag / due_date |
| `get_task_stats` | aggregate counts including overdue |
| Resources readable | all six URIs (all, completed, today, in-progress, overdue, high-priority) |
| Resources read-only | mutation attempt via resource refused |
| MCP Prompts | /daily-plan, /prioritize-tasks, /weekly-review |
| Custom slash commands | /daily-plan, /prioritize-tasks, /weekly-review in any interface |
| Skills | /git-commit, /add-test |
| Sub-agents | code-reviewer, test-writer, task-planner |
| Pre-edit hook blocks secrets | hard-coded API key write attempt |
| Post-edit hook formats + tests | edit on a .py file |
| Backend validation | empty title, past due_date |
| Auth required | corrupted API key → 401 |
| 404 handling | get_task id=99999 |

Step through the list top-to-bottom — at the end, every required system capability has been exercised at least once.
