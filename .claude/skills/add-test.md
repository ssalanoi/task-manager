---
name: add-test
description: Generate a pytest skeleton for a target function or module — happy path plus 1–2 edge cases. Use after implementing a new function, or when the user asks for test coverage on existing code. Argument format `path/to/file.py::function_name` or just `path/to/file.py`.
---

# /add-test

Procedure (follow exactly):

1. Parse the argument:
   - `path/to/file.py::name` -> target a single function
   - `path/to/file.py`       -> target every public function in the module
2. Read the target file with the Read tool. Identify:
   - public callables (no leading `_`)
   - their signatures, type hints, docstrings
   - whether they're sync or async
   - external dependencies (HTTP client, DB session, env vars) that need stubbing
3. Decide the test file path:
   - Prefer the project's existing convention (`backend/tests/test_<module>.py`, `mcp-server/tests/test_<module>.py`).
   - Mirror the source layout when no test exists yet.
4. Delegate the heavy lifting to the **test-writer** sub-agent. Pass it:
   - the absolute target path (and function name if any)
   - the chosen test file path
   - the project's testing conventions (pytest + pytest-asyncio, FastAPI `TestClient` for backend, in-process FastMCP harness for MCP)
5. After the sub-agent writes the file, run `pytest -q <test_file>` and report the result. If anything fails, iterate.

For each tested function, ensure coverage of:
- happy path with realistic inputs
- one edge case (boundary, empty input, or invalid type)
- one error path (HTTP non-2xx, raised exception, missing auth) where applicable

Do not modify production code from this skill.
