"""The Player Card's Volume column: the count behind each rate, shown beside it and never ranked."""

from __future__ import annotations

import pytest
from conftest import APP_READY_JS


@pytest.fixture()
def page(live_server_url, open_page):
    return open_page(live_server_url, ready_js=APP_READY_JS)


# One Player Card on a synthetic five-player slice. Every count a metric names as its volume is
# set to a distinct number (its index plus 100), and `drop` removes one count from the record.
CARD_JS = """
async ({ category, position, drop }) => {
  const d = await import('/data.js');
  const cat = d.metadata[category];
  const keys = Object.keys(cat.metrics);
  const volumeKeys = [...new Set(keys.map((k) => cat.metrics[k].volume).filter(Boolean))];
  const records = [1, 2, 3, 4, 5].map((n) => ({
    player: `P${n}`, abbr_name: `P${n}`, team: 'ARI', position, games: 17,
    [cat.threshold_field]: 500,
    [`TPS ${cat.threshold_field}`]: 200,
    ...Object.fromEntries(keys.map((k) => [k, n * 10])),
    ...Object.fromEntries(volumeKeys.map((k, i) => [k, 100 + i])),
  }));
  if (drop) delete records[4][drop];
  d.setCurrentSlice(records, category);
  d.setAppliedFilters({ ...d.appliedFilters, category, position, threshold: '100' });
  const s = await import('/scout-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, records[4]);
  const sections = [...card.querySelectorAll('.scout-section-title')].map((h) => {
    const grid = h.nextElementSibling;
    const labels = [...grid.querySelectorAll('dt, th')].map((e) => e.textContent);
    const volumes = [...grid.querySelectorAll('dd.scout-stat-volume')].map((e) => e.textContent);
    return {
      title: h.textContent,
      labels,
      volumes,
      heads: [...grid.querySelectorAll('.scout-col-head')].map((e) => e.textContent),
      volumeChips: grid.querySelectorAll('dd.scout-stat-volume .scout-pct-chip').length,
    };
  });
  return { sections, volumeByLabel: Object.fromEntries(
    (() => {
      const grid = [...card.querySelectorAll('.scout-section-title')]
        .find((h) => h.textContent === 'Required Metrics').nextElementSibling;
      const labels = [...grid.querySelectorAll('dt')].map((e) => e.textContent);
      const volumes = [...grid.querySelectorAll('dd.scout-stat-volume')].map((e) => e.textContent);
      return labels.map((label, i) => [label, volumes[i]]);
    })()
  ) };
}
"""


def _card(page, category, position, drop=None):
    return page.evaluate(
        CARD_JS, {"category": category, "position": position, "drop": drop}
    )


def _required(card):
    return next(s for s in card["sections"] if s["title"] == "Required Metrics")


def test_the_front_7_required_metrics_show_the_count_behind_each_rate(page):
    volumes = _card(page, "pass_rush", "ED")["volumeByLabel"]

    # Counts are set to 100 + their index in the metric order: Wins, TPS Wins, Pressures, ...
    assert volumes["Win"] == "100"
    assert volumes["TPS Win"] == "101"
    assert volumes["Pressure"] == "102"
    assert volumes["TPS Pressure"] == "103"
    assert volumes["Havoc"] == "104"
    assert volumes["TPS Havoc"] == "105"


def test_a_metric_with_no_count_carries_a_dash(page):
    volumes = _card(page, "pass_rush", "ED")["volumeByLabel"]

    assert volumes["PRP"] == "–"
    assert volumes["TPS PRP"] == "–"


def test_the_required_section_has_a_volume_and_rate_header_and_no_other_section_does(
    page,
):
    sections = {s["title"]: s for s in _card(page, "pass_rush", "ED")["sections"]}

    assert sections["Required Metrics"]["heads"] == ["", "Volume", "Rate", ""]
    assert sections["Metadata"]["heads"] == []
    assert sections["Metadata"]["volumes"] == []
    assert sections["Bonus Metrics"]["heads"] == []

    # Pass Cov Percent has no count, so it carries the dash; the Batted Pass rows show theirs.
    assert sections["Bonus Metrics"]["volumes"] == ["–", "–", "106", "107"]


