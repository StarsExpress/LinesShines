"""PostToolUse hook on Write and Edit: format what Claude just wrote, and note that the repo changed.

A `.py` file goes through `black -S`. A `frontend/*.js` file goes through Prettier, then ESLint.
Whatever the file, the change is noted in a marker file so the Stop gate knows to run.
A formatter that fails or is missing exits with code 2, which shows the message to Claude.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from hook_common import (
    REPO_ROOT,
    block,
    file_path_of,
    is_under_repo,
    marker_path,
    read_event,
)

FRONTEND_DIR = REPO_ROOT / "frontend"
VENDOR_DIR = FRONTEND_DIR / "vendor"
TOOL_TIMEOUT_SECONDS = 120


def black_command() -> list[str]:
    """`black` from the path if there is one, else the black of the Python that runs this hook."""
    black_path = shutil.which("black")

    return [black_path] if black_path else [sys.executable, "-m", "black"]


def run_tool(command: list[str]) -> tuple[bool, str]:
    """Run one tool in the repo root; returns whether it passed and its output."""
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
        )

    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"could not run {' '.join(command)}: {error}"

    return result.returncode == 0, (result.stdout + result.stderr).strip()


def is_formatted_javascript(file_path: Path) -> bool:
    """A repo script under frontend/ that Prettier and ESLint cover (vendor/ is ignored)."""
    return (
        file_path.suffix == ".js"
        and FRONTEND_DIR in file_path.parents
        and VENDOR_DIR not in file_path.parents
    )


def format_file(file_path: Path) -> list[str]:
    """Format one file; returns one message per tool that failed."""
    failures: list[str] = []

    if file_path.suffix == ".py":
        passed, output = run_tool([*black_command(), "-S", str(file_path)])

        if not passed:
            failures.append(f"black -S failed on {file_path.name}:\n{output}")

    elif is_formatted_javascript(file_path):
        passed, output = run_tool(
            ["npx", "--no-install", "prettier", "--write", str(file_path)]
        )

        if not passed:
            failures.append(f"prettier failed on {file_path.name}:\n{output}")

        passed, output = run_tool(["npx", "--no-install", "eslint", str(file_path)])

        if not passed:
            failures.append(f"eslint failed on {file_path.name}:\n{output}")

    return failures


def main() -> None:
    event = read_event()
    file_path = file_path_of(event)

    if file_path is None or not is_under_repo(file_path):
        return

    # The Stop gate runs only for sessions that changed the repo.
    marker = marker_path(event.get("session_id") or "")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()

    if not file_path.is_file():
        return

    failures = format_file(file_path)

    if failures:
        block(
            "The LinesShines hook found a problem after this write. Fix it:\n"
            + "\n".join(failures)
        )


if __name__ == "__main__":
    main()
