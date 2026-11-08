"""The NCAAF Career page: Status Filter, two threshold bars, one pool."""

from __future__ import annotations

import pytest
from conftest import APP_READY_JS, wait_until
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
PROSPECT = CareerStatus.PROSPECTS.value
AKRON_ID = 102

# The default bars of the front 7 (Joined NFL stricter than Prospects).
DEFAULTS = NCAAF_CAREER_DEFAULT_THRESHOLDS["pass_rush"]
JOINED_BAR = DEFAULTS[JOINED]
PROSPECT_BAR = DEFAULTS[PROSPECT]

# player id -> (status, pass rush opportunities), set around the default bars: only
# 1, 2 and 5 clear the bar of their own status. Player 5 only lifts the Prospects slider ceiling, so that bar can be raised past player 2.
PLAYERS = {
    1: (JOINED, JOINED_BAR + 100),
    2: (PROSPECT, PROSPECT_BAR + 50),
    3: (PROSPECT, PROSPECT_BAR - 50),
    4: (JOINED, JOINED_BAR - 50),
    5: (PROSPECT, PROSPECT_BAR + 150),
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


# The page is ready once it has its metadata and applied filters, a slice and a drawn chart.
CHART_READY_JS = "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters) && d.currentFiltered.length > 0 && !!document.querySelector('#chart').layout; }"


@pytest.fixture()
def page(live_server_url, seeded_career_page_db, open_page):
    # The first render can be redone once the page's last requests land (the logo preload),
    # which empties the chart for a moment, so open_page waits for the network to go quiet
    # and for the chart to be drawn again before a test reads it.
    return open_page(
        f"{live_server_url}/ncaaf-career",
        viewport={"width": 1280, "height": 900},
        ready_js=CHART_READY_JS,
        settle=True,
    )


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
    wait_until(
        page,
        "args => import('/data.js').then(d => String(d.appliedFilters[args.key]) === args.value)",
        dict(key=key, value=str(value)),
    )


def _is_muted(page, control_id):
    return page.eval_on_selector(control_id, "el => el.classList.contains('is-muted')")


def _opacity(page, control_id):
    return page.eval_on_selector(control_id, "el => getComputedStyle(el).opacity")


def test_the_page_shows_a_status_dropdown_and_two_bars_and_no_season(page):
    assert page.is_hidden(".control-season")
    assert page.is_visible("#status-control")
    assert page.is_hidden("#status-dropdown")
    assert page.is_visible("#threshold-control")
    assert page.is_visible("#prospect-threshold-control")


def test_only_prospects_is_lit_at_first(page):
    assert not page.is_checked("#status-joined")
    assert page.is_checked("#status-prospect")
    assert page.inner_text("#status-select-summary") == "Prospects"
    assert _applied(page)["statuses"] == PROSPECT


def test_both_bars_stay_fully_usable_whatever_status_is_lit(page):
    # Joined NFL is off at first; its bar is neither greyed nor tied to the Status Filter.
    for control in ("#threshold-control", "#prospect-threshold-control"):
        assert not _is_muted(page, control)
        assert _opacity(page, control) == "1"

    _toggle_status(page, "#status-prospect")

    for control in ("#threshold-control", "#prospect-threshold-control"):
        assert _opacity(page, control) == "1"

    _set_bar(page, "#threshold-number", "300")

    assert page.input_value("#threshold-number") == "300"


def test_the_status_summary_follows_the_ticks(page):
    page.click("#status-toggle-btn")
    page.click("#status-joined")

    assert page.inner_text("#status-select-summary") == "All Status"

    page.click("#status-prospect")

    assert page.inner_text("#status-select-summary") == "Joined NFL"

    page.click("#status-joined")

    assert page.inner_text("#status-select-summary") == "No Status"


def test_the_bars_start_at_the_defaults_of_their_own_status(page):
    assert page.input_value("#threshold-number") == str(JOINED_BAR)
    assert page.input_value("#threshold-prospect-number") == str(PROSPECT_BAR)

    applied = _applied(page)

    assert applied["season"] == "Career"
    assert applied["threshold"] == str(JOINED_BAR)
    assert applied["prospectThreshold"] == str(PROSPECT_BAR)


def test_each_player_must_clear_the_bar_of_his_own_status(page):
    assert _pool_ids(page) == [1, 2, 5]


def test_lighting_joined_nfl_only_changes_the_dimming_and_never_the_pool(page):
    _toggle_status(page, "#status-joined")

    assert not _is_muted(page, "#threshold-control")
    assert page.eval_on_selector(
        "#apply-filters", "el => el.classList.contains('pending')"
    )

    _apply_and_wait(page, "statuses", f"{JOINED},{PROSPECT}")

    assert _pool_ids(page) == [1, 2, 5]


def test_a_switched_off_status_still_counts_toward_the_pool_through_its_bar(page):
    # Joined NFL is off at first, yet lowering its bar brings player 4 into the pool.
    _set_bar(page, "#threshold-number", JOINED_BAR - 60)
    _apply_and_wait(page, "threshold", JOINED_BAR - 60)

    assert _pool_ids(page) == [1, 2, 4, 5]


def test_raising_one_bar_changes_only_that_statuss_players(page):
    _set_bar(page, "#threshold-prospect-number", PROSPECT_BAR + 60)
    _apply_and_wait(page, "prospectThreshold", PROSPECT_BAR + 60)

    assert _pool_ids(page) == [1, 5]


def test_the_chart_title_names_career_and_the_subtitle_counts_each_status(page):
    title = page.evaluate("document.querySelector('#chart').layout.title")
    subtitle = title["subtitle"]["text"]

    assert "Career" in title["text"]

    # Two lines: Prospects first, then Joined NFL, each with its own count and bar.
    prospect_line, joined_line = subtitle.split("<br>")

    assert prospect_line.startswith("2 Prospects with at least ")
    assert f"at least {PROSPECT_BAR} " in prospect_line
    assert joined_line.startswith("1 Joined NFL with at least ")
    assert f"at least {JOINED_BAR} " in joined_line


def test_a_changed_bar_lights_apply_until_it_is_applied(page):
    assert not page.eval_on_selector(
        "#apply-filters", "el => el.classList.contains('pending')"
    )

    _set_bar(page, "#threshold-prospect-number", PROSPECT_BAR - 20)

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
    _apply_and_wait(page, "statuses", f"{JOINED},{PROSPECT}")

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


def _flip_enable_status(page):
    page.click("#status-enabled")


def test_enable_status_is_on_at_first(page):
    assert page.is_checked("#status-enabled")
    assert page.is_enabled("#status-toggle-btn")
    assert page.inner_text("#status-select-summary") == "Prospects"


def test_turning_enable_status_off_lights_apply_and_takes_status_out_of_the_highlights(
    page,
):
    _flip_enable_status(page)

    assert page.eval_on_selector(
        "#apply-filters", "el => el.classList.contains('pending')"
    )
    assert page.inner_text("#status-select-summary") == "Off"
    assert page.is_disabled("#status-toggle-btn")

    _apply_and_wait(page, "statuses", "")

    assert _lit_players(page) == []
    assert _pool_ids(page) == [1, 2, 5]


def test_with_enable_status_off_only_teams_and_players_light_players(page):
    _flip_enable_status(page)

    page.click("#players-toggle-btn")
    page.fill("#players-input", "Player 1")
    page.click("#players-dropdown .player-option")
    page.click("#apply-filters")

    wait_until(
        page,
        "() => import('/data.js').then(d => d.appliedFilters.players === 'Player 1')",
    )

    assert _lit_players(page) == [1]


def test_the_ticks_are_kept_while_enable_status_is_off_and_come_back_on(page):
    _toggle_status(page, "#status-joined")
    _apply_and_wait(page, "statuses", f"{JOINED},{PROSPECT}")
    _flip_enable_status(page)
    _apply_and_wait(page, "statuses", "")

    assert page.is_checked("#status-joined")
    assert page.is_checked("#status-prospect")

    _flip_enable_status(page)
    _apply_and_wait(page, "statuses", f"{JOINED},{PROSPECT}")

    assert page.inner_text("#status-select-summary") == "All Status"
    assert _lit_players(page) == [1, 2, 5]


def test_the_nfl_alumni_roster_is_joined_nfl_only(page):
    # Anchor is a Prospect; his card's roster is the school's same-line players who
    # reached the NFL and clear the Joined NFL bar. Player 4 is Joined NFL but below the bar,
    # Player 5 clears his own bar but is a Prospect — neither is an alum.
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const l = await import('/linemate-card.js');
  const anchor = d.currentRecords.find((r) => r.player === 'Player 2');
  const roster = l.computeLinemateRoster(anchor);
  return { players: roster.map((r) => r.player), statuses: roster.map((r) => r.status) };
}""")

    assert out["players"] == ["Player 1"]
    assert set(out["statuses"]) == {"Joined NFL"}


def test_the_career_cards_are_named_nfl_alumni(page):
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const s = await import('/scout-card.js');
  const l = await import('/linemate-card.js');
  const anchor = d.currentRecords.find((r) => r.player === 'Player 2');
  s.openScoutCard(anchor);
  const button = document.querySelector('.card-linemate-toggle').textContent.trim();
  l.openLinemateCard(anchor);
  const title = document.querySelector('.linemate-card-title').textContent;
  return { button, title };
}""")

    assert out["button"] == "NFL Alumni"
    assert "NFL Alumni" in out["title"]
    assert "Linemate" not in out["title"]