def test_the_volume_is_never_a_ranked_chip_and_the_row_labels_stay_the_metrics(page):
    required = _required(_card(page, "pass_rush", "ED"))

    assert required["volumeChips"] == 0
    assert required["labels"][:2] == ["Win", "TPS Win"]
    assert len(required["volumes"]) == len(required["labels"])


def test_a_missing_count_shows_the_same_dash(page):
    volumes = _card(page, "pass_rush", "ED", drop="Pressures")["volumeByLabel"]

    assert volumes["Pressure"] == "–"
    assert volumes["Win"] == "100"


def test_the_offensive_line_shows_its_pressures_havoc_and_tps_count(page):
    volumes = _card(page, "pass_block", "T")["volumeByLabel"]

    # The counts in metric order: TPS Non Spike PB Snaps, Pressures, TPS Pressures, Havoc, TPS Havoc.
    assert volumes["TPS Proportion"] == "100"
    assert volumes["Allowed Pressure"] == "101"
    assert volumes["TPS Allowed Pressure"] == "102"
    assert volumes["Allowed Havoc"] == "103"
    assert volumes["TPS Allowed Havoc"] == "104"
    assert volumes["PBE"] == "–"
    assert volumes["TPS PBE"] == "–"


def test_the_metadata_keeps_the_denominators(page):
    metadata = next(
        s
        for s in _card(page, "pass_block", "T")["sections"]
        if s["title"] == "Metadata"
    )

    assert metadata["labels"] == [
        "Games",
        "PB Snaps",
        "TPS PB Snaps",
    ]


def test_the_comparison_card_has_no_volume_column(page):
    count = page.evaluate("""async () => {
  const d = await import('/data.js');
  const cat = d.metadata.pass_rush;
  const keys = Object.keys(cat.metrics);
  const records = [1, 2, 3].map((n) => ({
    player: `P${n}`, abbr_name: `P${n}`, team: 'ARI', position: 'ED', games: 17,
    [cat.threshold_field]: 300, [`TPS ${cat.threshold_field}`]: 120, Wins: 9,
    ...Object.fromEntries(keys.map((k) => [k, n * 10])),
  }));
  d.setCurrentSlice(records, 'pass_rush');
  d.setAppliedFilters({ ...d.appliedFilters, category: 'pass_rush', position: 'ED', threshold: '100' });
  const m = await import('/merge-card.js');
  const el = (cls, tag = 'div') => { const e = document.createElement(tag); e.className = cls; return e; };
  const card = el('scout-card scout-card--merge', 'aside');
  const table = el('merge-table', 'table');
  card.append(el('merge-card-title'), el('merge-card-subtitle'), el('merge-card-pool'), el('merge-card-scope', 'li'), table);
  m.renderMergeCardBody(card, records, { key: null, dir: 'asc' });
  return card.querySelectorAll('.scout-stat-volume, .scout-col-head').length;
}""")

    assert count == 0


@pytest.mark.parametrize(
    "key, shown",
    [
        ("Win Rate", "Win"),
        ("TPS Pressure Rate", "TPS Pressure"),
        ("Havoc Rate", "Havoc"),
        ("Allowed Pressure %", "Allowed Pressure"),
        ("TPS Allowed Havoc %", "TPS Allowed Havoc"),
        ("TPS Proportion %", "TPS Proportion"),
        ("PRP", "PRP"),
        ("TPS PBE", "TPS PBE"),
        ("Pass Cov Percent", "Pass Cov Percent"),
    ],
)
def test_the_player_card_drops_the_percent_sign_and_rate_from_a_metric_name(
    page, key, shown
):
    name = page.evaluate(
        "async (key) => (await import('/scout-card.js')).metricCardName(key)", key
    )

    assert name == shown


