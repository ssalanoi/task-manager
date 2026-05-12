"""Tests for the private async helpers in resources/task_resources.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api_client import ApiError  # noqa: E402
from resources.task_resources import _high_priority, _overdue  # noqa: E402


# ---------------------------------------------------------------------------
# _overdue
# ---------------------------------------------------------------------------


async def test_overdue_excludes_done() -> None:
    tasks = [
        {"id": 1, "status": "todo", "priority": "high", "due_date": "2020-01-01"},
        {"id": 2, "status": "in_progress", "priority": "medium", "due_date": "2020-06-01"},
        {"id": 3, "status": "done", "priority": "low", "due_date": "2020-01-01"},
    ]
    with patch("resources.task_resources.api_get", new=AsyncMock(return_value=tasks)):
        result = await _overdue()
    rows = json.loads(result)
    ids = [r["id"] for r in rows]
    assert 1 in ids
    assert 2 in ids
    assert 3 not in ids


async def test_overdue_excludes_no_due_date() -> None:
    tasks = [
        {"id": 1, "status": "todo", "priority": "medium", "due_date": None},
        {"id": 2, "status": "in_progress", "priority": "low", "due_date": None},
    ]
    with patch("resources.task_resources.api_get", new=AsyncMock(return_value=tasks)):
        result = await _overdue()
    rows = json.loads(result)
    assert rows == []


async def test_overdue_returns_json_string() -> None:
    tasks = [
        {"id": 1, "status": "todo", "priority": "urgent", "due_date": "2020-01-01"},
    ]
    with patch("resources.task_resources.api_get", new=AsyncMock(return_value=tasks)):
        result = await _overdue()
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# _high_priority
# ---------------------------------------------------------------------------


async def test_high_priority_sort_order() -> None:
    urgent_tasks = [
        {"id": 1, "status": "todo", "priority": "urgent", "due_date": "2026-06-01"},
        {"id": 2, "status": "todo", "priority": "urgent", "due_date": "2026-05-01"},
    ]
    high_tasks = [
        {"id": 3, "status": "todo", "priority": "high", "due_date": "2026-04-01"},
    ]

    async def _fake_api_get(_path: str, *, params: dict | None = None) -> list:
        if params and params.get("priority") == "urgent":
            return urgent_tasks
        return high_tasks

    with patch("resources.task_resources.api_get", new=AsyncMock(side_effect=_fake_api_get)):
        result = await _high_priority()
    rows = json.loads(result)
    priorities = [r["priority"] for r in rows]
    # all urgent entries must precede any high entry
    seen_high = False
    for p in priorities:
        if p == "high":
            seen_high = True
        if seen_high:
            assert p != "urgent"
    # within urgent, earlier due_date comes first
    urgent_rows = [r for r in rows if r["priority"] == "urgent"]
    assert urgent_rows[0]["due_date"] <= urgent_rows[1]["due_date"]


async def test_high_priority_excludes_done() -> None:
    urgent_tasks = [
        {"id": 1, "status": "done", "priority": "urgent", "due_date": "2026-06-01"},
    ]
    high_tasks = [
        {"id": 2, "status": "done", "priority": "high", "due_date": "2026-06-01"},
        {"id": 3, "status": "todo", "priority": "high", "due_date": "2026-07-01"},
    ]

    async def _fake_api_get(_path: str, *, params: dict | None = None) -> list:
        if params and params.get("priority") == "urgent":
            return urgent_tasks
        return high_tasks

    with patch("resources.task_resources.api_get", new=AsyncMock(side_effect=_fake_api_get)):
        result = await _high_priority()
    rows = json.loads(result)
    ids = [r["id"] for r in rows]
    assert 1 not in ids
    assert 2 not in ids
    assert 3 in ids


async def test_overdue_propagates_api_error() -> None:
    with patch(
        "resources.task_resources.api_get",
        new=AsyncMock(side_effect=ApiError(500, "server error")),
    ):
        with pytest.raises(ApiError):
            await _overdue()


async def test_high_priority_propagates_api_error() -> None:
    with patch(
        "resources.task_resources.api_get",
        new=AsyncMock(side_effect=ApiError(503, "unavailable")),
    ):
        with pytest.raises(ApiError):
            await _high_priority()


async def test_high_priority_deduplication() -> None:
    shared_task = {"id": 99, "status": "todo", "priority": "urgent", "due_date": "2026-06-01"}

    async def _fake_api_get(_path: str, *, params: dict | None = None) -> list:
        # same task returned by both queries
        return [shared_task]

    with patch("resources.task_resources.api_get", new=AsyncMock(side_effect=_fake_api_get)):
        result = await _high_priority()
    rows = json.loads(result)
    assert len([r for r in rows if r["id"] == 99]) == 1
