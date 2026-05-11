# Task Manager (AI-native, MCP-based)

A Task Manager you drive entirely through Claude Code.

```
Claude Code  ──MCP/stdio──▶  Python MCP server  ──HTTPS + X-API-Key──▶  FastAPI backend  ─▶  SQLite
```

**Why MCP and not direct HTTP?** Claude can discover tools / resources / prompts automatically, validate inputs against typed schemas, and keep the API key out of its own context. The same MCP server works in Claude Desktop, MCP Inspector, and any other MCP host.

## Repository layout

```
task-manager/
├── backend/                 FastAPI + SQLModel + SQLite
│   ├── app/                 main, models, schemas, auth, routers/tasks.py
│   └── tests/               pytest with TestClient
├── mcp-server/              FastMCP server
│   ├── server.py            entrypoint (stdio)
│   ├── api_client.py        single source of the X-API-Key
│   ├── tools/tasks_crud.py  add/get/update/delete + filtered list
│   ├── resources/           tasks://all, completed, today, in-progress
│   ├── prompts/             /daily-plan, /prioritize-tasks
│   └── tests/
├── .claude/
│   ├── settings.json        wires the hooks
│   ├── skills/              /git-commit, /add-test
│   └── agents/              code-reviewer, test-writer
├── hooks/
│   ├── precheck_secrets.py  PreToolUse — blocks secret leaks
│   ├── post_edit.ps1        PostToolUse — ruff + black + pytest (Windows)
│   └── post_edit.sh         POSIX mirror
├── CLAUDE.md
└── README.md  (this file)
```

## Prerequisites

