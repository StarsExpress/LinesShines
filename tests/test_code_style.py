"""The code-style checker in tools/check_code_style.py, and the repo staying inside its baseline."""

from __future__ import annotations

import textwrap
from collections import Counter
from pathlib import Path

import pytest

from tools import check_code_style


def rules_found(snippet: str, path: str = "package/example.py") -> set[str]:
    """The rules a snippet of code breaks, given the file it pretends to be."""
    return {
        violation.rule
        for violation in check_code_style.check_source(textwrap.dedent(snippet), path)
    }


# (rule, a snippet that breaks it, a snippet that follows it).
RULE_CASES = [
    (
        "blank-before-branch",
        '''
        """Module."""


        def pick(flag: bool) -> int:
            """Pick."""
            if flag:
                return 1
            else:
                return 2
        ''',
        '''
        """Module."""


        def pick(flag: bool) -> int:
            """Pick."""
            if flag:
                return 1

            else:
                return 2
        ''',
    ),
    (
        "blank-before-branch",
        '''
        """Module."""

        try:
            value = 1
        except ValueError:
            value = 2
        ''',
        '''
        """Module."""

        try:
            value = 1

        except ValueError:
            value = 2

        finally:
            value = 3
        ''',
    ),
    (
        "type-hints",
        '''
        """Module."""


        def add(left, right: int) -> int:
            """Add."""
            return left + right
        ''',
        '''
        """Module."""


        class Counter:
            """Counts."""

            def add(self, amount: int, *rest: int, **named: int) -> int:
                """Add."""
                return amount
        ''',
    ),
    (
        "type-hints",
        '''
        """Module."""


        def add(left: int, right: int):
            """Add."""
            return left + right
        ''',
        '''
        """Module."""


        def add(left: int, right: int) -> int:
            """Add."""
            return left + right
        ''',
    ),
    (
        "module-docstring",
        """
        VALUE = 1
        """,
        '''
        """Module."""

        VALUE = 1
        ''',
    ),
    (
        "comment-period",
        '''
        """Module."""

        # Explains why but has no period
        VALUE = 1
        ''',
        '''
        """Module."""

        # A sentence that wraps onto
        # a second line and ends here.
        VALUE = 1  # Akron.
        OTHER = 2  # noqa: E402
        THIRD = 3  # https://example.com/page
        # ---- A section divider ----
        ''',
    ),
    (
        "comment-period",
        '''
        """Module."""

        VALUE = 1  # Akron
        ''',
        '''
        """Module."""

        VALUE = 1  # Akron.
        ''',
    ),
    (
        "docstring-period",
        '''
        """Module."""


        def run() -> None:
            """Run the thing"""
        ''',
        '''
        """Module."""


        def run() -> None:
            """Run the thing."""
        ''',
    ),
    (
        "docstring-period",
        '''
        """Module.

        A paragraph with no ending
        """
        ''',
        '''
        """Module.

        Usage (from the repo root):
            python -m tools.check_code_style
        """
        ''',
    ),
    (
        "snake-case",
        '''
        """Module."""


        def run() -> None:
            """Run."""
            userName = 1
        ''',
        '''
        """Module."""

        import enum


        class League(enum.Enum):
            """Leagues."""

            NFL = "nfl"


        SessionLocal = dict()
        MAX_ROWS = 5


        def run() -> None:
            """Run."""
            user_name = 1
        ''',
    ),
    (
        "abbreviation",
        '''
        """Module."""


        def run() -> None:
            """Run."""
            value_cnt = 1
        ''',
        '''
        """Module."""


        def run() -> None:
            """Run."""
            pass_rush_df = 1
            value_count = 2
        ''',
    ),
    (
        "dataframe-name",
        '''
        """Module."""

        import pandas as pd

        frame = pd.read_csv("a.csv")
        ''',
        '''
        """Module."""

        import pandas as pd

        frame_df = pd.read_csv("a.csv")
        sheets = pd.read_excel("a.xlsx", sheet_name=None)
        ''',
    ),
    (
        "constants-above-functions",
        '''
        """Module."""


        def run() -> None:
            """Run."""


        LATE_CONSTANT = 1
        ''',
        '''
        """Module."""

        EARLY_CONSTANT = 1


        def run() -> None:
            """Run."""


        RUNNERS = [run]
        ''',
    ),
    (
        "blank-between-steps",
        '''
        """Module."""


        def run() -> None:
            """Run."""
            first = 1
            second = 2
            third = 3
            fourth = 4
            fifth = 5
            sixth = 6
            seventh = 7
        ''',
        '''
        """Module."""


        def run() -> None:
            """Run."""
            first = 1
            second = 2
            third = 3

            fourth = 4
            fifth = 5
            sixth = 6
            seventh = 7
        ''',
    ),
]


@pytest.mark.parametrize(
    ("rule", "breaking", "following"),
    RULE_CASES,
    ids=[f"{case[0]}-{index}" for index, case in enumerate(RULE_CASES)],
)
def test_each_rule_catches_its_break_and_accepts_the_fix(rule, breaking, following):
    assert rule in rules_found(breaking)
    assert rule not in rules_found(following)


