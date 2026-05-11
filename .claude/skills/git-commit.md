---
name: git-commit
description: Draft a Conventional Commits message from staged changes, optionally invoke the code-reviewer sub-agent, then run `git commit` after the user confirms. Use after `git add` when the user wants to commit.
---

# /git-commit

Procedure (follow exactly):

1. Run `git diff --cached --stat` and `git diff --cached` to inspect staged changes. If nothing is staged, ask the user what to stage and stop.
2. Run `git status --short` to confirm there are no unintended unstaged changes the user expected to include.
3. (Optional but recommended) Delegate to the **code-reviewer** sub-agent with the staged diff. If it reports blocking issues, surface them and stop — do not commit.
4. Draft a Conventional Commits message:
   - format: `type(scope): subject` (subject ≤ 72 chars, imperative mood)
   - allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`
   - infer scope from top-level folder touched (`backend`, `mcp`, `hooks`, `skills`, `agents`, `docs`)
   - add a body only if the change is non-trivial; explain *why*, not *what*
5. Show the message to the user and ask for confirmation before committing.
6. On confirm: run
   ```
   git commit -m "<subject>" -m "<body if any>"
   ```
   Use a HEREDOC (multi-`-m`) — never embed newlines inside a single `-m` string.
7. Run `git log -1 --oneline` to confirm and report the result.

Hard rules:
- NEVER pass `--no-verify`.
- NEVER amend an existing commit unless the user explicitly asks.
- NEVER `git push`. Stop at the local commit.
