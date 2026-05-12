"""Read-only MCP resources backed by GET /tasks.

URIs:
  tasks://all            -> every task
  tasks://completed      -> status == done
  tasks://today          -> open tasks due today or overdue (excludes done)
  tasks://in-progress    -> status == in_progress
  tasks://overdue        -> non-done tasks whose due_date is strictly in the past
  tasks://high-priority  -> non-done tasks with priority == urgent or high

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


async def _overdue() -> str:
    """Tasks past their due_date that are not done."""
    today = date.today().isoformat()
    rows = await api_get("/tasks", params={"due_before": today})
    open_rows = [
        r
        for r in rows
        if r.get("status") != "done" and r.get("due_date") is not None
    ]
    return _dump(open_rows)


async def _high_priority() -> str:
    """Non-done tasks with priority=urgent or priority=high, sorted by urgency then due_date."""
    urgent = await api_get("/tasks", params={"priority": "urgent"})
    high = await api_get("/tasks", params={"priority": "high"})
    rows = [r for r in (urgent + high) if r.get("status") != "done"]
    seen: set[int] = set()
    unique: List[dict] = []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    unique.sort(key=lambda r: (r.get("priority") != "urgent", r.get("due_date") or "9999-99-99"))
    return _dump(unique)


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

    @mcp.resource("tasks://overdue", mime_type="application/json")
    async def overdue_tasks() -> str:
        """Non-done tasks whose due_date is strictly in the past."""
        return await _overdue()

    @mcp.resource("tasks://high-priority", mime_type="application/json")
    async def high_priority_tasks() -> str:
        """Non-done tasks with priority=urgent or high, sorted by urgency then due_date."""
        return await _high_priority()
