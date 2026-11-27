"""Run the browser tests in parallel inside Novita Agent Sandboxes, one shard per sandbox.

    python -m tools.sandbox_tests                 # 5 shards, every test marked `browser`
    python -m tools.sandbox_tests --shards 3

The repo is packed (without data/, playbook/, .git, node_modules, sandbox/, .env or caches), the browser tests are
counted locally with pytest's own collection, and the test files are dealt out so each shard gets about the same
number of tests. Every shard starts from the template, unpacks the repo, brings the requirements up to date and
runs its files. Every sandbox is killed at the end and also expires on its own after `SANDBOX_LIFETIME_SECONDS`.

Exit code: 0 when every shard passed, 1 when a test (or the collection) failed, 3 when the check could not run at all
(no API key, no SDK, no network, no balance, template missing). The Stop gate blocks on 1 and only warns on 3.

The API key comes from `NOVITA_API_KEY`, else from a `.env` file in the repo root. `NOVITA_TEMPLATE` names the
template (default `lines-shines-browser:latest`). Setup and how the template is built: `playbook/COMMANDS.md`.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tarfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

EXIT_PASSED = 0
EXIT_TESTS_FAILED = 1
EXIT_UNAVAILABLE = 3

API_KEY_NAME = "NOVITA_API_KEY"
TEMPLATE_ENV_VAR = "NOVITA_TEMPLATE"
DEFAULT_TEMPLATE = "lines-shines-browser:latest"
DEFAULT_SHARDS = 5

# A sandbox that nobody kills still ends by itself; the shard run has to finish well inside this.
SANDBOX_LIFETIME_SECONDS = 900
UNPACK_SECONDS = 180
SETUP_SECONDS = 300
SHARD_TEST_SECONDS = 420
COLLECT_SECONDS = 180
OUTPUT_TAIL_LINES = 6

REMOTE_ARCHIVE = "/tmp/repo.tar.gz"
REMOTE_REPO = "/tmp/repo"

# Top-level names that never go to the sandbox: licensed data, secrets, history and local junk.
LEFT_OUT = {
    "data",
    "playbook",
    ".git",
    "node_modules",
    "sandbox",
    ".env",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".claude",
}
LEFT_OUT_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".DS_Store"}
LEFT_OUT_SUFFIXES = {".db", ".xlsx", ".csv", ".pyc"}


class Unavailable(Exception):
    """The check could not run (as opposed to running and finding a failing test)."""


@dataclass
class ShardOutcome:
    """What one shard did: how long each part took, whether its tests passed, and the end of its output."""

    number: int
    expected_tests: int
    start_seconds: float = 0.0
    run_seconds: float = 0.0
    passed: bool = False
    infrastructure_error: str = ""
    output_tail: str = ""


def load_api_key() -> bool:
    """Make `NOVITA_API_KEY` available: from the environment, else from `.env` in the repo root. Never prints it."""
    if os.environ.get(API_KEY_NAME):
        return True

    env_file = REPO_ROOT / ".env"

    if not env_file.is_file():
        return False

    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.strip().partition("=")

        if separator and name.strip() == API_KEY_NAME and value.strip().strip("\"'"):
            os.environ[API_KEY_NAME] = value.strip().strip("\"'")
            return True

    return False


def pack_repo() -> bytes:
    """The repo as a gzip archive in memory, minus everything in the left-out lists."""
    buffer = io.BytesIO()

    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in sorted(REPO_ROOT.rglob("*")):
            relative = path.relative_to(REPO_ROOT)

            if relative.parts[0] in LEFT_OUT or LEFT_OUT_PARTS.intersection(
                relative.parts
            ):
                continue

            if path.is_file() and path.suffix in LEFT_OUT_SUFFIXES:
                continue

            if path.is_file() or path.is_dir():
                archive.add(path, arcname=relative.as_posix(), recursive=False)

    return buffer.getvalue()


def parse_collected_counts(collect_output: str) -> Counter:
    """How many tests each file holds, from the lines `path::test_name` of `pytest --collect-only -q`."""
    counts: Counter = Counter()

    for line in collect_output.splitlines():
        if "::" in line:
            counts[line.split("::", 1)[0].strip()] += 1

    return counts


def count_browser_tests() -> Counter:
    """Count the browser tests per file with pytest's own collection (no browser is started)."""
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "browser",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
    ]

    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=COLLECT_SECONDS,
        )

    except (OSError, subprocess.TimeoutExpired) as error:
        raise Unavailable(f"could not collect the browser tests: {error}") from error

    counts = parse_collected_counts(result.stdout)

    if result.returncode != 0 or not counts:
        tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-15:])
        raise RuntimeError(f"pytest could not collect the browser tests:\n{tail}")

    return counts


def deal_into_shards(counts: Counter, shard_count: int) -> list[list[str]]:
    """Largest files first, each to the shard with the fewest tests so far; empty shards are dropped."""
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    totals = [0] * shard_count

    for path, test_count in sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    ):
        lightest = totals.index(min(totals))
        shards[lightest].append(path)
        totals[lightest] += test_count

    return [files for files in shards if files]


def last_lines(text: str, line_count: int = OUTPUT_TAIL_LINES) -> str:
    """The last few non-empty lines of some output."""
    lines = [line for line in text.strip().splitlines() if line.strip()]

    return "\n".join(lines[-line_count:])


