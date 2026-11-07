# Claude Code hooks

> **Load when:** changing a script in `tools/claude_hooks/`, `tools/install_claude_hooks.py`, the `browser` test marker, or the working rules the hooks enforce.

The working rules of `INVARIANTS.md` are enforced by Claude Code hooks on the owner's computer, so a machine checks them instead of Claude's own care. The hooks are for Claude Code running locally; sessions that reach the computer through an MCP tool are out of scope, and GitHub Actions keeps running the full CI set on every push whatever the local gate skips.

## Where they live

- **Scripts:** `tools/claude_hooks/`, plain Python with the standard library only. They are tracked in git (`.claude/` is local only, so it cannot hold them).
- **Registration:** `python -m tools.install_claude_hooks` writes pointers (the Python that ran it plus an absolute script path) into the user-level `~/.claude/settings.json`, so the hooks fire in every directory, not only in the repo. `--remove` takes them out; both touch only their own entries and are idempotent. Run it with the Python that has `black` and `pytest`, because the hooks reuse that interpreter. Commands are in `COMMANDS.md`.
- **Which project:** a script finds the repo root from its own location, never from the working directory. It first decides whether the action concerns LinesShines: a file tool when the path is under the repo; a Bash call when its working directory is under the repo or the command contains the repo path or the repo folder name. Anything else passes untouched.

## The hooks

| Script | Event and matcher | What it does |
|---|---|---|
| `session_start.py` | `SessionStart`, `compact\|resume` | Prints the "Working rules" section of `INVARIANTS.md` and the names in `next_steps/` into the context. Only when the session starts in the repo, inside it, or in the folder directly above it. |
| `pre_bash.py` | `PreToolUse`, `Bash` | Exit code 2 when the command contains `git`, `railway`, `psql` or `pkill` as a word (`.gitignore`, `.github`, `.git/config` pass). One exception: the whole command is `pkill -f "uvicorn main:app ..."` with no `;`, `&&`, `\|`, backtick or `$(`. |
| `pre_write.py` | `PreToolUse`, `Write\|Edit\|MultiEdit` | Exit code 2 for a `.csv` or `.xlsx` inside the repo (invariant 13). A write under `playbook/discussions/` returns `permissionDecision: "ask"`. |
| `post_write.py` | `PostToolUse`, `Write\|Edit\|MultiEdit` | `black -S` after a `.py`; Prettier then ESLint after a `frontend/*.js` (not `vendor/`). Touches the session marker. A failing or missing formatter exits with code 2 and the message reaches Claude. |
| `stop_gate.py` | `Stop` | The CI gate, below. |

`hook_common.py` holds what they share (repo root, "does this concern the repo", marker path).

## The CI gate

- Runs only when the session marker exists, i.e. `post_write.py` saw a write under the repo. A session that only answered questions runs nothing. The marker is a file in the system temp folder keyed by session id.
- Checks, run in parallel: `black -S --check .`, `npm run lint:js`, `npm run format:js:check`, `pytest -m "not browser"`.
- **The browser tests are not run.** `tests/conftest.py` adds the marker `browser` (registered in `pytest.ini`) to every test whose fixtures include `page`, `live_server_url`, `chromium_browser` or `open_page`, directly or through another fixture, so a new browser test is marked on its own. The full `pytest -v` takes about ten minutes and stays the owner's local run.
- On failure it answers `{"decision": "block", "reason": ...}` with each failed step and the tail of its output, and Claude carries on. When Claude Code sends `stop_hook_active`, the gate has already blocked this turn: it runs the checks again but only warns (`systemMessage`) and lets Claude stop, so a check that cannot pass cannot loop. The marker stays while the repo is red and is deleted when every check passes.
- A program that is missing counts as a failed step.

## Gotchas

- Exit code 2 is the only way these scripts refuse; any other non-zero exit is a non-blocking error that Claude Code ignores.
- JSON must go to stdout with nothing before it, and fields such as `permissionDecision` belong inside `hookSpecificOutput`; a misplaced field is ignored without an error (`claude --debug` logs it).
- `SessionStart` output is capped by Claude Code at 10,000 characters; the script cuts at 9,500.
- `tests/test_hooks.py` replaces the gate's checks with the environment variable `LINES_SHINES_HOOK_CHECKS` and the marker folder with `LINES_SHINES_HOOK_STATE_DIR`. Those two are test seams, not settings.
- To change a hook, edit the script here; the registered pointer needs no change. To add or retarget a hook, change `HOOK_DEFINITIONS` in `tools/install_claude_hooks.py` and run the installer again.
