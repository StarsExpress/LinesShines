"""Smoke tests for the wiring behind INVARIANTS 4, 9, 10 and 17: real clicks on the real page.

The pure rules are tested elsewhere (`test_pinned_impact.py`, `test_merge_table.py`); these tests
only check that the controls are connected to them. Every test uses the synthetic players below.
"""

from __future__ import annotations

import re

import pytest
from conftest import RECORDS_READY_JS, wait_until
from database.db_models import (
    NFLPassBlockStat,
    NFLPassRushStat,
    NFLTeam,
)
from main import SessionLocal

# (full name, abbreviated name, team, pass rush opportunities). Ten edge rushers spread
# evenly above the default bar of 230, so a higher bar can cut the pool at any point.
EDGE_PLAYERS = [
    ("Aaron Able", "A. Able", "BUF", 400),
    ("Brian Baker", "B. Baker", "MIA", 380),
    ("Carl Cole", "C. Cole", "BUF", 360),
    ("Dean Drake", "D. Drake", "MIA", 340),
    ("Evan East", "E. East", "BUF", 320),
    ("Fred Frost", "F. Frost", "MIA", 300),
    ("Gary Gale", "G. Gale", "BUF", 280),
    ("Hank Hale", "H. Hale", "MIA", 260),
    ("Ivan Iron", "I. Iron", "BUF", 240),
    ("Jake Jones", "J. Jones", "MIA", 235),
]

# Two interior linemen, for the position change.
INTERIOR_PLAYERS = [
    ("Karl Kane", "K. Kane", "BUF", 300),
    ("Leo Lane", "L. Lane", "MIA", 260),
]

DEFAULT_THRESHOLD = 230
ORDINAL_PATTERN = re.compile(r"^\d+(st|nd|rd|th)$")
# What a metric cell shows for a metric the seeded rows leave empty.
NO_VALUE = "—"

PINNED_QUOTA_LABEL = "#pcs-quota-label"
SINGLES_ROWS = "#pcs-singles-list .pcs-row"
MERGED_ROWS = "#pcs-merged-list .pcs-row"
MERGE_CARDS = ".scout-card--merge"
CONFIRM_OVERLAY = "#merge-confirm-overlay"
TOAST = "#pinned-refresh-notice.is-visible"


@pytest.fixture()
def seeded_smoke_db():
    """Replace the shared fixture's rows with the players above (2025, pass rush only)."""
    with SessionLocal() as db:
        db.query(NFLPassRushStat).delete()
        db.query(NFLPassBlockStat).delete()
        db.query(NFLTeam).delete()

        db.add(NFLTeam(code="BUF", full_name="Buffalo Bills", primary_color="#00338D"))
        db.add(NFLTeam(code="MIA", full_name="Miami Dolphins", primary_color="#008E97"))

        player_id = 1000

        for position, players in (("ED", EDGE_PLAYERS), ("DI", INTERIOR_PLAYERS)):
            for index, (full_name, short_name, team, opportunities) in enumerate(
                players
            ):
                player_id += 1

                db.add(
                    NFLPassRushStat(
                        season=2025,
                        position=position,
                        team_code=team,
                        player_id=player_id,
                        player=full_name,
                        abbr_name=short_name,
                        games=17,
                        pr_opp=opportunities,
                        tps_pr_opp=opportunities // 2,
                        pass_cov_percent=8.0 + index,
                        tps_pass_cov_percent=5.0 + index,
                        win_rate=10.0 + index,
                        tps_win_rate=10.0 + index,
                        pressure_rate=15.0 + index,
                        tps_pressure_rate=15.0 + index,
                        havoc_rate=5.0 + index,
                        tps_havoc_rate=5.0 + index,
                        prp=4.0 + index,
                        tps_prp=4.0 + index,
                    )
                )

        db.commit()

    yield


@pytest.fixture()
def page(live_server_url, seeded_smoke_db, open_page):
    page = open_page(
        live_server_url,
        viewport={"width": 1280, "height": 900},
        ready_js=RECORDS_READY_JS,
    )

    assert page.locator("#threshold-number").input_value() == str(DEFAULT_THRESHOLD)

    return page


