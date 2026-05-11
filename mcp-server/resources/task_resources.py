"""Read-only MCP resources backed by GET /tasks.

URIs:
  tasks://all          -> every task
  tasks://completed    -> status == done
  tasks://today        -> open tasks due today or overdue (excludes done)
  tasks://in-progress  -> status == in_progress

Resources never invoke mutating endpoints.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, List

from api_client import api_get


def _dump(rows: List[dict]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


async def _all() -> str:
    rows = await api_get("/tasks")
    return _dump(rows)


async def _completed() -> str:
    rows = await api_get("/tasks", params={"status": "done"})
    return _dump(rows)


async def _in_progress() -> str:
    rows = await api_get("/tasks", params={"status": "in_progress"})
    return _dump(rows)


async def _today() -> str:
    today = date.today()
    tomorrow = (today + timedelta(days=1)).isoformat()
    rows = await api_get("/tasks", params={"due_before": tomorrow})
    open_rows = [
        r
        for r in rows
        if r.get("status") != "done" and r.get("due_date") is not None
    ]
    return _dump(open_rows)


def register(mcp: Any) -> None:
    """Register read-only resources on the given FastMCP instance."""

    @mcp.resource("tasks://all", mime_type="application/json")
    async def all_tasks() -> str:
        """All tasks as JSON array."""
        return await _all()

    @mcp.resource("tasks://completed", mime_type="application/json")
    async def completed_tasks() -> str:
        """Tasks with status=done."""
        return await _completed()

    @mcp.resource("tasks://today", mime_type="application/json")
    async def today_tasks() -> str:
        """Open tasks due today or overdue (excludes done)."""
        return await _today()

    @mcp.resource("tasks://in-progress", mime_type="application/json")
    async def in_progress_tasks() -> str:
        """Tasks with status=in_progress."""
        return await _in_progress()
