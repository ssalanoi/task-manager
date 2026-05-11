"""Focused tests for the `add_task` MCP tool.

The HTTP layer is stubbed via `patch("tools.tasks_crud.api_post", ...)`.
Tools are invoked through the FastMCP instance, not imported directly.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from tools import tasks_crud  # noqa: E402


@pytest.fixture()
def server() -> FastMCP:
    mcp = FastMCP(name="test")
    tasks_crud.register(mcp)
    return mcp


async def test_happy_path_all_fields(server: FastMCP) -> None:
    with patch(
        "tools.tasks_crud.api_post",
        new=AsyncMock(return_value={"id": 42}),
    ) as m:
        await server.call_tool(
            "add_task",
            {
                "title": "Write report",
                "description": "Quarterly summary",
                "status": "in_progress",
                "priority": "urgent",
                "due_date": "2026-12-31",
                "tags": ["a", "b"],
            },
        )
        m.assert_awaited_once()
        path, payload = m.await_args.args
        assert path == "/tasks"
        assert payload["title"] == "Write report"
        assert payload["description"] == "Quarterly summary"
        assert payload["status"] == "in_progress"
        assert payload["priority"] == "urgent"
        assert payload["due_date"] == "2026-12-31"
        assert payload["tags"] == ["a", "b"]


async def test_defaults_applied(server: FastMCP) -> None:
    with patch(
        "tools.tasks_crud.api_post",
        new=AsyncMock(return_value={"id": 1}),
    ) as m:
        await server.call_tool("add_task", {"title": "Just a title"})
        m.assert_awaited_once()
        _, payload = m.await_args.args
        assert payload["title"] == "Just a title"
        assert payload["status"] == "todo"
        assert payload["priority"] == "medium"
        assert payload["description"] is None
        assert payload["tags"] == []


async def test_tags_none_becomes_empty_list(server: FastMCP) -> None:
    with patch(
        "tools.tasks_crud.api_post",
        new=AsyncMock(return_value={"id": 2}),
    ) as m:
        await server.call_tool("add_task", {"title": "No tags", "tags": None})
        m.assert_awaited_once()
        _, payload = m.await_args.args
        assert payload["tags"] == []


async def test_title_too_long_rejected(server: FastMCP) -> None:
    long_title = "x" * 201
    with patch(
        "tools.tasks_crud.api_post",
        new=AsyncMock(return_value={"id": 3}),
    ) as m:
        with pytest.raises(Exception) as excinfo:
            await server.call_tool("add_task", {"title": long_title})
        assert "title" in str(excinfo.value).lower()
        m.assert_not_awaited()


async def test_empty_title_rejected(server: FastMCP) -> None:
    with patch(
        "tools.tasks_crud.api_post",
        new=AsyncMock(return_value={"id": 4}),
    ) as m:
        with pytest.raises(Exception) as excinfo:
            await server.call_tool("add_task", {"title": ""})
        assert "title" in str(excinfo.value).lower()
        m.assert_not_awaited()


async def test_invalid_priority_rejected(server: FastMCP) -> None:
    with patch(
        "tools.tasks_crud.api_post",
        new=AsyncMock(return_value={"id": 5}),
    ) as m:
        with pytest.raises(Exception) as excinfo:
            await server.call_tool(
                "add_task", {"title": "ok", "priority": "critical"}
            )
        assert "priority" in str(excinfo.value).lower()
        m.assert_not_awaited()