def create_sandbox(novita: Any, number: int) -> Any:
    """One sandbox from the template; a failure here means the sandbox service cannot be used right now."""
    template = os.environ.get(TEMPLATE_ENV_VAR, DEFAULT_TEMPLATE)
    options = {
        "timeout": SANDBOX_LIFETIME_SECONDS,
        "metadata": {"project": "lines-shines", "purpose": f"gate-shard-{number}"},
    }

    return novita.sandbox.create(template, **options)


def run_shard(
    novita: Any, archive: bytes, number: int, files: list[str], expected_tests: int
) -> ShardOutcome:
    """One shard from start to finish. Never raises: the outcome says what happened."""
    outcome = ShardOutcome(number=number, expected_tests=expected_tests)
    sandbox = None

    try:
        started = time.monotonic()
        sandbox = create_sandbox(novita, number)
        sandbox.files.write(REMOTE_ARCHIVE, archive)
        unpack = f"mkdir -p {REMOTE_REPO} && tar xzf {REMOTE_ARCHIVE} -C {REMOTE_REPO} && rm {REMOTE_ARCHIVE}"
        sandbox.commands.run(unpack, timeout=UNPACK_SECONDS)

        # The template already holds the requirements; this only catches up when they changed since it was built.
        requirements = "-r requirements.txt -r requirements-dev.txt"
        install = (
            f"cd {REMOTE_REPO} && (python3 -m pip install -q {requirements} "
            f"|| python3 -m pip install -q --break-system-packages {requirements})"
        )
        sandbox.commands.run(install, timeout=SETUP_SECONDS)
        outcome.start_seconds = time.monotonic() - started

        started = time.monotonic()
        command = (
            f"cd {REMOTE_REPO} && python3 -m pytest {' '.join(files)} -m browser "
            "-q --tb=short -p no:cacheprovider"
        )

        try:
            result = sandbox.commands.run(command, timeout=SHARD_TEST_SECONDS)
            outcome.passed = True
            outcome.output_tail = last_lines(result.stdout)

        except Exception as error:
            # A command that ran and exited non-zero carries an exit code; anything else is the service failing.
            if getattr(error, "exit_code", None) is None:
                raise

            outcome.output_tail = last_lines(
                f"{getattr(error, 'stdout', '')}\n{getattr(error, 'stderr', '')}", 25
            )

        outcome.run_seconds = time.monotonic() - started

    except Exception as error:
        outcome.infrastructure_error = f"{type(error).__name__}: {error}"

    finally:
        if sandbox is not None:
            try:
                sandbox.kill()

            except Exception:  # The sandbox also expires by itself.
                pass

    return outcome


def connect() -> Any:
    """The Novita client, or `Unavailable` with the reason."""
    if not load_api_key():
        raise Unavailable(
            f"no {API_KEY_NAME} in the environment or in {REPO_ROOT / '.env'}"
        )

    try:
        from novita_sandbox import Novita

    except ImportError as error:
        raise Unavailable(
            "the novita-sandbox package is not installed (pip install -r requirements-sandbox.txt)"
        ) from error

    return Novita()


def run(shard_count: int) -> int:
    """Run every shard and print the report; returns the exit code."""
    novita = connect()

    counts = count_browser_tests()
    shards = deal_into_shards(counts, shard_count)
    expected = [sum(counts[path] for path in files) for files in shards]

    archive = pack_repo()
    print(
        f"{sum(expected)} browser tests in {len(shards)} shards: {expected}", flush=True
    )

    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=len(shards)) as pool:
        futures = [
            pool.submit(run_shard, novita, archive, number, files, tests)
            for number, (files, tests) in enumerate(zip(shards, expected), 1)
        ]
        outcomes = [future.result() for future in futures]

    return report(outcomes, time.monotonic() - started)


def report(outcomes: list[ShardOutcome], wall_seconds: float) -> int:
    """Print one line per shard, then what the owner or Claude needs to act on; returns the exit code."""
    for outcome in outcomes:
        if outcome.infrastructure_error:
            status = "COULD NOT RUN"

        elif outcome.passed:
            status = "passed"

        else:
            status = "FAILED"

        print(
            f"shard {outcome.number}: {outcome.expected_tests} tests, setup {outcome.start_seconds:.0f}s, "
            f"pytest {outcome.run_seconds:.0f}s, {status}"
        )

    print(f"wall time {wall_seconds:.0f}s")
    failed = [
        outcome
        for outcome in outcomes
        if not outcome.passed and not outcome.infrastructure_error
    ]
    broken = [outcome for outcome in outcomes if outcome.infrastructure_error]

    for outcome in failed:
        print(f"\n--- shard {outcome.number} output ---\n{outcome.output_tail}")

    if failed:
        print("\nRESULT: browser tests FAILED in the sandbox.")
        return EXIT_TESTS_FAILED

    if broken:
        print(
            f"\nRESULT: UNAVAILABLE: shard {broken[0].number}: {broken[0].infrastructure_error}"
        )
        return EXIT_UNAVAILABLE

    print("\nRESULT: every shard passed.")

    return EXIT_PASSED


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the browser tests in parallel in Novita sandboxes."
    )
    parser.add_argument(
        "--shards",
        type=int,
        default=DEFAULT_SHARDS,
        help="how many sandboxes at once (the free plan allows 5)",
    )
    options = parser.parse_args(arguments)

    try:
        return run(max(1, options.shards))

    except Unavailable as error:
        print(f"RESULT: UNAVAILABLE: {error}")

        return EXIT_UNAVAILABLE

    except Exception as error:
        print(f"RESULT: browser tests FAILED before they ran: {error}")

        return EXIT_TESTS_FAILED


if __name__ == "__main__":
    sys.exit(main())
