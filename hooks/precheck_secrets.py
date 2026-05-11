"""PreToolUse hook: block edits that introduce hard-coded secrets.

Claude Code invokes this with hook input on stdin (JSON). For Edit/Write/MultiEdit
tools we inspect the proposed `new_string` / `content` and exit 2 if a secret
pattern matches — that exit code blocks the tool call.

Allowlist:
  - the dev placeholder `dev-secret-123`
  - the literal string `os.getenv(` on the same line (config plumbing)
"""
from __future__ import annotations

import json
import re
import sys
from typing import Iterable

# Patterns we treat as likely real secrets.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api-key", re.compile(r"""(?i)\bapi[_-]?key\b\s*[:=]\s*["'][A-Za-z0-9_\-]{8,}["']""")),
    ("aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer", re.compile(r"""\bBearer\s+[A-Za-z0-9._\-]{20,}""")),
    ("github-pat", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("slack", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b")),
]

ALLOWLIST_VALUES = {"dev-secret-123", "test-key-xyz"}


def _candidate_strings(payload: dict) -> Iterable[str]:
    """Pull the user-controllable text out of the tool input."""
    inp = payload.get("tool_input") or {}
    for key in ("new_string", "content"):
        v = inp.get(key)
        if isinstance(v, str):
            yield v
    # MultiEdit ships a list of edits.
    for edit in inp.get("edits") or []:
        v = edit.get("new_string")
        if isinstance(v, str):
            yield v


def _line_is_allowlisted(line: str) -> bool:
    if any(token in line for token in ALLOWLIST_VALUES):
        return True
    if "os.getenv(" in line or "os.environ" in line:
        return True
    return False


def scan(text: str) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _line_is_allowlisted(line):
            continue
        for label, pat in PATTERNS:
            if pat.search(line):
                hits.append((label, lineno, line.strip()[:160]))
                break
    return hits


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # If we can't parse, don't block — just exit 0.
        return 0

    tool = payload.get("tool_name", "")
    if tool not in {"Edit", "Write", "MultiEdit"}:
        return 0

    all_hits: list[tuple[str, int, str]] = []
    for chunk in _candidate_strings(payload):
        all_hits.extend(scan(chunk))

    if not all_hits:
        return 0

    msg_lines = ["BLOCKED: potential secret detected. Use os.getenv(...) instead."]
    for label, lineno, line in all_hits[:5]:
        msg_lines.append(f"  [{label}] line {lineno}: {line}")
    print("\n".join(msg_lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
