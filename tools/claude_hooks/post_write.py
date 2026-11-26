"""PostToolUse hook on Write and Edit: format what Claude just wrote, and note that the repo changed.

A `.py` file goes through `black -S`, then through the code-style check (`tools/check_code_style.py`), which
reports only violations that are new, so the old ones in `code_style_baseline.json` stay quiet. A
`frontend/*.js` file goes through Prettier, then ESLint. Whatever the file, the change is noted in a marker
file so the Stop gate knows to run. A tool that fails or is missing exits with code 2, which shows the
message to Claude.
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

# The checker lives in the repo, not next to this script, and the hook may run from any folder.
sys.path.insert(0, str(REPO_ROOT))

from tools import check_code_style  # noqa: E402

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


def style_failures(
    file_path: Path, root: Path | None = None, baseline_path: Path | None = None
) -> list[str]:
    """The code-style violations in one Python file that the baseline does not list, as one message."""
    try:
        violations = check_code_style.check_files([file_path], root=root)

    except (OSError, SyntaxError, ValueError) as error:
        return [f"the code-style check could not read {file_path.name}: {error}"]

    new_violations, _ = check_code_style.split_by_baseline(
        violations, check_code_style.load_baseline(baseline_path)
    )

    if not new_violations:
        return []

    listing = "\n".join(violation.render() for violation in new_violations)

    return [
        f"the code-style check found new violations in {file_path.name}:\n{listing}\n"
        "Fix them in the code; do not add them to tools/code_style_baseline.json."
    ]


def format_file(file_path: Path) -> list[str]:
    """Format one file; returns one message per tool that failed."""
    failures: list[str] = []

    if file_path.suffix == ".py":
        passed, output = run_tool([*black_command(), "-S", str(file_path)])

        if not passed:
            failures.append(f"black -S failed on {file_path.name}:\n{output}")

        else:
            failures.extend(style_failures(file_path))

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
