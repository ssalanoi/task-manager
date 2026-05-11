"""`/prioritize-tasks` prompt: re-order open tasks with rationale.

Reads only the `tasks://all` resource — no mutating tool calls.
"""
from __future__ import annotations

from typing import Any


PROMPT_TEMPLATE = """\
You are an assistant ranking the user's open tasks by importance.

Use the MCP **resource** `tasks://all` (read-only). Do NOT call mutating tools.

Sort the open tasks (exclude `status=done`) using these rules in order:
  1. Overdue first (`due_date < today`).
  2. Higher priority first: urgent > high > medium > low.
  3. Earlier `due_date` first; tasks with no `due_date` go last within their tier.

Output a markdown table with columns: rank, id, title, priority, due_date, status.

Below the table, write **Rationale** as a bulleted list — one short line per
task explaining why it sits at that rank.

End with **Suggested deferrals**: at most 3 low/medium-priority items that
could be dropped or pushed out so the user can focus.
"""


def register(mcp: Any) -> None:
    @mcp.prompt(
        name="prioritize-tasks",
        description="Rank open tasks by overdue/priority/due-date with rationale.",
    )
    def prioritize_tasks() -> str:
        return PROMPT_TEMPLATE
