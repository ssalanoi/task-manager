"""FastMCP server entrypoint for the Task Manager.

Run directly:        python mcp-server/server.py
Inspector:           npx @modelcontextprotocol/inspector python mcp-server/server.py
Claude Code:         claude mcp add task-manager -- python mcp-server/server.py

Required env vars:
  API_KEY        — must match the backend's API key
  API_BASE_URL   — defaults to http://localhost:8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow importing sibling modules (api_client, tools, resources, prompts) when
# the script is executed as a file rather than as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from prompts import daily_plan, prioritize_tasks  # noqa: E402
from resources import task_resources  # noqa: E402
from tools import tasks_crud  # noqa: E402

mcp = FastMCP(
    name="task-manager",
    instructions=(
        "Task Manager MCP. Use tools (add_task / update_task / delete_task / "
        "get_task / get_all_tasks) for any mutation or by-id lookup. Use "
        "resources (tasks://all, tasks://completed, tasks://today, "
        "tasks://in-progress) for read-only browsing. Prompts /daily-plan and "
        "/prioritize-tasks help plan and rank work."
    ),
)

tasks_crud.register(mcp)
task_resources.register(mcp)
daily_plan.register(mcp)
prioritize_tasks.register(mcp)


def main() -> None:
    # Default transport is stdio; the host (Claude Code, Inspector) drives I/O.
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
