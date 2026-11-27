"""The shard dealing in tools/browser_shards.py, used by the sandbox runner and by the CI matrix.

The collection is replaced by fixed counts, except in one test that runs pytest's real collection (no browser starts).
"""

from __future__ import annotations

from collections import Counter

import pytest

from tools import browser_shards


def test_collected_counts_are_per_file_and_ignore_summary_lines():
    output = (
        "tests/test_a.py::test_one\n"
        "tests/test_a.py::test_two[x]\n"
        "tests/test_b.py::TestThing::test_three\n"
        "\n321/400 tests collected (79 deselected) in 1.2s\n"
    )

    assert browser_shards.parse_collected_counts(output) == Counter(
        {"tests/test_a.py": 2, "tests/test_b.py": 1}
    )


def test_dealing_balances_the_test_counts_and_loses_no_file():
    counts = Counter({"a": 50, "b": 40, "c": 30, "d": 20, "e": 10, "f": 10})

    shards = browser_shards.deal_into_shards(counts, 3)
    totals = sorted(sum(counts[path] for path in files) for files in shards)

    assert totals == [50, 50, 60]
    assert sorted(path for files in shards for path in files) == sorted(counts)


def test_dealing_is_the_same_every_time():
    counts = Counter({f"file_{number}": number % 7 + 1 for number in range(30)})

    assert browser_shards.deal_into_shards(
        counts, 5
    ) == browser_shards.deal_into_shards(counts, 5)


def test_dealing_drops_shards_that_would_be_empty():
    shards = browser_shards.deal_into_shards(Counter({"a": 3, "b": 2}), 5)

    assert len(shards) == 2
    assert all(shards)


@pytest.fixture()
def fixed_counts(monkeypatch):
    counts = Counter(
        {"tests/a.py": 5, "tests/b.py": 4, "tests/c.py": 3, "tests/d.py": 3}
    )
    monkeypatch.setattr(browser_shards, "count_browser_tests", lambda: counts)

    return counts


def test_every_index_together_runs_every_file_exactly_once(fixed_counts, capsys):
    printed_files: list[str] = []

    for index in (1, 2, 3):
        assert browser_shards.main(["--shards", "3", "--index", str(index)]) == 0
        printed_files += capsys.readouterr().out.split()

    assert sorted(printed_files) == sorted(fixed_counts)


def test_an_index_prints_that_shards_files_on_one_line(fixed_counts, capsys):
    browser_shards.main(["--shards", "2", "--index", "1"])

    output = capsys.readouterr().out

    assert output.count("\n") == 1
    assert output.split()[0] == "tests/a.py"


@pytest.mark.parametrize("index", ["0", "4", "-1"])
def test_an_index_outside_the_shards_is_exit_code_2_and_prints_no_files(
    index, fixed_counts, capsys
):
    code = browser_shards.main(["--shards", "3", "--index", index])
    captured = capsys.readouterr()

    assert code == browser_shards.EXIT_BAD_INDEX
    assert captured.out == ""
    assert "does not exist" in captured.err


def test_without_an_index_it_lists_every_shard(fixed_counts, capsys):
    code = browser_shards.main(["--shards", "2"])

    assert code == 0
    assert capsys.readouterr().out.splitlines() == [
        "shard 1: 2 files, 8 tests",
        "shard 2: 2 files, 7 tests",
    ]


def test_a_collection_failure_is_exit_code_1_with_the_reason(monkeypatch, capsys):
    def broken() -> Counter:
        raise RuntimeError("pytest could not collect the browser tests")

    monkeypatch.setattr(browser_shards, "count_browser_tests", broken)

    code = browser_shards.main(["--index", "1"])

    assert code == browser_shards.EXIT_COLLECTION_FAILED
    assert "could not collect" in capsys.readouterr().err


def test_the_real_collection_finds_the_browser_tests_and_every_file_gets_dealt():
    counts = browser_shards.count_browser_tests()
    shards = browser_shards.deal_into_shards(counts, 5)

    assert sum(counts.values()) > 100
    assert len(shards) == 5
    assert sorted(path for files in shards for path in files) == sorted(counts)
