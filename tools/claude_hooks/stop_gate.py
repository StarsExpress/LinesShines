"""Stop hook: the CI gate. Runs the checks that are fast enough for every finished reply.

It runs only when the PostToolUse hook noted that this session changed the repo. The checks
are `black -S --check .`, `npm run lint:js`, `npm run format:js:check` and `pytest -m "not browser"`.
The browser tests take about ten minutes, so they stay the owner's local run.

When a check fails, the gate blocks once and lists the failed steps, so Claude carries on and fixes them.
When Claude Code reports `stop_hook_active` (the gate already blocked this turn), the gate never blocks
again: it only warns, so a check that cannot pass cannot loop for ever.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from hook_common import REPO_ROOT, marker_path, read_event

# Tests replace the real checks with a JSON list of {"name": ..., "command": [...]}.
CHECKS_ENV_VAR = "LINES_SHINES_HOOK_CHECKS"
CHECK_TIMEOUT_SECONDS = 540
OUTPUT_TAIL_LINES = 25


def black_command() -> list[str]:
    """`black` from the path if there is one, else the black of the Python that runs this hook."""
    black_path = shutil.which("black")

    return [black_path] if black_path else [sys.executable, "-m", "black"]


def build_checks() -> list[dict]:
    """The checks to run, each with a name and the command line."""
    override = os.environ.get(CHECKS_ENV_VAR)

    if override:
        return json.loads(override)

    return [
        {
            "name": "black -S --check .",
            "command": [*black_command(), "-S", "--check", "."],
        },
        {"name": "npm run lint:js", "command": ["npm", "run", "lint:js"]},
        {
            "name": "npm run format:js:check",
            "command": ["npm", "run", "format:js:check"],
        },
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
            "output": f"could not run: {error}",
        }

    output_lines = (result.stdout + result.stderr).strip().splitlines()

    return {
        "name": check["name"],
        "passed": result.returncode == 0,
        "output": "\n".join(output_lines[-OUTPUT_TAIL_LINES:]),
    }


def describe_failures(failed_results: list[dict]) -> str:
    """The text Claude reads: each failed step with the tail of its output."""
    lines = ["The CI gate failed. Fix these, then finish:"]

    for result in failed_results:
        lines.append(f"\n[{result['name']}]\n{result['output']}")

    lines.append(
        "\nThe gate skips the browser tests; say so in the report. "
        "The owner runs the full `pytest -v` locally."
    )

    return "\n".join(lines)


def main() -> None:
    event = read_event()
    marker = marker_path(event.get("session_id") or "")

    if not marker.exists():
        return

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(run_check, build_checks()))

    failed_results = [result for result in results if not result["passed"]]

    if not failed_results:
        marker.unlink(missing_ok=True)

        return

    description = describe_failures(failed_results)

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