def chart_point_count(page) -> int:
    return page.evaluate("document.querySelector('#chart').data[0].x.length")


def applied_state(page) -> dict:
    return page.evaluate("""async () => {
            const d = await import('/data.js');
            return {
                position: d.appliedFilters.position,
                threshold: String(d.appliedFilters.threshold),
            };
        }""")


def set_threshold_by_typing(page, value: int) -> None:
    """Type the number key by key, the way a user does; the field keeps focus."""
    number = page.locator("#threshold-number")
    number.focus()
    number.select_text()
    page.keyboard.type(str(value), delay=20)


def add_to_players_filter(page, full_name: str) -> None:
    if page.locator("#players-panel").is_hidden():
        page.click("#players-toggle-btn")

    page.fill("#players-input", full_name)
    page.locator(
        "#players-dropdown .player-option-name", has_text=full_name
    ).first.click()


def chip_names(page) -> list[str]:
    return page.locator("#players-chips .player-chip > span").all_text_contents()


def pin_player(page, full_name: str) -> None:
    page.fill("#pcs-add-input", full_name)
    page.locator(
        "#pcs-add-dropdown .player-option-name", has_text=full_name
    ).first.click()


def pick_for_comparison(page, full_name: str) -> None:
    page.fill("#merge-create-input", full_name)
    page.locator(
        "#merge-create-dropdown .player-option-name", has_text=full_name
    ).first.click()


def create_comparison(page, full_names: list[str]) -> None:
    page.click("#pcs-create-btn")

    for full_name in full_names:
        pick_for_comparison(page, full_name)

    page.click("#merge-create-submit")
    page.locator("#merge-create-overlay").wait_for(state="hidden")


def pinned_names(page) -> list[str]:
    return page.locator(SINGLES_ROWS).evaluate_all(
        "rows => rows.map(r => r.dataset.player)"
    )


def quota_text(page) -> str:
    return page.locator(PINNED_QUOTA_LABEL).text_content()


def click_apply_and_expect_confirm(page) -> None:
    page.click("#apply-filters")
    page.locator(CONFIRM_OVERLAY).wait_for(state="visible")


# --- Invariant 4: the chart changes only on Apply; the Players search pool stays live. ---------


def test_the_chart_waits_for_apply_while_the_controls_change(page):
    before_points = chart_point_count(page)
    assert before_points == len(EDGE_PLAYERS)

    page.select_option("#position-select", "DI")
    set_threshold_by_typing(page, 250)
    page.keyboard.press("Tab")

    assert chart_point_count(page) == before_points
    assert applied_state(page) == dict(position="ED", threshold=str(DEFAULT_THRESHOLD))
    assert "pending" in page.locator("#apply-filters").get_attribute("class")

    page.click("#apply-filters")
    wait_until(
        page,
        f"document.querySelector('#chart').data?.[0].x.length === {len(INTERIOR_PLAYERS)}",
    )

    assert applied_state(page) == dict(position="DI", threshold="250")


def test_the_players_search_follows_the_pending_position_not_the_chart(page):
    page.select_option("#position-select", "DI")
    page.click("#players-toggle-btn")

    page.fill("#players-input", "Kane")
    suggestion = page.locator(
        "#players-dropdown .player-option-name", has_text="Karl Kane"
    )
    suggestion.first.wait_for(state="visible")

    page.fill("#players-input", "Able")
    assert (
        page.locator(
            "#players-dropdown .player-option-name", has_text="Aaron Able"
        ).count()
        == 0
    )

    assert (
        applied_state(page)["position"] == "ED"
    ), "the chart must not follow the search"
    assert chart_point_count(page) == len(EDGE_PLAYERS)


# --- Invariant 17: selected Players are re-checked on commit, never while dragging or typing. ---


def select_three_players(page) -> None:
    for full_name in ("Aaron Able", "Fred Frost", "Jake Jones"):
        add_to_players_filter(page, full_name)

    assert chip_names(page) == ["A. Able", "F. Frost", "J. Jones"]

    # The open panel would sit on top of the slider, so close it the way a user does.
    page.click("#threshold-field-label")
    assert page.locator("#players-panel").is_hidden()


