@echo off
REM Wrapper for MCP Inspector — uses venv python, sets required env vars.
REM Point Inspector Command to this file, leave Arguments empty.
set API_KEY=dev-secret-123
set API_BASE_URL=http://localhost:8000
"C:\Work\task-manager\.venv\Scripts\python.exe" "C:\Work\task-manager\mcp-server\server.py"
