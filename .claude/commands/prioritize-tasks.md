---
description: Rank open tasks by overdue → priority → due_date (uses task-manager MCP resources)
---

You are an assistant ranking the user's open tasks by importance.

Use the MCP **resource** `tasks://all` from the `task-manager` server (read-only). Do NOT call mutating tools.

Sort the open tasks (exclude `status=done`) using these rules in order:

  1. Overdue first (`due_date < today`).
  2. Higher priority first: urgent > high > medium > low.
  3. Earlier `due_date` first; tasks with no `due_date` go last within their tier.

Output a markdown table with columns: **rank, id, title, priority, due_date, status**.

Below the table, write **Rationale** as a bulleted list — one short line per task explaining why it sits at that rank.

End with **Suggested deferrals**: at most 3 low/medium-priority items that could be dropped or pushed out so the user can focus.

**Do NOT call mutating tools** (`add_task` / `update_task` / `delete_task`). Read-only only.
