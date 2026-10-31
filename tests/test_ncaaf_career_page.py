"""The NCAAF Career page: Status Filter, two threshold bars, one pool."""

from __future__ import annotations

import pytest
from config import NCAAF_CAREER_DEFAULT_THRESHOLDS, CareerStatus
from database.db_models import (
    NCAAFPassBlockCareerMember,
    NCAAFPassBlockStat,
    NCAAFPassRushCareerMember,
    NCAAFPassRushStat,
    NCAAFTeam,
)
from main import SessionLocal

JOINED = CareerStatus.JOINED_NFL.value
POTENTIAL = CareerStatus.POTENTIAL_DRAFTEES.value
AKRON_ID = 102

# The default bars of the front 7 (Joined NFL stricter than Potential Draftees).
DEFAULTS = NCAAF_CAREER_DEFAULT_THRESHOLDS["pass_rush"]
JOINED_BAR = DEFAULTS[JOINED]
POTENTIAL_BAR = DEFAULTS[POTENTIAL]

# player id -> (status, pass rush opportunities), set around the default bars: only
# 1, 2 and 5 clear the bar of their own status. Player 5 only lifts the Potential
# Draftees slider ceiling, so that bar can be raised past player 2.
PLAYERS = {
    1: (JOINED, JOINED_BAR + 100),
    2: (POTENTIAL, POTENTIAL_BAR + 50),
    3: (POTENTIAL, POTENTIAL_BAR - 50),
    4: (JOINED, JOINED_BAR - 50),
    5: (POTENTIAL, POTENTIAL_BAR + 150),
}


@pytest.fixture()
def seeded_career_page_db():
    with SessionLocal() as db:
        for model in (
            NCAAFPassRushStat,
            NCAAFPassBlockStat,
            NCAAFPassRushCareerMember,
            NCAAFPassBlockCareerMember,
            NCAAFTeam,
        ):
            db.query(model).delete()

        db.add(NCAAFTeam(franchise_id=AKRON_ID, full_name="Akron"))

        for player_id, (status, opportunities) in PLAYERS.items():
            db.add(
                NCAAFPassRushStat(
                    season=2025,
                    position="ED",
                    team_code=AKRON_ID,
                    conference="MAC",
                    player_id=player_id,
                    player=f"Player {player_id}",
                    abbr_name=f"P. {player_id}",
                    games=12,
                    pr_opp=opportunities,
                    tps_pr_opp=opportunities // 2,
                    pass_cov_percent=10.0,
                    tps_pass_cov_percent=10.0,
                    win_rate=10.0 + player_id,
                    tps_win_rate=10.0,
                    pressure_rate=10.0,
                    tps_pressure_rate=10.0,
                    havoc_rate=5.0,
                    tps_havoc_rate=5.0,
                    prp=5.0 + player_id,
                    tps_prp=5.0,
                    pass_rush_snaps=90,
                    pass_play_snaps=100,
                    tps_pass_rush_snaps=40,
                    tps_pass_play_snaps=50,
                )
            )
            db.add(NCAAFPassRushCareerMember(player_id=player_id, status=status))

        db.commit()

    yield


@pytest.fixture()
def page(live_server_url, seeded_career_page_db):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{live_server_url}/ncaaf-career")

        # The app has finished loading once it has drawn the chart: the metadata and the
        # applied filters come first, then the logos preload, then the first render.
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters) && d.currentFiltered.length > 0 && !!document.querySelector('#chart').layout; }"
        )

        yield pg
        browser.close()


def _pool_ids(page) -> list[int]:
    return page.evaluate("""async () => {
            const d = await import('/data.js');
            return d.currentFiltered.map(r => r.player_id).sort((a, b) => a - b);
        }""")


def _applied(page) -> dict:
    return page.evaluate(
        "async () => { const d = await import('/data.js'); return d.appliedFilters; }"
    )


def _set_bar(page, number_id, value):
    page.fill(number_id, str(value))
    page.dispatch_event(number_id, "change")


def _toggle_status(page, checkbox_id):
    """Open the Status dropdown, tick or untick one status, and close it again."""
    page.click("#status-toggle-btn")
    page.click(checkbox_id)
    page.click("#status-toggle-btn")


def _apply_and_wait(page, key, value):
    page.click("#apply-filters")
    page.wait_for_function(
        "args => import('/data.js').then(d => String(d.appliedFilters[args.key]) === args.value)",
        arg=dict(key=key, value=str(value)),
    )


def _is_muted(page, control_id):
    return page.eval_on_selector(control_id, "el => el.classList.contains('is-muted')")


def test_the_page_shows_a_status_dropdown_and_two_bars_and_no_season(page):
    assert page.is_hidden(".control-season")
    assert page.is_visible("#status-control")
    assert page.is_hidden("#status-dropdown")
    assert page.is_visible("#threshold-control")
    assert page.is_visible("#potential-threshold-control")


def test_only_potential_draftees_is_lit_at_first(page):
    assert not page.is_checked("#status-joined")
    assert page.is_checked("#status-potential")
    assert page.inner_text("#status-select-summary") == "Potential Draftees"
    assert _applied(page)["statuses"] == POTENTIAL
    assert _is_muted(page, "#threshold-control")
    assert not _is_muted(page, "#potential-threshold-control")


