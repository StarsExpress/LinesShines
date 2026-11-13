"""The page remembers the last axes (per category and position) and switches, separately for each View."""

from __future__ import annotations

import json

import pytest
from conftest import APP_READY_JS, wait_until
from test_ncaaf_career_page import seeded_career_page_db  # noqa: F401 (fixture)

NFL_KEY = "linesshines.prefs.v1.nfl-season"
CAREER_KEY = "linesshines.prefs.v1.ncaaf-career"

APPLIED_MATCHES_CONTROLS_JS = """
async () => {
  const d = await import('/data.js');
  const value = (id) => document.querySelector(id).value;
  const a = d.appliedFilters;
  return a.category === value('#category-select') && a.position === value('#position-select')
    && a.xMetric === value('#x-metric-select') && a.yMetric === value('#y-metric-select');
}
"""


@pytest.fixture()
def page(live_server_url, open_page):
    return open_page(live_server_url, ready_js=APP_READY_JS)


def _axes(page) -> list[str]:
    return page.evaluate(
        "() => [document.querySelector('#x-metric-select').value, document.querySelector('#y-metric-select').value]"
    )


def _options(page, selector: str) -> list[str]:
    return page.locator(f"{selector} option").evaluate_all("o => o.map(x => x.value)")


def _choose_other_axes(page, skip: int = 0) -> list[str]:
    """Picks an X and a Y different from the defaults (and from each other); `skip` makes another pair."""
    metrics = [m for m in _options(page, "#x-metric-select") if m not in _axes(page)]
    x, y = metrics[skip], metrics[skip + 1]
    page.select_option("#x-metric-select", x)
    page.select_option("#y-metric-select", y)

    return [x, y]


def _apply(page) -> None:
    page.click("#apply-filters")
    wait_until(page, APPLIED_MATCHES_CONTROLS_JS)


def _stored(page, key: str = NFL_KEY):
    raw = page.evaluate("(key) => localStorage.getItem(key)", key)
    return json.loads(raw) if raw else None


def _reload(page) -> None:
    page.reload()
    wait_until(page, APP_READY_JS)


def test_an_applied_pair_comes_back_after_a_reload(page):
    chosen = _choose_other_axes(page)
    _apply(page)

    _reload(page)

    assert _axes(page) == chosen


def test_a_pair_that_was_not_applied_is_not_remembered(page):
    defaults = _axes(page)
    _choose_other_axes(page)

    _reload(page)

    assert _axes(page) == defaults
    assert _stored(page) is None


def test_each_position_keeps_its_own_pair(page):
    ed_default = _axes(page)
    ed_pair = _choose_other_axes(page)
    _apply(page)

    # DI has nothing remembered, so it keeps whatever is selected now.
    page.select_option("#position-select", "DI")
    assert _axes(page) == ed_pair
    di_pair = _choose_other_axes(page, skip=2)
    _apply(page)

    page.select_option("#position-select", "ED")
    assert _axes(page) == ed_pair

    page.select_option("#position-select", "DI")
    assert _axes(page) == di_pair
    assert ed_pair != ed_default and di_pair != ed_pair

    _reload(page)
    assert _axes(page) == ed_pair
    page.select_option("#position-select", "DI")
    assert _axes(page) == di_pair


def test_each_category_keeps_its_own_pair(page):
    rush_pair = _choose_other_axes(page)
    _apply(page)

    page.select_option("#category-select", "pass_block")
    block_defaults = _axes(page)
    assert block_defaults == ["TPS Proportion %", "TPS PBE"]

    page.select_option("#category-select", "pass_rush")
    assert _axes(page) == rush_pair


def test_the_default_pair_is_not_stored_so_a_new_default_still_reaches_everyone(page):
    defaults = _axes(page)
    _choose_other_axes(page)
    _apply(page)
    assert _stored(page)["axes"]["pass_rush"]["ED"]

    # Picking the default pair again and applying it is how a visitor goes back: the entry is dropped.
    page.select_option("#x-metric-select", defaults[0])
    page.select_option("#y-metric-select", defaults[1])
    _apply(page)

    assert "ED" not in _stored(page)["axes"].get("pass_rush", {})

    _reload(page)
    assert _axes(page) == defaults


