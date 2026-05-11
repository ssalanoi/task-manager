"""Smoke tests for the MCP server's tool surface.

These tests stub the HTTP layer so they don't require a running backend.
They verify that:
 - register() wires up tools and resources without errors
 - tools translate inputs into the expected api_client calls
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from prompts import daily_plan, prioritize_tasks  # noqa: E402
from resources import task_resources  # noqa: E402
from tools import tasks_crud  # noqa: E402


@pytest.fixture()
def server() -> FastMCP:
    mcp = FastMCP(name="test")
    tasks_crud.register(mcp)
    task_resources.register(mcp)
    daily_plan.register(mcp)
    prioritize_tasks.register(mcp)
    return mcp


async def test_tools_listed(server: FastMCP) -> None:
    names = {t.name for t in await server.list_tools()}
    assert {"get_task", "get_all_tasks", "add_task", "update_task", "delete_task"} <= names


async def test_resources_listed(server: FastMCP) -> None:
    uris = {str(r.uri) for r in await server.list_resources()}
    assert {"tasks://all", "tasks://completed", "tasks://today", "tasks://in-progress"} <= uris


async def test_prompts_listed(server: FastMCP) -> None:
    names = {p.name for p in await server.list_prompts()}
    assert {"daily-plan", "prioritize-tasks"} <= names


async def test_add_task_calls_post(server: FastMCP) -> None:
    with patch("tools.tasks_crud.api_post", new=AsyncMock(return_value={"id": 1})) as m:
        result = await server.call_tool(
            "add_task", {"title": "x", "priority": "high"}
        )
        m.assert_awaited_once()
        path, payload = m.await_args.args
        assert path == "/tasks"
        assert payload["title"] == "x" and payload["priority"] == "high"
        # FastMCP wraps results; just confirm we got something truthy back.
        assert result is not None
