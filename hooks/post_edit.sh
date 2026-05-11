#!/usr/bin/env bash
# PostToolUse hook (POSIX mirror of post_edit.ps1).
set -u

payload=$(cat)
[ -z "$payload" ] && exit 0

# Cheap JSON extraction — avoids a hard jq dependency.
extract() {
  python3 - "$1" <<'PY' "$payload"
import json, sys
key = sys.argv[1]
try:
    obj = json.loads(sys.stdin.read() if False else sys.argv[2])
except Exception:
    sys.exit(0)
def walk(o, path):
    cur = o
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return ""
        cur = cur[p]
    return cur if isinstance(cur, str) else ""
print(walk(obj, key.split(".")))
PY
}

tool=$(extract tool_name)
case "$tool" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

file=$(extract tool_input.file_path)
[ -z "$file" ] && exit 0
case "$file" in *.py) ;; *) exit 0 ;; esac
[ ! -f "$file" ] && exit 0

repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo" || exit 0

failed=0

if command -v ruff >/dev/null 2>&1; then
  ruff check --fix "$file" || failed=1
fi
if command -v black >/dev/null 2>&1; then
  black -q "$file" || failed=1
fi

if command -v pytest >/dev/null 2>&1; then
  case "$file" in
    backend/*)    [ -d backend/tests ]    && pytest -q backend/tests    || failed=$? ;;
    mcp-server/*) [ -d mcp-server/tests ] && pytest -q mcp-server/tests || failed=$? ;;
  esac
fi

[ "$failed" -ne 0 ] && exit 2
exit 0