def test_the_switches_are_remembered(page):
    page.uncheck("#labels-toggle")
    page.check("#metric-notes-toggle")

    _reload(page)

    assert not page.is_checked("#labels-toggle")
    assert page.is_checked("#logos-toggle")
    assert page.is_checked("#metric-notes-toggle")


def test_a_remembered_metric_that_no_longer_exists_falls_back_to_the_default(page):
    defaults = _axes(page)
    page.evaluate(
        """(key) => localStorage.setItem(key, JSON.stringify({
            version: 1, axes: { pass_rush: { ED: { x: 'Gone Metric', y: 'Win Rate' } } }, switches: {} }))""",
        NFL_KEY,
    )

    _reload(page)

    assert _axes(page) == defaults


@pytest.mark.parametrize(
    "stored",
    [
        "not json",
        '{"version": 99, "axes": {}, "switches": {}}',
        "[1, 2]",
        '{"version": 1, "axes": 5}',
    ],
)
def test_text_that_cannot_be_read_is_ignored(page, stored):
    defaults = _axes(page)
    page.evaluate(
        "([key, value]) => localStorage.setItem(key, value)", [NFL_KEY, stored]
    )

    _reload(page)

    assert _axes(page) == defaults
    assert page.is_checked("#labels-toggle")


def test_the_page_works_where_storage_is_blocked(live_server_url, chromium_browser):
    page = chromium_browser.new_page()
    page.add_init_script("""
        for (const name of ['getItem', 'setItem', 'removeItem']) {
          Storage.prototype[name] = () => { throw new Error('storage blocked'); };
        }
        """)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(live_server_url)
    wait_until(page, APP_READY_JS)

    _choose_other_axes(page)
    _apply(page)
    page.uncheck("#labels-toggle")
    _reload(page)

    assert errors == []


def test_the_view_key_names_the_page(page):
    assert (
        page.evaluate("async () => (await import('/preferences.js')).viewKey()")
        == "nfl-season"
    )


def test_the_career_page_keeps_its_own_memory(
    live_server_url, seeded_career_page_db, open_page
):  # noqa: F811
    page = open_page(f"{live_server_url}/ncaaf-career", ready_js=APP_READY_JS)
    chosen = _choose_other_axes(page)
    _apply(page)
    page.uncheck("#logos-toggle")

    assert _stored(page, CAREER_KEY)["axes"]["pass_rush"]["ED"] == {
        "x": chosen[0],
        "y": chosen[1],
    }
    assert _stored(page, CAREER_KEY)["switches"] == {"logos": False}
    assert _stored(page, NFL_KEY) is None

    _reload(page)
    assert _axes(page) == chosen
    assert not page.is_checked("#logos-toggle")


def _reload_without_the_modules(page) -> None:
    """Reloads with main.js refused, so only the inline script in index.html can have restored a switch."""
    page.route("**/main.js*", lambda route: route.abort())
    page.reload()


def test_a_remembered_switch_is_drawn_before_the_modules_load(page):
    page.check("#metric-notes-toggle")
    page.uncheck("#labels-toggle")

    _reload_without_the_modules(page)

    assert page.is_checked("#metric-notes-toggle")
    assert not page.is_checked("#labels-toggle")
    assert page.is_checked("#logos-toggle")


def test_the_inline_script_reads_the_career_key_too(
    live_server_url, seeded_career_page_db, open_page  # noqa: F811
):
    page = open_page(f"{live_server_url}/ncaaf-career", ready_js=APP_READY_JS)
    page.check("#metric-notes-toggle")

    _reload_without_the_modules(page)

    assert page.is_checked("#metric-notes-toggle")
