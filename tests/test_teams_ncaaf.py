"""The NCAAF conference lookup: stints are well formed and the known moves resolve.

Uses only the tables in `teams/ncaaf.py`, so it needs no PFF data.
"""

from __future__ import annotations

from collections import Counter

import pytest

import teams.ncaaf as reference
from teams.ncaaf import (
    ACC,
    B1G,
    BIG_12,
    INDEPENDENT,
    MAC,
    PAC_12,
    SEC,
    conference_of,
)

FIRST_SEASON = 2014
LAST_SEASON = 2026


def test_every_stint_names_a_scoped_conference_and_starts_in_the_covered_range():
    for franchise_id, stints in reference.CONFERENCE_STINTS.items():
        for stint in stints:
            assert stint.conference in reference.SCOPED_CONFERENCES, franchise_id
            assert stint.first_season >= reference.FIRST_SEASON_COVERED, franchise_id


def test_stints_of_one_school_are_in_order_and_never_overlap():
    for franchise_id, stints in reference.CONFERENCE_STINTS.items():
        for earlier, later in zip(stints, stints[1:]):
            assert earlier.last_season is not None, franchise_id
            assert earlier.last_season < later.first_season, franchise_id


def test_a_school_is_not_both_scoped_and_out_of_scope():
    scoped_ids = set(reference.CONFERENCE_STINTS)

    assert not scoped_ids & reference.OUT_OF_SCOPE_FRANCHISE_IDS


def test_a_school_moving_conference_changes_label_in_the_move_season():
    assert conference_of(311, 2023) == BIG_12  # Texas.
    assert conference_of(311, 2024) == SEC
    assert conference_of(264, 2023) == PAC_12  # Oregon.
    assert conference_of(264, 2024) == B1G
    assert conference_of(130, 2024) == ACC  # California.


def test_a_school_outside_its_stints_is_out_of_scope_for_that_season():
    assert conference_of(128, 2022) is None  # BYU was independent.
    assert conference_of(128, 2023) == BIG_12
    assert conference_of(314, 2025) is None  # Texas State, Sun Belt until 2026.
    assert conference_of(314, 2026) == PAC_12


def test_umass_has_two_separate_mac_stints():
    assert conference_of(216, 2015) == MAC
    assert conference_of(216, 2016) is None
    assert conference_of(216, 2024) is None
    assert conference_of(216, 2025) == MAC


def test_northern_illinois_leaves_the_mac_after_2025():
    assert conference_of(254, 2025) == MAC
    assert conference_of(254, 2026) is None


def test_the_two_schools_left_in_the_pac_12_in_2024_and_2025():
    pac_12_ids = [
        franchise_id
        for franchise_id in reference.CONFERENCE_STINTS
        if conference_of(franchise_id, 2024) == PAC_12
    ]

    assert sorted(pac_12_ids) == [265, 341]  # Oregon State, Washington State.


def test_notre_dame_is_the_only_independent_in_scope():
    independents = [
        franchise_id
        for franchise_id in reference.CONFERENCE_STINTS
        if conference_of(franchise_id, 2025) == INDEPENDENT
    ]

    assert independents == [258]


@pytest.mark.parametrize(
    "season, conference, expected_size",
    [
        (2022, BIG_12, 10),
        (2023, BIG_12, 14),
        (2024, BIG_12, 16),
        (2022, PAC_12, 12),
        (2024, PAC_12, 2),
        (2026, PAC_12, 8),
        (2024, B1G, 18),
        (2024, ACC, 17),
        (2024, SEC, 16),
        (2025, MAC, 13),
        (2026, MAC, 13),
    ],
)
def test_conference_size_in_season(season, conference, expected_size):
    sizes = Counter(
        conference_of(franchise_id, season)
        for franchise_id in reference.CONFERENCE_STINTS
    )

    assert sizes[conference] == expected_size


def test_a_never_scoped_school_is_dropped_without_an_error():
    assert conference_of(101, 2024) is None  # Air Force.


def test_an_unknown_franchise_id_raises_instead_of_being_dropped():
    with pytest.raises(KeyError):
        conference_of(999999, 2024)


def test_scoped_franchise_ids_collects_schools_with_any_scoped_season():
    ids = reference.scoped_franchise_ids(FIRST_SEASON, LAST_SEASON)

    assert ids == sorted(reference.CONFERENCE_STINTS)
    assert 128 in reference.scoped_franchise_ids(2023, 2023)
    assert 128 not in reference.scoped_franchise_ids(2022, 2022)
