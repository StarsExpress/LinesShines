"""The NCAAF Career Teams checklist places each member by his last season's conference.

A school that changed conference is two entries there: UCLA's Pac-12 members (last year 2023
or earlier) and its B1G members (last year 2024 or later) tick and highlight separately.
"""

from __future__ import annotations

import pytest
from conftest import wait_until
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
OPPORTUNITIES = NCAAF_CAREER_DEFAULT_THRESHOLDS["pass_rush"][JOINED] + 100

UCLA_ID = 324
TEXAS_ID = 311
UCLA_PAC_12 = f"{UCLA_ID}|Pac-12"
UCLA_B1G = f"{UCLA_ID}|B1G"
TEXAS_BIG_12 = f"{TEXAS_ID}|Big 12"
TEXAS_SEC = f"{TEXAS_ID}|SEC"

# Player ID -> (label on chart, name, school, last season, that season's conference).
MEMBERS = {
    1: ("L. Latu", "Laiatu Latu", UCLA_ID, 2023, "Pac-12"),
    2: ("L. Bruin", "Later Bruin", UCLA_ID, 2025, "B1G"),
    3: ("V. Broughton", "Vernon Broughton", TEXAS_ID, 2024, "SEC"),
    4: ("E. Longhorn", "Earlier Longhorn", TEXAS_ID, 2023, "Big 12"),
}

CAREER_READY_JS = "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters) && d.currentFiltered.length > 0 && !!document.querySelector('#chart').layout; }"


@pytest.fixture()
def seeded_split_conference_db():
    with SessionLocal() as db:
        for model in (
            NCAAFPassRushStat,
            NCAAFPassBlockStat,
            NCAAFPassRushCareerMember,
            NCAAFPassBlockCareerMember,
            NCAAFTeam,
        ):
            db.query(model).delete()

        db.add(NCAAFTeam(franchise_id=UCLA_ID, full_name="UCLA"))
        db.add(NCAAFTeam(franchise_id=TEXAS_ID, full_name="Texas"))

        for player_id, (label, name, team, season, conference) in MEMBERS.items():
            db.add(
                NCAAFPassRushStat(
                    season=season,
                    position="ED",
                    team_code=team,
                    conference=conference,
                    player_id=player_id,
                    player=name,
                    abbr_name=label,
                    games=12,
                    pr_opp=OPPORTUNITIES,
                    tps_pr_opp=OPPORTUNITIES // 2,
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
            db.add(NCAAFPassRushCareerMember(player_id=player_id, status=JOINED))

        db.commit()

    yield


@pytest.fixture()
def page(live_server_url, seeded_split_conference_db, open_page):
    return open_page(
        f"{live_server_url}/ncaaf-career",
        viewport={"width": 1280, "height": 900},
        ready_js=CAREER_READY_JS,
        settle=True,
    )


def _open_teams(page):
    page.click("#teams-toggle-btn")


def _box(key):
    return f"#teams-checklist input[value='{key}']"


def _column_values(page, conference):
    """The checklist keys listed under one conference's header."""
    return page.evaluate(
        """conference => {
            const column = [...document.querySelectorAll('#teams-checklist .teams-column')]
                .find(c => c.querySelector('.teams-column-header').textContent.trim() === conference);
            return column ? [...column.querySelectorAll('input')].map(box => box.value) : null;
        }""",
        conference,
    )


def _checked(page):
    return sorted(
        page.eval_on_selector_all(
            "#teams-checklist input:checked", "boxes => boxes.map(box => box.value)"
        )
    )


def _select_only(page, *keys):
    """Clear every box, then tick `keys`, with the dropdown left closed."""
    _open_teams(page)
    page.click("#teams-select-none")
    for key in keys:
        page.check(_box(key))
    _open_teams(page)


def _apply_and_read_lit(page):
    """Apply, wait for the chart to carry the new Teams filter, and return the labels not dimmed."""
    page.click("#apply-filters")
    expected = ",".join(sorted(_checked(page)))
    wait_until(
        page,
        "expected => import('/data.js').then(d => d.appliedFilters.teams === expected)",
        expected,
    )
    page.wait_for_load_state("networkidle")

    return page.evaluate("""async () => {
        const c = await import('/config.js');
        const trace = document.querySelector('#chart').data[0];
        const dimmed = `,${c.DIM_OPACITY.label})`;
        return trace.text.filter((_, i) => !trace.textfont.color[i].endsWith(dimmed)).sort();
    }""")


def test_a_school_in_two_conferences_is_listed_under_each(page):
    _open_teams(page)

    assert _column_values(page, "Pac-12") == [UCLA_PAC_12]
    assert _column_values(page, "B1G") == [UCLA_B1G]
    assert _column_values(page, "Big 12") == [TEXAS_BIG_12]
    assert _column_values(page, "SEC") == [TEXAS_SEC]
    # Career opens with no school ticked (the Status Filter is what lights players).
    assert _checked(page) == []


def test_ticking_one_conferences_school_leaves_the_same_school_in_the_other_alone(page):
    _open_teams(page)
    page.check(_box(UCLA_PAC_12))

    assert _checked(page) == [UCLA_PAC_12]

    page.check(_box(UCLA_B1G))
    page.uncheck(_box(UCLA_PAC_12))

    assert _checked(page) == [UCLA_B1G]


def test_a_conference_button_selects_only_that_conferences_entries(page):
    _open_teams(page)
    page.click("#teams-select-none")
    page.click("#teams-checklist .teams-column-header >> text='Pac-12'")

    assert _checked(page) == [UCLA_PAC_12]


def test_latu_is_lit_by_ucla_in_the_pac_12_and_not_by_ucla_in_the_b1g(page):
    _select_only(page, UCLA_PAC_12)
    assert _apply_and_read_lit(page) == ["L. Latu"]

    _select_only(page, UCLA_B1G)
    assert _apply_and_read_lit(page) == ["L. Bruin"]


def test_broughton_is_lit_by_texas_in_the_sec_not_the_big_12(page):
    # His last year is 2024, so the four earlier Big 12 years do not place him.
    _select_only(page, TEXAS_SEC)
    assert _apply_and_read_lit(page) == ["V. Broughton"]

    _select_only(page, TEXAS_BIG_12)
    assert _apply_and_read_lit(page) == ["E. Longhorn"]


def test_the_summary_names_the_school_of_a_single_entry(page):
    _select_only(page, UCLA_B1G)

    assert page.inner_text("#teams-select-summary").strip() == "UCLA"
