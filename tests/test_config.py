"""Unit tests for the season-threshold routing rule (config.py)."""

from __future__ import annotations
from datetime import date
from config import (
    DEFAULT_THRESHOLDS,
    DYNAMIC_THRESHOLDS,
    NCAAF_DEFAULT_THRESHOLDS,
    NCAAF_DYNAMIC_THRESHOLDS,
    League,
    resolve_default_threshold,
)


def test_finalized_season_uses_static_default():
    assert (
        resolve_default_threshold("pass_rush", 2025, today=date(2026, 6, 1))
        == DEFAULT_THRESHOLDS["pass_rush"]
    )

    assert (
        resolve_default_threshold("pass_block", 2025, today=date(2026, 6, 1))
        == DEFAULT_THRESHOLDS["pass_block"]
    )


def test_in_progress_season_uses_dynamic_value_when_configured():
    current_year, thresholds = next(iter(DYNAMIC_THRESHOLDS.items()))

    assert (
        resolve_default_threshold(
            "pass_rush", current_year, today=date(current_year, 10, 1)
        )
        == thresholds["pass_rush"]
    )

    assert (
        resolve_default_threshold(
            "pass_block", current_year, today=date(current_year, 10, 1)
        )
        == thresholds["pass_block"]
    )


def test_in_progress_season_falls_back_to_static_when_not_yet_configured():
    # 2030 is a stand-in for "currently in-progress season before anyone
    # has hand-edited DYNAMIC_THRESHOLDS for it yet" — must not KeyError.
    assert (
        resolve_default_threshold("pass_rush", 2030, today=date(2030, 9, 10))
        == DEFAULT_THRESHOLDS["pass_rush"]
    )


def test_future_season_relative_to_today_uses_static_default():
    # A season strictly ahead of the current calendar year isn't "in progress" either.
    # Only season_year == current_year routes dynamic.
    assert (
        resolve_default_threshold("pass_block", 2027, today=date(2026, 10, 1))
        == DEFAULT_THRESHOLDS["pass_block"]
    )


def test_the_college_has_its_own_thresholds():
    assert NCAAF_DEFAULT_THRESHOLDS == {"pass_rush": 230, "pass_block": 360}
    assert (
        resolve_default_threshold(
            "pass_block", 2025, League.NCAAF, today=date(2026, 6, 1)
        )
        == 360
    )
    assert (
        resolve_default_threshold("pass_block", 2025, today=date(2026, 6, 1))
        == DEFAULT_THRESHOLDS["pass_block"]
        == 300
    )


def test_the_college_in_progress_season_uses_its_own_dynamic_value():
    current_year, thresholds = next(iter(NCAAF_DYNAMIC_THRESHOLDS.items()))

    for category in ("pass_rush", "pass_block"):
        assert (
            resolve_default_threshold(
                category, current_year, League.NCAAF, today=date(current_year, 10, 1)
            )
            == thresholds[category]
        )


def test_a_college_season_without_a_dynamic_entry_falls_back_to_the_static_default():
    assert (
        resolve_default_threshold(
            "pass_block", 2030, League.NCAAF, today=date(2030, 9, 10)
        )
        == NCAAF_DEFAULT_THRESHOLDS["pass_block"]
    )