- Python **3.11+**
- Node + npx (only for MCP Inspector)
- [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI
- `pip` (or `uv`) and `git`

## Installation (Windows / PowerShell)

```powershell
git clone <repo> task-manager
cd task-manager

python -m venv .venv
./.venv/Scripts/Activate.ps1

pip install -e ./backend[dev]
pip install -e ./mcp-server[dev]

Copy-Item backend\.env.example backend\.env
```

POSIX:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ./backend[dev] -e ./mcp-server[dev]
cp backend/.env.example backend/.env
```

## Step 1 — Run the backend

Открой **первый терминал** и выполни:

```powershell
cd C:\Work\task-manager
.\.venv\Scripts\Activate.ps1
$env:API_KEY = "dev-secret-123"
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Процесс остаётся запущенным. Проверь: открой http://localhost:8000/docs, нажми **Authorize**, введи `dev-secret-123`.

Запуск тестов (в отдельном терминале с активированным venv):
```powershell
pytest -q backend/tests
```

## Step 2 — Run the MCP server (прямой запуск)

Прямой запуск для отладки (stdio, завершить Ctrl+C):

```powershell
cd C:\Work\task-manager
.\.venv\Scripts\Activate.ps1
$env:API_KEY = "dev-secret-123"
$env:API_BASE_URL = "http://localhost:8000"
python mcp-server/server.py
```

## Step 3 — Validate with MCP Inspector

> **Важно для Windows:** MCP Inspector v0.21 некорректно обрабатывает Windows-пути с `C:\` в поле Arguments. Обходное решение — использовать `python` как команду (без пути) и добавить venv в `PATH` перед запуском Inspector.

Открой **новый терминал** (бэкенд должен быть запущен в другом):

```powershell
cd C:\Work\task-manager
.\.venv\Scripts\Activate.ps1
$env:PATH = "C:\Work\task-manager\.venv\Scripts;" + $env:PATH
$env:API_KEY = "dev-secret-123"
$env:API_BASE_URL = "http://localhost:8000"
& "C:\Program Files\nodejs\npx.cmd" "@modelcontextprotocol/inspector" python "mcp-server/server.py"
```

Inspector напечатает URL вида `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...` и откроет браузер автоматически.

**В браузере:**
- Поля Command / Arguments уже заполнены (`python` / `mcp-server/server.py`) — **не меняй их**
- Нажми **Connect**

### Чеклист проверки в Inspector

**Tools tab** — вызови каждый инструмент:
1. `add_task` → `{"title": "Test task", "priority": "high"}` — должен вернуть объект с `id`
2. `get_task` → `{"id": <id из шага 1>}` — должен вернуть тот же объект
3. `get_all_tasks` → `{"status": "todo"}` — должен содержать созданную задачу
4. `update_task` → `{"id": <id>, "patch": {"status": "done"}}` — статус обновлён
5. `delete_task` → `{"id": <id>}` — возвращает `{"deleted": true}`; повторный `get_task` → 404

**Resources tab** — прочитай каждый ресурс:
- `tasks://all` — все задачи
- `tasks://completed` — только `status=done`
- `tasks://today` — открытые задачи на сегодня / просроченные
- `tasks://in-progress` — только `status=in_progress`

**Prompts tab:**
- `daily-plan` — текст промпта со ссылками на ресурсы
- `prioritize-tasks` — текст с правилами сортировки

**Негативный тест:** в терминале с Inspector замени `$env:API_KEY = "wrong"` и нажми Connect — инструменты должны вернуть ошибку 401.

## Step 4 — Connect to Claude Code

```powershell
cd C:\Work\task-manager
claude mcp add task-manager `
  --env API_KEY=dev-secret-123 `
  --env API_BASE_URL=http://localhost:8000 `
  -- C:/Work/task-manager/.venv/Scripts/python.exe C:/Work/task-manager/mcp-server/server.py
```

> **Важно:** команду нужно выполнять из папки `C:\Work\task-manager` и использовать **полный путь к venv python** — иначе Claude Code возьмёт системный Python без установленного `mcp`.

Открой проект в Claude Code, выполни `/mcp` — должен появиться `task-manager`. Попробуй:

- *"Добавь задачу написать отчёт до пятницы, приоритет высокий."*
- *"Что мне сделать сегодня?"* (Claude использует `/daily-plan`)
- `/prioritize-tasks`

## Development workflow

1. `.\.venv\Scripts\Activate.ps1`
2. Редактируй `.py` файлы. Хук **PostToolUse** автоматически запускает `ruff --fix`, `black` и соответствующий `pytest`.
3. После добавления новой функции выполни `/add-test path/to/file.py::name`. Агент `test-writer` создаст pytest-файл; хук запустит тесты.
4. Зафиксируй изменения: `git add <paths>`, затем `/git-commit`. Skill вызывает агент `code-reviewer` и при успехе создаёт коммит в формате Conventional Commits.

Хук **PreToolUse** (`hooks/precheck_secrets.py`) блокирует любое изменение файла, содержащее литеральный API-ключ, AWS-ключ, GitHub PAT или приватный ключ. Используй `os.getenv("API_KEY", "dev-secret-123")`.

## Troubleshooting

| Симптом | Причина | Решение |
| --- | --- | --- |
| MCP Inspector: путь сломан (`Worktask-manager...`) | Inspector v0.21 не обрабатывает Windows-пути с `C:\` | Добавь venv в `$env:PATH` и используй `python` + относительный путь как показано в Step 3 |
| `401 Missing or invalid API key` из MCP-инструментов | `API_KEY` не установлен или не совпадает с бэкендом | Установи одинаковое значение в обоих терминалах |
| `tasks://today` возвращает пустой массив | Все открытые задачи не имеют `due_date` или уже `done` | Добавь задачу с `due_date` |
| `claude mcp list` показывает `Failed to connect` | Claude Code берёт системный Python без `mcp` | Используй полный путь к venv: `C:/Work/task-manager/.venv/Scripts/python.exe` |
| Pre-edit хук блокирует легитимную запись | Ложное срабатывание паттерна | Читай из `os.getenv(...)`; allowlist это покрывает |
| `pytest` не запускается из post-edit хука | Инструменты не установлены в активном venv | `pip install -e ./backend[dev] -e ./mcp-server[dev]` |

## License

MIT (or whichever the assignment specifies).