def test_the_comparison_card_names_its_roster_column_nfl_alumni_in_both_layouts(page):
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const m = await import('/merge-card.js');
  const records = ['Player 1', 'Player 2'].map((name) => d.currentRecords.find((r) => r.player === name));
  const el = (cls, tag = 'div') => {
    const e = document.createElement(tag);
    e.className = cls;
    return e;
  };
  const render = (mode) => {
    const card = el('scout-card scout-card--merge', 'aside');
    const table = el('merge-table', 'table');
    card.append(el('merge-card-title'), el('merge-card-subtitle'), el('merge-card-pool'), el('merge-card-scope', 'li'), table);
    m.renderMergeCardBody(card, records, { key: null, dir: 'asc' }, mode);
    return { text: table.textContent, label: table.querySelector('button.merge-row-linemate-toggle').getAttribute('aria-label') };
  };
  return { read: render('read'), sort: render('sort') };
}""")

    for layout in ("read", "sort"):
        assert "NFL Alumni" in out[layout]["text"], layout
        assert "Linemates" not in out[layout]["text"], layout
        assert out[layout]["label"].startswith("NFL Alumni for "), layout


def test_a_career_player_card_marks_the_status_and_writes_the_bar_of_each_status(page):
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const s = await import('/scout-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, d.currentRecords.find((r) => r.player === 'Player 2'));
  const metadata = card.querySelector('.scout-metadata-table');
  return {
    labels: [...metadata.querySelectorAll('th')].map((e) => e.textContent),
    values: [...metadata.querySelectorAll('td')].map((e) => e.textContent),
    threshold: card.querySelector('.scout-card-threshold').textContent,
    bars: d.appliedThreshold(),
  };
}""")

    assert out["labels"][0] == "Status"
    assert out["values"][0] == "Prospects"
    joined_line, prospect_line = out["threshold"].split("\n")
    assert joined_line.startswith(f"Threshold: ≥ {out['bars']['joined']} ")
    assert joined_line.endswith("(Joined NFL).")
    assert prospect_line.startswith(f"≥ {out['bars']['prospect']} ")
    assert prospect_line.endswith("(Prospects).")