def test_a_run_of_asserts_or_imports_is_not_a_wall_of_statements():
    snippet = '''
    """Module."""

    import json
    import re
    import sys
    import os
    import io
    import ast
    import abc


    def test_it(page) -> None:
        """Check it."""
        assert page == 1
        assert page == 2
        assert page == 3
        assert page == 4
        assert page == 5
        assert page == 6
        assert page == 7
    '''

    assert "blank-between-steps" not in rules_found(snippet)


def test_a_comment_line_between_statements_ends_the_run():
    snippet = '''
    """Module."""


    def run() -> None:
        """Run."""
        first = 1
        second = 2
        third = 3
        # Why the next three.
        fourth = 4
        fifth = 5
        sixth = 6
        seventh = 7
    '''

    assert "blank-between-steps" not in rules_found(snippet)


def test_tests_are_not_held_to_type_hints_short_names_or_constant_order():
    snippet = '''
    """Module."""


    def test_it(page, tmp_path):
        """Check it."""
        r = 1


    LATE = 1
    '''

    assert rules_found(snippet, "tests/test_example.py") == set()
    assert {"type-hints", "abbreviation", "constants-above-functions"} <= rules_found(
        snippet, "package/example.py"
    )


def test_tests_still_need_a_blank_line_before_else_and_a_period_on_comments():
    snippet = '''
    """Module."""

    # No period here
    if True:
        pass
    else:
        pass
    '''

    assert {"comment-period", "blank-before-branch"} <= rules_found(
        snippet, "tests/test_example.py"
    )


def test_a_file_that_cannot_be_parsed_is_reported_not_raised():
    assert rules_found("def broken(:\n") == {"syntax"}


def test_the_baseline_forgives_only_what_it_lists():
    first = check_code_style.Violation("a.py", 3, "type-hints", "m", "def f(x):")
    again = check_code_style.Violation("a.py", 9, "type-hints", "m", "def f(x):")
    other = check_code_style.Violation("a.py", 5, "snake-case", "m", "userName = 1")

    new_violations, stale_keys = check_code_style.split_by_baseline(
        [first, again, other], Counter({first.key: 1, "b.py|type-hints|def g(y):": 1})
    )

    assert new_violations == [again, other]
    assert stale_keys == ["b.py|type-hints|def g(y):"]


def test_a_baseline_key_ignores_line_numbers_so_moving_code_is_not_a_new_violation():
    before = check_code_style.Violation("a.py", 3, "type-hints", "m", "def f(x):")
    after = check_code_style.Violation("a.py", 40, "type-hints", "m", "def f(x):")

    assert before.key == after.key


def test_the_command_line_fails_on_a_new_violation_and_on_a_stale_baseline(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(check_code_style, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_code_style, "BASELINE_PATH", tmp_path / "baseline.json")
    source_path = tmp_path / "example.py"
    source_path.write_text("VALUE = 1\n", encoding="utf-8")

    assert check_code_style.main([]) == 1
    assert "module-docstring" in capsys.readouterr().out

    assert check_code_style.main(["--update-baseline"]) == 0
    assert check_code_style.main([]) == 0

    source_path.write_text('"""Fixed."""\n\nVALUE = 1\n', encoding="utf-8")

    assert check_code_style.main([]) == 1
    assert "no longer applies" in capsys.readouterr().out
    assert check_code_style.main(["--update-baseline"]) == 0
    assert check_code_style.main([]) == 0


def test_virtual_environments_node_modules_and_the_playbook_are_not_scanned(tmp_path):
    for folder in ("venv", "node_modules", "playbook", "sandbox", "package"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    found = check_code_style.find_python_files(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in found] == [
        "package/module.py"
    ]


def test_a_file_named_by_hand_in_a_skipped_folder_is_still_left_alone(tmp_path):
    skipped_path = tmp_path / "node_modules" / "tool.py"
    skipped_path.parent.mkdir()
    skipped_path.write_text("VALUE = 1\n", encoding="utf-8")

    assert check_code_style.check_files([skipped_path], root=tmp_path) == []


def test_update_baseline_refuses_to_run_on_named_files(capsys):
    with pytest.raises(SystemExit) as stopped:
        check_code_style.main(["--update-baseline", "some_file.py"])

    assert stopped.value.code == 2
    assert "name no files" in capsys.readouterr().err


def test_the_repo_has_no_violation_beyond_its_baseline():
    paths = check_code_style.find_python_files(check_code_style.REPO_ROOT)
    violations = check_code_style.check_files(paths)

    new_violations, stale_keys = check_code_style.split_by_baseline(
        violations, check_code_style.load_baseline()
    )

    assert [violation.render() for violation in new_violations] == []
    assert stale_keys == []


def test_the_checker_and_its_own_test_follow_every_rule_without_the_baseline():
    own_paths = [
        Path(check_code_style.__file__),
        Path(__file__),
    ]
    violations = check_code_style.check_files(own_paths)

    assert [violation.render() for violation in violations] == []