def test_only_the_player_card_shortens_the_names(page):
    keys = page.evaluate(
        "async () => Object.keys((await import('/data.js')).metadata.pass_rush.metrics)"
    )

    # The metadata, and so the axis menus and the other cards, keep the full names.
    assert "Win Rate" in keys
    assert "Pressure Rate" in keys


OPEN_CARD_JS = """
async (category) => {
  const d = await import('/data.js');
  const cat = d.metadata[category];
  const position = Object.keys(cat.positions)[0];
  const keys = Object.keys(cat.metrics);
  const records = [1, 2, 3].map((n) => ({
    player: `P${n}`, abbr_name: `P${n}`, team: 'ARI', position, games: 17,
    [cat.threshold_field]: 500,
    [`TPS ${cat.threshold_field}`]: 200,
    ...Object.fromEntries(keys.map((k) => [k, n * 10])),
  }));
  d.setCurrentSlice(records, category);
  d.setAppliedFilters({ ...d.appliedFilters, category, position, threshold: '100' });
  const s = await import('/scout-card.js');
  s.openScoutCard(records[2]);
  const table = document.querySelector('.scout-card .scout-metadata-table');
  const style = getComputedStyle(table.querySelector('td'));
  return {
    labels: [...table.querySelectorAll('th')].map((e) => e.textContent),
    values: [...table.querySelectorAll('td')].map((e) => e.textContent),
    rows: table.rows.length,
    border: style.borderTopWidth,
  };
}
"""


def test_the_metadata_is_a_one_row_table_with_gridlines(page):
    page.set_viewport_size({"width": 1300, "height": 1000})
    out = page.evaluate(OPEN_CARD_JS, "pass_rush")

    assert out["labels"] == ["Games", "PR Opp", "TPS PR Opp"]
    assert out["values"] == ["17", "500", "200"]
    assert out["rows"] == 1
    assert out["border"] == "1px"


def test_the_offensive_line_metadata_table_keeps_every_cell(page):
    page.set_viewport_size({"width": 1300, "height": 1000})
    out = page.evaluate(OPEN_CARD_JS, "pass_block")

    assert out["labels"] == ["Games", "PB Snaps", "TPS PB Snaps"]
    assert out["values"] == ["17", "500", "200"]
    assert out["rows"] == 1


NOTES_JS = """
async (category) => {
  const d = await import('/data.js');
  const cat = d.metadata[category];
  const position = Object.keys(cat.positions)[0];
  const keys = Object.keys(cat.metrics);
  const records = [1, 2, 3].map((n) => ({
    player: `P${n}`, abbr_name: `P${n}`, team: 'ARI', position, games: 17,
    [cat.threshold_field]: 500, [`TPS ${cat.threshold_field}`]: 200,
    ...Object.fromEntries(keys.map((k) => [k, n * 10])),
  }));
  d.setCurrentSlice(records, category);
  d.setAppliedFilters({ ...d.appliedFilters, category, position, threshold: '100' });
  const s = await import('/scout-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, records[0]);
  return [...card.querySelectorAll('.scout-card-note')].map((e) => ({ text: e.textContent, hidden: e.hidden }));
}
"""


def test_the_offensive_line_card_says_once_that_only_non_spike_snaps_count(page):
    notes = page.evaluate(NOTES_JS, "pass_block")

    assert notes[1]["text"].startswith("Threshold: ≥ 100")
    assert notes[2] == {
        "text": "For OL, only non-spike pass block snaps are considered.",
        "hidden": False,
    }


def test_the_front_7_card_has_no_such_note(page):
    notes = page.evaluate(NOTES_JS, "pass_rush")

    assert notes[2]["hidden"] is True
    assert notes[2]["text"] == ""