def test_the_nfl_alumni_card_has_no_line_summary(page):
    # Alumni never played together, so there is no line to summarise.
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const l = await import('/linemate-card.js');
  l.openLinemateCard(d.currentRecords.find((r) => r.player === 'Player 2'));
  const card = document.querySelector('.scout-card--linemate');
  const wrap = card.querySelector('.linemate-summary-wrap');
  return {
    hidden: getComputedStyle(wrap).display === 'none',
    rows: card.querySelectorAll('.linemate-summary-table tbody tr').length,
    heading: card.querySelector('.linemate-table-title > span').textContent,
    visibleText: card.innerText,
  };
}""")

    assert out["hidden"]
    assert out["rows"] == 0
    assert out["heading"] == "Players"
    assert "Line Summary" not in out["visibleText"]
    assert "RSWA" not in out["visibleText"]


def test_the_nfl_alumni_card_marks_the_status_and_states_only_the_joined_nfl_bar(page):
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const l = await import('/linemate-card.js');
  l.openLinemateCard(d.currentRecords.find((r) => r.player === 'Player 2'));
  return {
    note: document.querySelector('.linemate-card-roster-note').textContent,
    labels: [...document.querySelectorAll('.linemate-read-label')].map((e) => e.textContent),
    bars: d.appliedThreshold(),
  };
}""")

    assert out["note"].startswith(f"1 NFL alumnus with ≥ {out['bars']['joined']} ")
    assert "Prospect" not in out["note"]
    assert "Status" in out["labels"]


def test_a_career_comparison_card_marks_each_status_and_writes_both_bars(page):
    out = page.evaluate("""async () => {
  const d = await import('/data.js');
  const m = await import('/merge-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.mergeCardTemplate.content.firstElementChild.cloneNode(true);
  const records = ['Player 1', 'Player 2'].map((n) => d.currentRecords.find((r) => r.player === n));
  m.renderMergeCardBody(card, records, { key: null, dir: 'asc' });
  const row = [...card.querySelectorAll('tr')].find(
    (tr) => tr.querySelector('th')?.textContent === 'Status'
  );
  return {
    status: [...row.querySelectorAll('td')].map((e) => e.textContent),
    pool: card.querySelector('.merge-card-pool').textContent,
  };
}""")

    assert out["status"] == ["Joined NFL", "Prospects"]
    assert "(Joined NFL)" in out["pool"]
    assert "(Prospects)" in out["pool"]


def test_the_season_pages_keep_one_bar_and_no_status_filter(
    live_server_url, seeded_ncaaf_db, open_page
):
    pg = open_page(
        f"{live_server_url}/ncaaf-season",
        viewport={"width": 1280, "height": 900},
        ready_js=APP_READY_JS,
    )

    assert pg.is_visible(".control-season")
    assert pg.is_hidden("#status-control")
    assert pg.is_hidden("#prospect-threshold-control")

    applied = pg.evaluate("async () => (await import('/data.js')).appliedFilters")

    assert "prospectThreshold" not in applied
    assert "statuses" not in applied