def test_dragging_the_slider_checks_nothing_until_it_is_released(page):
    select_three_players(page)
    slider_box = page.locator("#threshold-slider").bounding_box()
    middle_y = slider_box["y"] + slider_box["height"] / 2
    start_ratio = DEFAULT_THRESHOLD / float(
        page.locator("#threshold-slider").get_attribute("max")
    )

    page.mouse.move(
        slider_box["x"] + 8 + (slider_box["width"] - 16) * start_ratio, middle_y
    )
    page.mouse.down()
    page.mouse.move(slider_box["x"] + slider_box["width"] + 30, middle_y, steps=10)

    top_value = page.locator("#threshold-slider").get_attribute("max")
    assert page.locator("#threshold-number").input_value() == top_value
    assert chip_names(page) == [
        "A. Able",
        "F. Frost",
        "J. Jones",
    ], "checked while dragging"
    assert page.locator(TOAST).count() == 0

    page.mouse.up()

    assert chip_names(page) == ["A. Able"]
    assert (
        "Removed from Players: F. Frost, J. Jones" in page.locator(TOAST).text_content()
    )


def test_typing_a_number_checks_nothing_until_the_change_is_committed(page):
    select_three_players(page)

    set_threshold_by_typing(page, 330)

    assert chip_names(page) == [
        "A. Able",
        "F. Frost",
        "J. Jones",
    ], "checked while typing"
    assert page.locator(TOAST).count() == 0

    page.keyboard.press("Tab")

    assert chip_names(page) == ["A. Able"]
    assert (
        "Removed from Players: F. Frost, J. Jones" in page.locator(TOAST).text_content()
    )


def test_enter_in_the_number_box_runs_apply_and_checks_the_selection(page):
    select_three_players(page)

    set_threshold_by_typing(page, 330)
    assert chip_names(page) == ["A. Able", "F. Frost", "J. Jones"]

    page.keyboard.press("Enter")
    wait_until(
        page, "document.querySelectorAll('#players-chips .player-chip').length === 1"
    )

    assert chip_names(page) == ["A. Able"]
    assert (
        "Removed from Players: F. Frost, J. Jones" in page.locator(TOAST).text_content()
    )
    assert applied_state(page)["threshold"] == "330"


def test_a_removed_player_is_not_restored_when_the_value_moves_back(page):
    select_three_players(page)

    set_threshold_by_typing(page, 330)
    page.keyboard.press("Tab")
    assert chip_names(page) == ["A. Able"]

    set_threshold_by_typing(page, DEFAULT_THRESHOLD)
    page.keyboard.press("Tab")

    assert chip_names(page) == ["A. Able"]


# --- Invariant 9: Pinned Players follow the final filter combination. --------------------------


def pin_two_comparisons(page) -> None:
    """Able, Baker and Drake in one Comparison; Cole and East in another. Five distinct players."""
    create_comparison(page, ["Aaron Able", "Brian Baker", "Dean Drake"])
    create_comparison(page, ["Carl Cole", "Evan East"])

    assert page.locator(SINGLES_ROWS).count() == 5
    assert page.locator(MERGED_ROWS).count() == 2
    assert "5 / 8" in quota_text(page)


def test_a_higher_bar_removes_only_who_no_longer_fits_and_shrinks_or_dissolves(page):
    pin_two_comparisons(page)

    set_threshold_by_typing(page, 350)
    page.keyboard.press("Tab")
    click_apply_and_expect_confirm(page)

    confirm_text = page.locator("#merge-confirm-body").text_content()
    assert "D. Drake" in confirm_text
    assert "E. East" in confirm_text
    assert "A. Able" in confirm_text, "the shrunk Comparison is listed with its members"
    assert "dissolved" in confirm_text.lower()

    page.click("#merge-confirm-clear")
    wait_until(
        page, "document.querySelectorAll('#pcs-singles-list .pcs-row').length === 3"
    )

    assert sorted(pinned_names(page)) == ["Aaron Able", "Brian Baker", "Carl Cole"]
    assert page.locator(MERGED_ROWS).count() == 1
    assert (
        page.locator(MERGED_ROWS).first.locator(".pcs-row-name").text_content()
        == "A. Able · B. Baker"
    )
    assert page.locator(MERGE_CARDS).count() == 1
    assert "3 / 8" in quota_text(page)