def test_the_status_summary_follows_the_ticks(page):
    page.click("#status-toggle-btn")
    page.click("#status-joined")

    assert page.inner_text("#status-select-summary") == "All Status"

    page.click("#status-potential")

    assert page.inner_text("#status-select-summary") == "Joined NFL"

    page.click("#status-joined")

    assert page.inner_text("#status-select-summary") == "No Status"


def test_the_bars_start_at_the_defaults_of_their_own_status(page):
    assert page.input_value("#threshold-number") == str(JOINED_BAR)
    assert page.input_value("#threshold-potential-number") == str(POTENTIAL_BAR)

    applied = _applied(page)

    assert applied["season"] == "Career"
    assert applied["threshold"] == str(JOINED_BAR)
    assert applied["potentialThreshold"] == str(POTENTIAL_BAR)


def test_each_player_must_clear_the_bar_of_his_own_status(page):
    assert _pool_ids(page) == [1, 2, 5]


def test_lighting_joined_nfl_only_changes_the_dimming_and_never_the_pool(page):
    _toggle_status(page, "#status-joined")

    assert not _is_muted(page, "#threshold-control")
    assert page.eval_on_selector(
        "#apply-filters", "el => el.classList.contains('pending')"
    )

    _apply_and_wait(page, "statuses", f"{JOINED},{POTENTIAL}")

    assert _pool_ids(page) == [1, 2, 5]


def test_a_switched_off_status_still_counts_toward_the_pool_through_its_bar(page):
    # Joined NFL is off at first, yet lowering its bar brings player 4 into the pool.
    _set_bar(page, "#threshold-number", JOINED_BAR - 60)
    _apply_and_wait(page, "threshold", JOINED_BAR - 60)

    assert _pool_ids(page) == [1, 2, 4, 5]


def test_raising_one_bar_changes_only_that_statuss_players(page):
    _set_bar(page, "#threshold-potential-number", POTENTIAL_BAR + 60)
    _apply_and_wait(page, "potentialThreshold", POTENTIAL_BAR + 60)

    assert _pool_ids(page) == [1, 5]


def test_the_chart_title_names_career_and_the_subtitle_both_bars(page):
    title = page.evaluate("document.querySelector('#chart').layout.title")

    assert "Career" in title["text"]
    assert (
        f"{JOINED_BAR} (Joined NFL) / {POTENTIAL_BAR} (Potential Draftees)"
        in title["subtitle"]["text"]
    )


def test_a_changed_bar_lights_apply_until_it_is_applied(page):
    assert not page.eval_on_selector(
        "#apply-filters", "el => el.classList.contains('pending')"
    )

    _set_bar(page, "#threshold-potential-number", POTENTIAL_BAR - 20)

    assert page.eval_on_selector(
        "#apply-filters", "el => el.classList.contains('pending')"
    )


def _lit_players(page) -> list[int]:
    """The ids of the plotted players whose label is fully opaque (not dimmed)."""
    return page.evaluate("""async () => {
            const d = await import('/data.js');
            const colors = document.querySelector('#chart').data[0].textfont.color;
            const alpha = (color) => Number(color.match(/,([0-9.]+)\\)$/)[1]);
            return d.currentFiltered
                .filter((r, i) => alpha(colors[i]) === 1)
                .map((r) => r.player_id)
                .sort((a, b) => a - b);
        }""")


def test_no_team_is_picked_at_first_so_only_the_lit_status_is_highlighted(page):
    assert page.inner_text("#teams-select-summary") == "No Teams"
    assert _lit_players(page) == [2, 5]


def test_lighting_a_status_highlights_its_players(page):
    _toggle_status(page, "#status-joined")
    _apply_and_wait(page, "statuses", f"{JOINED},{POTENTIAL}")

    assert _lit_players(page) == [1, 2, 5]


def test_a_chosen_team_is_highlighted_whatever_the_status(page):
    page.click("#teams-toggle-btn")
    page.click(f'#teams-checklist input[value="{AKRON_ID}"]')
    page.click("#teams-toggle-btn")
    _apply_and_wait(page, "teams", AKRON_ID)

    assert _lit_players(page) == [1, 2, 5]
    assert _pool_ids(page) == [1, 2, 5]


def test_a_picked_player_is_highlighted_whatever_the_status(page):
    page.click("#players-toggle-btn")
    page.fill("#players-input", "Player 1")
    page.click("#players-dropdown .player-option")
    _apply_and_wait(page, "players", "Player 1")

    assert _lit_players(page) == [1, 2, 5]


def test_the_season_pages_keep_one_bar_and_no_status_filter(
    live_server_url, seeded_ncaaf_db
):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{live_server_url}/ncaaf-season")
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters); }"
        )

        assert pg.is_visible(".control-season")
        assert pg.is_hidden("#status-control")
        assert pg.is_hidden("#potential-threshold-control")

        applied = pg.evaluate("async () => (await import('/data.js')).appliedFilters")

        assert "potentialThreshold" not in applied
        assert "statuses" not in applied

        browser.close()
