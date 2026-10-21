"""Linemate Card roster: the "Card" button column opens a teammate's own card."""

from __future__ import annotations

import pytest


@pytest.fixture()
def page(live_server_url):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page()
        pg.goto(live_server_url)

        # The app has finished loading once it holds its metadata, its applied filters and a slice of records.
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters && d.currentRecords.length); }"
        )

        yield pg
        browser.close()


# Renders the real roster table for one record per position (so more than one position on the line),
# then reports the header, the buttons and what a click on each button hands to the card opener.
ROSTER_JS = """
async () => {
  const d = await import('/data.js');
  const l = await import('/linemate-card.js');

  const byPosition = {};
  d.currentRecords.forEach((r) => { byPosition[r.position] = byPosition[r.position] || r; });
  const records = Object.values(byPosition);

  const table = document.createElement('table');
  table.className = 'linemate-table';
  document.body.appendChild(table);
  l.renderLinemateRoster({ seeMore: true, rosterSort: { key: null, dir: 'asc' } }, records, table);

  const label = (th) => (th.querySelector('span') ? th.querySelector('span').textContent : th.textContent).trim();
  const heads = [...table.querySelectorAll('thead th')];
  const opened = [];
  l.setPlayerCardOpener((record) => opened.push(record.player));
  const buttons = [...table.querySelectorAll('.linemate-row-card-btn')];
  const clicked = buttons.map((b) => { b.click(); return b.getAttribute('aria-label'); });

  const result = {
    positions: records.map((r) => r.position),
    head: heads.slice(0, 4).map(label),
    cardHeadSortable: heads[1].classList.contains('sortable-th'),
    rows: table.querySelectorAll('tbody tr').length,
    buttons: buttons.length,
    cardCellIsSecond: [...table.querySelectorAll('tbody tr')].every((tr) => tr.children[1].classList.contains('linemate-table-card')),
    frozen: table.querySelectorAll('thead .linemate-table-frozen').length,
    clicked,
    opened,
  };
  table.remove();
  return result;
}
"""

# The real opener (scout-card.js's viewFloatingCard) behind the button: a second click must not add a second card.
BASE_CASE_JS = """
async () => {
  const d = await import('/data.js');
  const l = await import('/linemate-card.js');
  const s = await import('/scout-card.js');

  s.closeAllScoutCards();
  const record = d.currentRecords[0];
  const table = document.createElement('table');
  table.className = 'linemate-table';
  document.body.appendChild(table);
  l.renderLinemateRoster({ seeMore: true, rosterSort: { key: null, dir: 'asc' } }, [record], table);
  l.setPlayerCardOpener(s.viewFloatingCard);

  const button = table.querySelector('.linemate-row-card-btn');
  button.click();
  const afterFirst = s.scoutCards.size;
  button.click();
  const afterSecond = s.scoutCards.size;

  s.closeAllScoutCards();
  table.remove();
  return { afterFirst, afterSecond };
}
"""


# A Player Card for a player at another position than the plot's must rank him among his own position.
POOL_JS = """
async () => {
  const d = await import('/data.js');
  const dom = await import('/dom.js');
  const s = await import('/scout-card.js');

  const record = d.currentRecords.find((r) => r.position !== d.appliedFilters.position);
  if (!record) return { skipped: true };

  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, record);
  return {
    text: card.querySelector('.scout-card-pool').textContent,
    expected: `Percentiles calculated among ${d.positionPool(record.position).length} ${record.position}.`,
    plotPosition: d.appliedFilters.position,
    position: record.position,
  };
}
"""


def test_roster_has_a_card_button_column_between_player_and_position(page):
    result = page.evaluate(ROSTER_JS)

    assert result["head"] == ["Player", "Card", "Position", "Games"]
    assert result["cardHeadSortable"] is False
    assert result["buttons"] == result["rows"] > 0
    assert result["cardCellIsSecond"] is True
    assert result["frozen"] == 3, "Player, Card and Position must all stay frozen"


def test_each_button_opens_its_own_players_card_whatever_the_position(page):
    result = page.evaluate(ROSTER_JS)

    assert (
        len(set(result["positions"])) >= 2
    ), "the fixture needs two positions on the line"
    assert result["opened"], "clicking the buttons opened nothing"
    assert [f"Open {name}'s card" for name in result["opened"]] == result["clicked"]


def test_clicking_a_card_that_is_already_open_does_not_open_a_second(page):
    result = page.evaluate(BASE_CASE_JS)

    assert result == {"afterFirst": 1, "afterSecond": 1}


def test_a_card_for_another_position_ranks_among_his_own_position(page):
    result = page.evaluate(POOL_JS)

    assert not result.get("skipped"), "the fixture needs a player at a second position"
    assert result["text"] == result["expected"]