def test_cancelling_the_confirm_changes_nothing(page):
    pin_two_comparisons(page)

    set_threshold_by_typing(page, 350)
    page.keyboard.press("Tab")
    click_apply_and_expect_confirm(page)

    page.click("#merge-confirm-cancel")
    page.locator(CONFIRM_OVERLAY).wait_for(state="hidden")

    assert page.locator(SINGLES_ROWS).count() == 5
    assert page.locator(MERGED_ROWS).count() == 2
    assert applied_state(page)["threshold"] == str(DEFAULT_THRESHOLD)
    assert "pending" in page.locator("#apply-filters").get_attribute("class")


def test_a_position_change_clears_everything_pinned(page):
    pin_two_comparisons(page)

    page.select_option("#position-select", "DI")
    click_apply_and_expect_confirm(page)

    page.click("#merge-confirm-clear")
    wait_until(
        page, "document.querySelectorAll('#pcs-singles-list .pcs-row').length === 0"
    )

    assert page.locator(MERGED_ROWS).count() == 0
    assert page.locator(MERGE_CARDS).count() == 0
    assert "0 / 8" in quota_text(page)
    assert applied_state(page)["position"] == "DI"


def test_a_looser_bar_keeps_everything_without_a_confirm(page):
    pin_two_comparisons(page)

    set_threshold_by_typing(page, 100)
    page.keyboard.press("Tab")
    page.click("#apply-filters")
    wait_until(
        page, "!document.querySelector('#apply-filters').classList.contains('pending')"
    )

    assert page.locator(CONFIRM_OVERLAY).is_hidden()
    assert page.locator(SINGLES_ROWS).count() == 5
    assert page.locator(MERGED_ROWS).count() == 2


# --- Invariant 10: Merge Cards show percentiles only, hold at most 5 and check the quota at Submit. ---


def test_a_comparison_shows_percentiles_only(page):
    create_comparison(page, ["Aaron Able", "Brian Baker", "Carl Cole"])

    cells = [
        text.strip()
        for text in page.locator(
            f"{MERGE_CARDS} .merge-metric-cell"
        ).all_text_contents()
    ]

    shown = [text for text in cells if text != NO_VALUE]

    assert shown, "the card has no percentile"
    assert all(ORDINAL_PATTERN.match(text) for text in shown), cells
    assert (
        "#" not in page.locator(MERGE_CARDS).inner_text()
    ), "a #rank/N leaked onto the card"


def test_the_create_popup_holds_at_most_five_players(page):
    page.click("#pcs-create-btn")

    for full_name in (
        "Aaron Able",
        "Brian Baker",
        "Carl Cole",
        "Dean Drake",
        "Evan East",
    ):
        pick_for_comparison(page, full_name)

    assert page.locator("#merge-create-message").text_content().strip() == ""

    pick_for_comparison(page, "Fred Frost")

    assert "at most 5 players" in page.locator("#merge-create-message").text_content()
    assert "Frost" not in page.locator("#merge-create-members").text_content()


def test_the_quota_is_checked_once_at_submit_not_while_picking(page):
    for full_name in (
        "Aaron Able",
        "Brian Baker",
        "Carl Cole",
        "Dean Drake",
        "Evan East",
    ):
        pin_player(page, full_name)

    assert "5 / 8" in quota_text(page)
    page.click("#pcs-create-btn")

    for full_name in (
        "Fred Frost",
        "Gary Gale",
        "Hank Hale",
        "Ivan Iron",
        "Jake Jones",
    ):
        pick_for_comparison(page, full_name)
        assert page.locator("#merge-create-message").text_content().strip() == ""

    page.click("#merge-create-submit")

    assert (
        "Workspace full (8/8)" in page.locator("#merge-create-message").text_content()
    )
    assert page.locator("#merge-create-overlay").is_visible()
    assert page.locator(MERGE_CARDS).count() == 0
    assert "5 / 8" in quota_text(page)
