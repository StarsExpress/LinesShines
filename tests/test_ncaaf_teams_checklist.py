"""The NCAAF Teams checklist is rebuilt for each season and keeps what the user chose."""

from __future__ import annotations

import pytest

# Akron (102) plays in 2024 and 2025; Alabama (103) only appears in 2025.
AKRON = "102"
ALABAMA = "103"


@pytest.fixture()
def page(live_server_url, seeded_ncaaf_db):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{live_server_url}/ncaaf-season")

        # The app has finished loading once it holds its metadata and its applied filters.
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters); }"
        )

        yield pg
        browser.close()


def _switch_season(page, season):
    page.select_option("#season-select", season)
    page.wait_for_function(
        "season => document.querySelector('#season-select').value === season",
        arg=season,
    )


def _checked_teams(page):
    return page.eval_on_selector_all(
        "#teams-checklist input:checked", "boxes => boxes.map(box => box.value)"
    )


def _listed_teams(page):
    return page.eval_on_selector_all(
        "#teams-checklist input", "boxes => boxes.map(box => box.value)"
    )


def _clear_all_teams(page):
    page.click("#teams-toggle-btn")
    page.click("#teams-select-none")
    page.click("#teams-toggle-btn")


def test_each_season_lists_only_its_own_schools(page):
    assert sorted(_listed_teams(page)) == [AKRON, ALABAMA]

    _switch_season(page, "2024")

    assert _listed_teams(page) == [AKRON]


def test_a_school_first_seen_in_a_later_season_does_not_turn_on_after_clear(page):
    _switch_season(page, "2024")
    _clear_all_teams(page)

    _switch_season(page, "2025")

    assert sorted(_listed_teams(page)) == [AKRON, ALABAMA]
    assert _checked_teams(page) == []


def test_all_teams_stays_all_teams_in_a_season_with_more_schools(page):
    _switch_season(page, "2024")
    assert _checked_teams(page) == [AKRON]

    _switch_season(page, "2025")

    assert sorted(_checked_teams(page)) == [AKRON, ALABAMA]


def test_an_unchecked_school_stays_unchecked_when_its_season_comes_back(page):
    page.click("#teams-toggle-btn")
    page.uncheck(f"#teams-checklist input[value='{ALABAMA}']")
    page.click("#teams-toggle-btn")

    _switch_season(page, "2024")
    _switch_season(page, "2025")

    assert _checked_teams(page) == [AKRON]


def test_choosing_a_player_with_all_teams_selected_then_changing_season_turns_nothing_on(
    page,
):
    # The reported sequence: Players filter on top of "All Teams" clears Teams, then
    # moving through seasons must not tick any school the user never touched.
    page.click("#players-toggle-btn")
    page.fill("#players-input", "Akron")
    page.wait_for_selector("#players-dropdown:not([hidden]) .player-option")
    page.click("#players-dropdown .player-option >> nth=0")
    assert _checked_teams(page) == []

    _switch_season(page, "2024")
    _switch_season(page, "2025")

    assert _checked_teams(page) == []
