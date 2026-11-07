# test_hooks.py

> **Add tests here when:** changing a script in `tools/claude_hooks/` (what a hook blocks, asks, prints or marks) or `tools/install_claude_hooks.py` (what it writes into, keeps in and removes from the settings file).

- **Kind:** pure Python. Each hook runs as a subprocess with one JSON event on stdin, the way Claude Code runs it; the installer is imported and called on plain dicts.
- **Needs:** nothing. The marker folder is a temporary folder (`LINES_SHINES_HOOK_STATE_DIR`) and the gate's checks are replaced by tiny Python commands (`LINES_SHINES_HOOK_CHECKS`), so no test touches the real settings, black, npm or the real CI set.
- **Covers:** the Bash hook (forbidden programs, look-alike words that pass, the one `pkill`, other projects left alone); the write hook (csv/xlsx refused, discussions asked, relative paths); the post-write marker; the Stop gate (silent without a marker, blocks and names the failed step, never blocks when `stop_hook_active`, clears the marker, a missing program fails); the SessionStart text and its working-directory rule; the installer (all hooks written, idempotent, foreign hooks and settings kept, remove, broken or missing settings file).
- **Not here:** that Claude Code really calls the hooks and reads their output the way the official documentation says (only a real session shows that); the formatters themselves (black, Prettier, ESLint are not run); the `browser` marker, which `pytest -m browser --collect-only` shows.
- **Known gaps:** `post_write.py` never runs a formatter in a test, so a broken tool call line is not caught there.
