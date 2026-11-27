"""Stop hook: the CI gate. Runs the checks that are fast enough for every finished reply.

It runs only when the PostToolUse hook noted that this session changed the repo. The checks
are `black -S --check .`, `npm run lint:js`, `npm run format:js:check`, `npm run test:js` and
`pytest -m "not browser"`. A sixth check runs the browser tests in parallel in Novita sandboxes
(`tools/sandbox_tests.py`, about 2.5 minutes), but only when a browser-relevant file was written this session
(`is_browser_relevant`). When that check cannot run at all (no API key, no SDK, no network), it ends with exit
code 3: the gate then only warns and does not block. A failing browser test blocks like any other check.

Once the checks have run, pass or fail, it also removes the cache files they leave behind
(`cache_files.py`: `__pycache__`, `__MACOSX` and `.DS_Store`).

When a check fails, the gate blocks once and lists the failed steps, so Claude carries on and fixes them.
When Claude Code reports `stop_hook_active` (the gate already blocked this turn), the gate never blocks
again: it only warns, so a check that cannot pass cannot loop forever.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cache_files import remove_cache_files
from hook_common import REPO_ROOT, marker_path, read_event, read_written_paths

# Tests replace the real checks with a JSON list of {"name": ..., "command": [...]}.
CHECKS_ENV_VAR = "LINES_SHINES_HOOK_CHECKS"

# Tests point the cleanup at a temporary folder, so no test deletes the real repo's cache files.
CLEAN_ROOT_ENV_VAR = "LINES_SHINES_HOOK_CLEAN_ROOT"
CHECK_TIMEOUT_SECONDS = 540
OUTPUT_TAIL_LINES = 25

# The sandbox check ends with this exit code when it could not run; the gate warns instead of blocking.
SANDBOX_UNAVAILABLE_EXIT_CODE = 3
SANDBOX_CHECK_NAME = "browser tests in Novita sandboxes"

# A write to one of these means the browser tests could be affected. Docs, playbook and preprocessing cannot.
BROWSER_RELEVANT_DIRECTORIES = ("frontend/", "database/", "config/", "teams/", "tests/")
BROWSER_RELEVANT_FILES = {
    "main.py",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
    "tools/sandbox_tests.py",
}
NODE_TESTS_DIRECTORY = "tests/js/"


def black_command() -> list[str]:
    """`black` from the path if there is one, else the black of the Python that runs this hook."""
    black_path = shutil.which("black")

    return [black_path] if black_path else [sys.executable, "-m", "black"]


def is_browser_relevant(relative_path: str) -> bool:
    """True when a write to this repo-relative path could change what the browser tests see."""
    if relative_path.startswith(NODE_TESTS_DIRECTORY):
        return False

    return relative_path in BROWSER_RELEVANT_FILES or relative_path.startswith(
        BROWSER_RELEVANT_DIRECTORIES
    )


def build_checks(include_sandbox: bool = False) -> list[dict]:
    """The checks to run, each with a name and the command line."""
    override = os.environ.get(CHECKS_ENV_VAR)

    if override:
        return json.loads(override)

    checks = [
        {
            "name": "black -S --check .",
            "command": [*black_command(), "-S", "--check", "."],
        },
        {"name": "npm run lint:js", "command": ["npm", "run", "lint:js"]},
        {
            "name": "npm run format:js:check",
            "command": ["npm", "run", "format:js:check"],
        },
        {"name": "npm run test:js", "command": ["npm", "run", "test:js"]},
        {
            "name": 'pytest -m "not browser"',
            "command": [
                sys.executable,
                "-m",
                "pytest",
                "-m",
                "not browser",
                "-q",
                "--tb=short",
            ],
        },
    ]

    if include_sandbox:
        checks.append(
            {
                "name": SANDBOX_CHECK_NAME,
                "command": [sys.executable, "-m", "tools.sandbox_tests"],
                "unavailable_exit_code": SANDBOX_UNAVAILABLE_EXIT_CODE,
            }
        )

    return checks


def run_check(check: dict) -> dict:
    """Run one check in the repo root; the result holds the name, whether it passed and the tail of its output."""
    try:
        result = subprocess.run(
            check["command"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS,
        )

    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "name": check["name"],
            "passed": False,
            "unavailable": False,
            "output": f"could not run: {error}",
        }

    output_lines = (result.stdout + result.stderr).strip().splitlines()

    return {
        "name": check["name"],
        "passed": result.returncode == 0,
        "unavailable": result.returncode == check.get("unavailable_exit_code"),
        "output": "\n".join(output_lines[-OUTPUT_TAIL_LINES:]),
    }


def describe_warnings(unavailable_results: list[dict]) -> str:
    """The warning for checks that could not run: each with the tail of its output; empty when there are none."""
    return "\n".join(
        f"WARNING: [{result['name']}] could not run, so it did not check anything:\n{result['output']}"
        for result in unavailable_results
    )


def describe_failures(
    failed_results: list[dict], unavailable_results: list[dict], sandbox_included: bool
) -> str:
    """The text Claude reads: each failed step with the tail of its output, then any warnings."""
    lines = ["The CI gate failed. Fix these, then finish:"]

    for result in failed_results:
        lines.append(f"\n[{result['name']}]\n{result['output']}")

    if unavailable_results:
        lines.append("\n" + describe_warnings(unavailable_results))

    if sandbox_included:
        lines.append(
            "\nThe browser tests ran in Novita sandboxes unless a warning above says they could not; "
            "say which in the report."
        )

    else:
        lines.append(
            "\nThe gate did not run the browser tests (no browser-relevant file was written); say so in the report. "
            "The owner runs the full `pytest -v` locally."
        )

    return "\n".join(lines)


def main() -> None:
    event = read_event()
    marker = marker_path(event.get("session_id") or "")

    if not marker.exists():
        return

    written_paths = read_written_paths(marker)
    sandbox_included = any(is_browser_relevant(path) for path in written_paths)

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(run_check, build_checks(sandbox_included)))

    # After the checks, never during them: they are what write the cache files.
    remove_cache_files(Path(os.environ.get(CLEAN_ROOT_ENV_VAR) or REPO_ROOT))

    unavailable_results = [result for result in results if result["unavailable"]]
    failed_results = [
        result
        for result in results
        if not result["passed"] and not result["unavailable"]
    ]

    if not failed_results:
        marker.unlink(missing_ok=True)

        if unavailable_results:
            message = (
                "LinesShines CI gate passed, with a warning.\n"
                + describe_warnings(unavailable_results)
            )
            print(json.dumps({"systemMessage": message}))

        return

    description = describe_failures(
        failed_results, unavailable_results, sandbox_included
    )

    if event.get("stop_hook_active"):
        # The gate already blocked once this turn; warn the owner and let Claude stop.
        print(
            json.dumps(
                {
                    "systemMessage": "LinesShines CI gate is still failing.\n"
                    + description
                }
            )
        )

        return

    print(json.dumps({"decision": "block", "reason": description}))


if __name__ == "__main__":
    main()
