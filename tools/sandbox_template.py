"""Build the Novita sandbox template the browser tests start from: Python 3.12, Playwright with Chromium, the requirements.

    python -m tools.sandbox_template                  # build `lines-shines-browser`, tagged with today's date and `latest`
    python -m tools.sandbox_template --no-cache       # ignore the layer cache (much slower)
    python -m tools.sandbox_template --name other     # another template name

Rebuild it when Playwright's version changes: the Chromium in the template has to match the installed Playwright, and
its folder is read-only for the sandbox user, so nothing can install a newer one at run time. Rebuilding because
`requirements*.txt` changed is optional: `tools/sandbox_tests.py` runs `pip install -r` in every sandbox anyway.

The API key and the exit codes are the same as in `tools/sandbox_tests.py` (0 built, 1 build failed, 3 could not run).
Start the result as `lines-shines-browser:latest` (the bare name returned a 404). Templates are deleted by hand in the
console or with `novita.template.delete(id)`; deleting is permanent. How it works and why: `playbook/architecture/SANDBOX.md`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

from tools.sandbox_tests import (
    DEFAULT_TEMPLATE,
    EXIT_PASSED,
    EXIT_TESTS_FAILED,
    EXIT_UNAVAILABLE,
    REPO_ROOT,
    Unavailable,
    connect,
)

# Has to match the Python of the CI jobs in .github/workflows/ci.yml; a test checks it.
PYTHON_VERSION = "3.12"
TEMPLATE_NAME = DEFAULT_TEMPLATE.split(":")[0]
LATEST_TAG = "latest"
CPU_COUNT = 2
MEMORY_MB = 4096

# Chromium goes where every user can read it, and the sandbox keeps the setting at run time.
BROWSERS_PATH = "/opt/ms-playwright"
REQUIREMENTS_DIRECTORY = "/opt/lines-shines"
REQUIREMENT_FILES = ["requirements.txt", "requirements-dev.txt"]


def browser_template() -> Any:
    """The template definition: layers ordered slowest-changing first, so a cache hit skips the expensive ones."""
    try:
        from novita_sandbox import Template

    except ImportError as error:
        raise Unavailable(
            "the novita-sandbox package is not installed (pip install -r requirements-sandbox.txt)"
        ) from error

    requirements = " ".join(
        f"-r {REQUIREMENTS_DIRECTORY}/{name}" for name in REQUIREMENT_FILES
    )

    return (
        Template(file_context_path=REPO_ROOT)
        .from_python_image(PYTHON_VERSION)
        .set_user("root")
        .set_envs({"PLAYWRIGHT_BROWSERS_PATH": BROWSERS_PATH}, runtime=True)
        # Playwright and its Chromium first: the range pinned in requirements-dev.txt is already satisfied afterwards.
        .run_cmd("python -m pip install --no-cache-dir playwright")
        .run_cmd("python -m playwright install --with-deps chromium")
        # Then the requirements, which change more often.
        .copy(REQUIREMENT_FILES, f"{REQUIREMENTS_DIRECTORY}/")
        .run_cmd(f"python -m pip install --no-cache-dir {requirements}")
        .set_user("user")
    )


def build_tags(today: date) -> list[str]:
    """A date tag and `latest` on every build, so a bad build can be left behind by naming the earlier one."""
    return [today.isoformat(), LATEST_TAG]


def print_log(entry: Any) -> None:
    """Show one build log line."""
    print(f"[{entry.level}] {entry.message}", flush=True)


def build(name: str, skip_cache: bool) -> int:
    """Build and tag the template; the build log streams to the terminal."""
    novita = connect()
    template = browser_template()
    tags = build_tags(date.today())
    print(
        f"building {name} (tags: {', '.join(tags)}, cache: {not skip_cache})",
        flush=True,
    )

    info = novita.template.build(
        template,
        name,
        tags=tags,
        cpu_count=CPU_COUNT,
        memory_mb=MEMORY_MB,
        skip_cache=skip_cache,
        on_build_logs=print_log,
    )
    print(
        f"\nbuilt: template_id={info.template_id} build_id={info.build_id} name={info.name} tags={info.tags}"
    )
    print(f"start it as {name}:{LATEST_TAG}")

    return EXIT_PASSED


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the Novita sandbox template for the browser tests."
    )
    parser.add_argument("--name", default=TEMPLATE_NAME, help="template name")
    parser.add_argument(
        "--no-cache", action="store_true", help="ignore the layer cache (much slower)"
    )
    options = parser.parse_args(arguments)

    try:
        return build(options.name, options.no_cache)

    except Unavailable as error:
        print(f"RESULT: UNAVAILABLE: {error}")

        return EXIT_UNAVAILABLE

    except Exception as error:
        print(f"RESULT: the build FAILED: {type(error).__name__}: {error}")

        return EXIT_TESTS_FAILED


if __name__ == "__main__":
    sys.exit(main())
