"""`/weekly-review` prompt: reflect on the week and plan ahead.

The prompt instructs Claude to consult RESOURCES (not mutating tools) so it
cannot accidentally change state while reviewing.
"""
from __future__ import annotations

from typing import Any


PROMPT_TEMPLATE = """\
You are an assistant helping the user run a structured weekly review.

Use the MCP **resources** (not tools) to read current task state:

  1. Read resource `tasks://completed`    -> tasks marked done
  2. Read resource `tasks://in-progress`  -> currently active work
  3. Read resource `tasks://overdue`      -> tasks past their due_date, still open
  4. Read resource `tasks://all`          -> full backlog for context

Then produce a weekly review in markdown with these four sections:

  ### Completed this week
  Tasks with status=done. For each: `[id] title — priority`.
  If the list is empty, write "Nothing completed yet — consider moving something to done."

  ### In progress
  Tasks currently being worked on.
  Flag any whose due_date has already passed with a ⚠️ symbol.

  ### Overdue — needs attention
  Tasks from `tasks://overdue`. Group by priority (urgent first).
  For each: `[id] title — due_date, priority`.

  ### Recommended focus for next week
  Pick the top 5 open tasks for the coming week. Criteria (in order):
    1. Overdue items not yet started
    2. High / urgent priority items due within 7 days
    3. In-progress items closest to completion
  For each: `[id] title — priority, due_date, reason for selection`.

Finish with a one-paragraph **Retrospective** that notes:
  - Whether the task load was realistic (too many open / overdue items is a signal)
  - Any recurring pattern (e.g. tasks consistently missed, priority inflation)
  - One concrete suggestion to improve next week's execution

Do NOT call mutating tools (add_task / update_task / delete_task). Read-only only.
"""


def register(mcp: Any) -> None:
    @mcp.prompt(
        name="weekly-review",
        description="Structured weekly review: completed work, overdue tasks, and a recommended focus for next week.",
    )
    def weekly_review() -> str:
        return PROMPT_TEMPLATE
