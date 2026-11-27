"""Deal the browser test files into shards of about equal test count, for the sandboxes and for CI.

    python -m tools.browser_shards --shards 5 --index 2   # the test files of shard 2, space separated, for pytest
    python -m tools.browser_shards --shards 5             # every shard with its number of files and tests

The tests are counted with pytest's own collection (`-m browser --collect-only`), which starts no browser, then the
files are dealt out: largest file first, each to the shard with the fewest tests so far. The result is the same on
every machine, so five CI jobs that each ask for their own index together run every file exactly once.

Exit code: 0 done; 1 the browser tests could not be collected; 2 the index is outside the shards.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXIT_DONE = 0
EXIT_COLLECTION_FAILED = 1
EXIT_BAD_INDEX = 2

DEFAULT_SHARDS = 5
COLLECT_SECONDS = 180
COLLECT_ERROR_LINES = 15


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
        raise RuntimeError(f"could not collect the browser tests: {error}") from error

    counts = parse_collected_counts(result.stdout)

    if result.returncode != 0 or not counts:
        output_lines = (result.stdout + result.stderr).strip().splitlines()
        tail = "\n".join(output_lines[-COLLECT_ERROR_LINES:])
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


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deal the browser test files into shards."
    )
    parser.add_argument("--shards", type=int, default=DEFAULT_SHARDS)
    parser.add_argument(
        "--index", type=int, help="print only this shard's files (counting from 1)"
    )
    options = parser.parse_args(arguments)

    try:
        counts = count_browser_tests()

    except RuntimeError as error:
        print(error, file=sys.stderr)

        return EXIT_COLLECTION_FAILED

    shards = deal_into_shards(counts, max(1, options.shards))

    if options.index is None:
        for number, files in enumerate(shards, 1):
            tests = sum(counts[path] for path in files)
            print(f"shard {number}: {len(files)} files, {tests} tests")

        return EXIT_DONE

    if not 1 <= options.index <= len(shards):
        print(
            f"shard {options.index} does not exist: there are {len(shards)} shards",
            file=sys.stderr,
        )

        return EXIT_BAD_INDEX

    print(" ".join(shards[options.index - 1]))

    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
