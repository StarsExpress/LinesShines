"""Linemate Card roster: the "Card" button column opens a teammate's own card."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


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

    assert len(set(result["positions"])) >= 2, "fixture needs two positions on the line"

    assert result["opened"], "clicking the buttons opened nothing"
    assert [f"Open {name}'s card" for name in result["opened"]] == result["clicked"]


def test_clicking_a_card_that_is_already_open_does_not_open_a_second(page):
    result = page.evaluate(BASE_CASE_JS)

    assert result == {"afterFirst": 1, "afterSecond": 1}


def test_a_card_for_another_position_ranks_among_his_own_position(page):
    result = page.evaluate(POOL_JS)

    assert not result.get("skipped"), "the fixture needs a player at a second position"
    assert result["text"] == result["expected"]


def test_the_card_template_titles_its_table_and_summary_sections():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    template = html[
        html.index(
            'class="scout-card-panel"',
            html.index('<template id="linemate-card-template">'),
        ) :
    ]

    headings = re.findall(r'<h4 class="([^"]*)">(.*?)</h4>', template, re.S)
    section_titles = [
        next(
            line.strip()
            for line in re.sub(r"<[^>]*>", "\n", text).splitlines()
            if line.strip()
        )
        for cls, text in headings
        if "scout-section-title" in cls
    ]

    assert section_titles[:2] == ["Individual", "Line Summary"]

    # The Individual heading sits above the roster table, the Summary heading inside its own wrapper.
    assert template.index("<span>Individual</span>") < template.index(
        "linemate-table-wrap"
    )
    assert template.index("linemate-summary-wrap") < template.index(">Line Summary<")

    # The Read | Sort switch lives on the Individual heading row, not in the notes.
    assert 'data-mode="read"' in headings[0][1] and 'data-mode="sort"' in headings[0][1]


# Synthetic teammates on one team, mixed positions, so percentile pools and the Linemate Card's own
# roster logic have something to work with (the seeded database has one player per position).
LINE_SETUP_JS = """
const d = await import('/data.js');
const cat = d.metadata[category];
const keys = Object.keys(cat.metrics);
const positions = Object.keys(cat.positions);
const records = Array.from({ length: count }, (_, i) => ({
  player: `P${i + 1}`, abbr_name: `P. ${i + 1}`, team: 'ARI',
  position: positions[i % positions.length], games: 17,
  [cat.threshold_field]: 400 - i * 10,
  ...Object.fromEntries(keys.map((k) => [k, (i + 1) * 5])),
}));
d.setCurrentSlice(records, category);
d.setAppliedFilters({ ...d.appliedFilters, category, position: positions[0], threshold: '100' });
"""

READ_TABLE_JS = "async ([category, count]) => {" + LINE_SETUP_JS + """
  const l = await import('/linemate-card.js');
  const table = document.createElement('table');
  table.className = 'linemate-table';
  document.body.appendChild(table);
  l.renderLinemateRoster({ mode: 'read', seeMore: false, rosterSort: { key: null, dir: 'asc' } }, records, table);
  const text = (c) => c.textContent.replace(/[▲▼]/g, '').trim();
  const out = {
    isRead: table.classList.contains('linemate-table--read'),
    head: [...table.querySelectorAll('thead tr')].map((tr) => [...tr.children].map(text)),
    sections: [...table.querySelectorAll('tbody tr')].reduce((acc, tr) => {
      if (tr.classList.contains('linemate-read-section')) acc.push([text(tr), tr.firstElementChild.colSpan, []]);
      else if (acc.length) acc[acc.length - 1][2].push(text(tr.firstElementChild));
      return acc;
    }, []),
    cardButtons: table.querySelectorAll('thead .linemate-row-card-btn').length,
    cardRows: table.querySelectorAll('thead .linemate-read-card-row').length,
    sortable: table.querySelectorAll('.sortable-th').length,
    frozen: table.querySelectorAll('.linemate-table-frozen').length,
    thresholdField: cat.threshold_field,
  };
  table.remove();
  return out;
}"""


def test_read_turns_the_roster_on_its_side_with_a_name_position_and_card_head(page):
    out = page.evaluate(READ_TABLE_JS, ["pass_rush", 4])

    assert out["isRead"]
    assert [row[0] for row in out["head"]] == ["Player", "Position", "Card"]

    assert out["head"][0][1:] == ["P. 1", "P. 2", "P. 3", "P. 4"]
    assert out["head"][1][1:] == ["ED", "DI", "ED", "DI"]
    assert out["cardButtons"] == 4 and out["cardRows"] == 1

    # Nothing sorts or freezes in Read.
    assert out["sortable"] == 0 and out["frozen"] == 0


def test_read_groups_the_dl_rows_and_leaves_the_ol_without_a_bonus_section(page):
    dl = page.evaluate(READ_TABLE_JS, ["pass_rush", 3])
    rows = {title: labels for title, _, labels in dl["sections"]}

    assert [title for title, _, _ in dl["sections"]] == [
        "Metadata",
        "Required Metrics",
        "Bonus Metrics",
    ]

    assert rows["Metadata"] == ["Games", dl["thresholdField"]]
    assert rows["Bonus Metrics"] == ["Pass Cov Percent", "TPS Pass Cov Percent"]
    assert "Win Rate" in rows["Required Metrics"]
    assert all(span == 4 for _, span, _ in dl["sections"])  # Label column + 3 players.

    ol = page.evaluate(READ_TABLE_JS, ["pass_block", 3])
    assert [title for title, _, _ in ol["sections"]] == ["Metadata", "Required Metrics"]


CARD_MODE_JS = (
    "async () => {"
    + "const category = 'pass_rush'; const count = 8;"
    + LINE_SETUP_JS
    + """
  const l = await import('/linemate-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.linemateCardTemplate.content.firstElementChild.cloneNode(true);
  const entry = {
    anchorRecord: records[0], roster: [], el: card, seeMore: false, mode: 'read', includeAnchor: false,
    rosterSort: { key: null, dir: 'asc' }, summarySort: { key: null, dir: 'asc' },
  };
  const snapshot = () => ({
    isRead: card.classList.contains('is-read'),
    isSort: card.classList.contains('is-sort'),
    seeMoreHidden: card.querySelector('.linemate-see-more').hidden,
    tableIsRead: card.querySelector('.linemate-table').classList.contains('linemate-table--read'),
    active: [...card.querySelectorAll('.merge-mode-btn.is-active')].map((b) => b.dataset.mode),
    summaryRows: [...card.querySelectorAll('.linemate-summary-table tbody tr')].map((tr) => tr.firstElementChild.textContent),
  });
  l.renderLinemateCardBody(entry);
  const read = snapshot();
  entry.mode = 'sort';
  l.renderLinemateCardBody(entry);
  return { read, sort: snapshot() };
}"""
)


def test_the_card_reads_by_default_hides_see_more_there_and_keeps_the_summary(page):
    out = page.evaluate(CARD_MODE_JS)

    assert out["read"]["isRead"] and not out["read"]["isSort"]
    assert out["read"]["tableIsRead"] and out["read"]["active"] == ["read"]
    assert out["read"]["seeMoreHidden"]  # Read shows every player.

    assert out["sort"]["isSort"] and not out["sort"]["isRead"]
    assert not out["sort"]["tableIsRead"] and out["sort"]["active"] == ["sort"]
    assert not out["sort"][
        "seeMoreHidden"
    ]  # Seven teammates: more than the default five.

    # The Line Summary does not depend on the mode (and leaves out Pass Cov Percent).
    assert out["read"]["summaryRows"] == out["sort"]["summaryRows"]
    assert "Win Rate" in out["read"]["summaryRows"]
    assert "Pass Cov Percent" not in out["read"]["summaryRows"]
