"""`/daily-plan` prompt: build a focused plan for the current day.

The prompt instructs Claude to consult RESOURCES (not mutating tools) so it
cannot accidentally change state while planning.
"""
from __future__ import annotations

from typing import Any


PROMPT_TEMPLATE = """\
You are an assistant helping the user plan their day.

Use the MCP **resources** (not tools) to read current task state:

  1. Read resource `tasks://today`        -> due today or overdue, open
  2. Read resource `tasks://in-progress`  -> currently active work

Then produce a short markdown plan with three sections:

  ### Must do today
  Items that are overdue or due today. Sorted by priority (urgent > high > medium > low).

  ### In progress
  Items already in flight. Note any that have stalled (due_date in the past).

  ### Stretch
  At most 3 high-priority items due within the next 7 days that aren't in the
  two sections above.

For each item show: `[id] title  — priority, due_date`.

Finish with a single short paragraph titled **Focus** that recommends what to
tackle first and why. Do NOT call mutating tools (add_task / update_task /
delete_task). Read-only only.
"""


def register(mcp: Any) -> None:
    @mcp.prompt(name="daily-plan", description="Plan the current day from open and in-progress tasks.")
    def daily_plan() -> str:
        return PROMPT_TEMPLATE
