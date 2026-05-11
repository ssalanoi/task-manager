"""MCP tools that wrap the Task Manager REST API.

Each tool maps 1:1 to an HTTP endpoint. Tools are the ONLY way to mutate state.
Read-only listing is also exposed here as a tool (`get_task`, `get_all_tasks`)
to support id-based lookups; resources cover the standard browse views.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from api_client import api_delete, api_get, api_post, api_put

Status = Literal["todo", "in_progress", "done"]
Priority = Literal["low", "medium", "high", "urgent"]


class _AddTaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Status = "todo"
    priority: Priority = "medium"
    due_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD")
    tags: List[str] = Field(default_factory=list)


class _UpdatePatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[Status] = None
    priority: Optional[Priority] = None
    due_date: Optional[str] = None
    tags: Optional[List[str]] = None


def register(mcp: Any) -> None:
    """Register all CRUD tools on the given FastMCP instance."""

    @mcp.tool()
    async def get_task(id: int) -> dict:
        """Fetch a single task by id."""
        return await api_get(f"/tasks/{id}")

    @mcp.tool()
    async def get_all_tasks(
        status: Optional[Status] = None,
        priority: Optional[Priority] = None,
        tag: Optional[str] = None,
        due_before: Optional[str] = None,
        due_after: Optional[str] = None,
    ) -> dict:
        """List tasks with optional filters. Returns {"tasks": [...]}."""
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if priority is not None:
            params["priority"] = priority
        if tag is not None:
            params["tag"] = tag
        if due_before is not None:
            params["due_before"] = due_before
        if due_after is not None:
            params["due_after"] = due_after
        rows = await api_get("/tasks", params=params or None)
        return {"tasks": rows}

    @mcp.tool()
    async def add_task(
        title: str,
        description: Optional[str] = None,
        status: Status = "todo",
        priority: Priority = "medium",
        due_date: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """Create a new task. due_date must be today or in the future (YYYY-MM-DD)."""
        payload = _AddTaskInput(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags or [],
        ).model_dump(exclude_none=False)
        return await api_post("/tasks", payload)

    @mcp.tool()
    async def update_task(id: int, patch: dict) -> dict:
        """Update fields of an existing task. `patch` is a partial Task object."""
        clean = _UpdatePatch.model_validate(patch).model_dump(exclude_unset=True)
        return await api_put(f"/tasks/{id}", clean)

    @mcp.tool()
    async def delete_task(id: int) -> dict:
        """Delete a task by id. Returns {"deleted": true, "id": ...}."""
        return await api_delete(f"/tasks/{id}")
