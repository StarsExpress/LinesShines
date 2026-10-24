"""Neutral metrics (Pass Cov Percent): ranked and shown, but never Color Coded."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
STYLES = (FRONTEND / "style.css").read_text(encoding="utf-8")


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
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters); }"
        )

        yield pg
        browser.close()


# Five ED players; each metric rises with the player's index, so ranks are predictable.
SETUP_JS = """
const d = await import('/data.js');
const cat = d.metadata.pass_rush;
const keys = Object.keys(cat.metrics);
const records = [1, 2, 3, 4, 5].map((n) => ({
  player: `P${n}`, abbr_name: `P${n}`, team: 'ARI', position: 'ED', games: 17,
  [cat.threshold_field]: 300,
  ...Object.fromEntries(keys.map((k) => [k, n * 10])),
}));
d.setCurrentSlice(records, 'pass_rush');
d.setAppliedFilters({ ...d.appliedFilters, category: 'pass_rush', position: 'ED', threshold: '100' });
"""

PLAYER_CARD_JS = "async () => {" + SETUP_JS + """
  const s = await import('/scout-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, records[0]);
  const labels = [...card.querySelectorAll('dt')].map((e) => e.textContent);
  const chips = {};
  card.querySelectorAll('dd.scout-stat-rank').forEach((dd, i) => {
    const chip = dd.querySelector('.scout-pct-chip');
    chips[labels[i]] = chip ? { cls: chip.className, text: chip.textContent } : null;
  });
  return { labels, chips };
}"""

MERGE_CARD_JS = "async () => {" + SETUP_JS + """
  const m = await import('/merge-card.js');
  const el = (cls, tag = 'div') => { const e = document.createElement(tag); e.className = cls; return e; };
  const card = el('scout-card scout-card--merge', 'aside');
  const table = el('merge-table', 'table');
  card.append(el('merge-card-title'), el('merge-card-subtitle'), el('merge-card-pool'), table);
  m.renderMergeCardBody(card, records, { key: null, dir: 'asc' });
  return [...table.querySelectorAll('.merge-pct-chip')].map((c) => c.className);
}"""


SECTIONS_JS = "async (category) => {" + """
  const d = await import('/data.js');
  const cat = d.metadata[category];
  const position = Object.keys(cat.positions)[0];
  const keys = Object.keys(cat.metrics);
  const records = [1, 2, 3].map((n) => ({
    player: `P${n}`, abbr_name: `P${n}`, team: 'ARI', position, games: 17,
    [cat.threshold_field]: 300,
    ...Object.fromEntries(keys.map((k) => [k, n * 10])),
  }));
  d.setCurrentSlice(records, category);
  d.setAppliedFilters({ ...d.appliedFilters, category, position, threshold: '100' });
  const s = await import('/scout-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, records[0]);
  const stats = card.querySelector('.scout-stats');
  return [...stats.children].reduce((out, el) => {
    if (el.tagName === 'H4') out.push([el.textContent, []]);
    else out[out.length - 1][1].push(...[...el.querySelectorAll('dt')].map((e) => e.textContent));
    return out;
  }, []);
}"""


def test_the_pass_rush_player_card_has_metadata_required_and_bonus_sections(page):
    sections = page.evaluate(SECTIONS_JS, "pass_rush")
    titles = [title for title, _ in sections]
    rows = dict(sections)

    assert titles == ["Metadata", "Required Metrics", "Bonus Metrics"]
    assert rows["Metadata"] == ["Games", "PR Opp"]

    assert rows["Bonus Metrics"] == ["Pass Cov Percent", "TPS Pass Cov Percent"]
    assert rows["Required Metrics"][:2] == ["Win Rate", "TPS Win Rate"]

    assert not {"Pass Cov Percent", "TPS Pass Cov Percent"} & set(
        rows["Required Metrics"]
    )


def test_the_pass_block_player_card_has_no_bonus_section(page):
    sections = page.evaluate(SECTIONS_JS, "pass_block")

    assert [title for title, _ in sections] == ["Metadata", "Required Metrics"]
    assert all(rows for _, rows in sections)


def test_the_line_summary_leaves_out_pass_cov_percent(page):
    result = page.evaluate("async () => {" + SETUP_JS + """
  const l = await import('/linemate-card.js');
  const summary = l.computeThreeMRSWA(records, cat);
  return { keys: Object.keys(summary), api: Object.fromEntries(keys.map((k) => [k, cat.metrics[k].line_summary])) };
}""")

    assert "Win Rate" in result["keys"]
    assert not {"Pass Cov Percent", "TPS Pass Cov Percent"} & set(result["keys"])
    assert result["api"]["Pass Cov Percent"] is False
    assert result["api"]["TPS Pass Cov Percent"] is False


def test_the_metric_order_puts_the_bonus_metrics_after_the_required_ones(page):
    metrics = page.evaluate(
        "async () => Object.keys((await import('/data.js')).metadata.pass_rush.metrics)"
    )

    assert metrics[0] == "Win Rate"
    assert metrics[-2:] == ["Pass Cov Percent", "TPS Pass Cov Percent"]


def test_player_card_explains_pass_cov_percent_after_the_threshold_line(page):
    notes = page.evaluate("async () => {" + SETUP_JS + """
  const s = await import('/scout-card.js');
  const dom = await import('/dom.js');
  const card = dom.els.scoutCardTemplate.content.firstElementChild.cloneNode(true);
  s.renderScoutCardStats(card, records[0]);
  return [...card.querySelectorAll('.scout-card-note')].map((e) => [e.textContent, e.hidden]);
}""")

    assert notes[1][0].startswith("Threshold: ≥ 100")
    assert notes[2] == [
        "Pass Cov Percent: drop to coverage frequency on pass plays.",
        False,
    ]


def test_player_card_shows_a_neutral_chip_with_rank_and_percentile(page):
    chips = page.evaluate(PLAYER_CARD_JS)["chips"]

    for label in ("Pass Cov Percent", "TPS Pass Cov Percent"):
        assert "scout-pct-neutral" in chips[label]["cls"]
        assert re.fullmatch(r"#\d+/5 · \d+(st|nd|rd|th) pct", chips[label]["text"])

    # Higher is better for this metric's direction: P1 has the lowest value, so it ranks last.
    assert chips["Pass Cov Percent"]["text"].startswith("#5/5")

    # Every other metric keeps its Color Code.
    assert "scout-pct-neutral" not in chips["Win Rate"]["cls"]


def test_merge_card_uses_the_neutral_chip_only_for_neutral_metrics(page):
    classes = page.evaluate(MERGE_CARD_JS)

    assert sum("merge-pct-neutral" in c for c in classes) > 0
    assert any("merge-pct-neutral" not in c for c in classes)


def test_pass_cov_percent_is_neutral_and_higher_is_better_so_its_axis_is_not_reversed(
    page,
):
    meta = page.evaluate(
        "async () => (await import('/data.js')).metadata.pass_rush.metrics['Pass Cov Percent']"
    )

    assert meta["neutral"] is True
    assert meta["higher_is_better"] is True


def test_the_linemate_card_uses_the_neutral_chip():
    source = (FRONTEND / "linemate-card.js").read_text(encoding="utf-8")

    assert 'meta.neutral === true ? "merge-pct-neutral"' in source


@pytest.mark.parametrize("cls", ["scout-pct-neutral", "merge-pct-neutral"])
def test_the_neutral_chip_text_is_readable(cls):
    body = re.search(rf"\.{cls}\s*\{{([^}}]*)\}}", STYLES).group(1)
    background = re.search(r"background:\s*(#[0-9a-fA-F]{6})", body).group(1)
    colour = re.search(r"(?<!-)color:\s*(#[0-9a-fA-F]{6})", body).group(1)

    def luminance(hex_):
        channels = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hi, lo = sorted((luminance(background), luminance(colour)), reverse=True)

    assert (hi + 0.05) / (lo + 0.05) >= 4.5
