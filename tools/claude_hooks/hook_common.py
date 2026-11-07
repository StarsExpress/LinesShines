"""Shared helpers for the Claude Code hooks of this repo.

Every hook script in this folder is registered in the user-level Claude Code settings
(see `tools/install_claude_hooks.py`), so it fires in every project on the computer.
The helpers below let a script find the repo from its own location and decide whether
an action concerns LinesShines at all; an action that does not is passed untouched.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# tools/claude_hooks/hook_common.py -> the repo root is two folders up.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Tests point this at a temporary folder; otherwise the markers live in the system temp folder.
STATE_DIR_ENV_VAR = "LINES_SHINES_HOOK_STATE_DIR"

FILE_TOOL_NAMES = {"Write", "Edit", "MultiEdit"}


def read_event() -> dict:
    """Read the JSON that Claude Code sends on stdin; an empty or broken input gives {}."""
    try:
        event = json.load(sys.stdin)

    except (json.JSONDecodeError, OSError):
        return {}

    return event if isinstance(event, dict) else {}


def resolve_path(path_text: str, working_directory: str) -> Path:
    """Turn a path from a tool call into an absolute one, relative paths starting at the cwd."""
    path = Path(path_text).expanduser()

    if not path.is_absolute():
        path = Path(working_directory or ".") / path

    return path.resolve()


def is_under_repo(path: Path) -> bool:
    """True when the path is the repo root or anything inside it."""
    return path == REPO_ROOT or REPO_ROOT in path.parents


def file_path_of(event: dict) -> Path | None:
    """The absolute file a Write or Edit call targets, or None when the call names none."""
    file_path_text = (event.get("tool_input") or {}).get("file_path")

    if not file_path_text:
        return None

    return resolve_path(file_path_text, event.get("cwd") or "")


def command_concerns_repo(command: str, working_directory: str) -> bool:
    """True when a Bash call works in the repo, or names it (an absolute path or a `cd` by folder name)."""
    if working_directory and is_under_repo(resolve_path(working_directory, "")):
        return True

    # The folder name catches `cd lines_shines && ...` started from the parent folder.
    return (
        str(REPO_ROOT) in command
        or re.search(rf"\b{re.escape(REPO_ROOT.name)}\b", command) is not None
    )


def session_concerns_repo(working_directory: str) -> bool:
    """True when the session starts in the repo, inside it, or in the folder directly above it."""
    if not working_directory:
        return False

    start_path = resolve_path(working_directory, "")

    return is_under_repo(start_path) or start_path == REPO_ROOT.parent


def marker_path(session_id: str) -> Path:
    """The file that says the repo changed during this session; the Stop gate reads it."""
    state_dir = Path(
        os.environ.get(STATE_DIR_ENV_VAR)
        or Path(tempfile.gettempdir()) / "lines_shines_hooks"
    )
    safe_session_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")

    return state_dir / f"{safe_session_id}.changed"


def block(reason: str) -> None:
    """Refuse the action: exit code 2 sends the reason back to Claude."""
    print(reason, file=sys.stderr)
    sys.exit(2)
