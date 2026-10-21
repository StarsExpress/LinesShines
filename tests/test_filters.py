"""Teams and Players combine by union (OR); the threshold is a hard gate and Teams only highlights."""

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

        # The app has finished loading once it holds its metadata and its applied filters.
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters); }"
        )

        yield pg
        browser.close()


# The union rule lives inside render(), so this calls the real render() on synthetic rows and reads the trace it
# hands to Plotly. A label counts as dimmed when its text colour carries the dimmed opacity from config.js.
SPOTLIGHT_JS = """
async ([rows, teams, players, threshold]) => {
  const d = await import('/data.js');
  const r = await import('/render.js');
  const c = await import('/config.js');

  const cat = d.metadata.pass_rush;
  const [xKey, yKey] = Object.keys(cat.metrics);
  d.setCurrentSlice(
    rows.map(([player, team, opportunities], i) => ({
      player,
      abbr_name: player,
      team,
      position: 'ED',
      [cat.threshold_field]: opportunities,
      [xKey]: 10 + i,
      [yKey]: 20 + 2 * i,
    })),
    'pass_rush'
  );
  d.setAppliedFilters({
    ...d.appliedFilters,
    category: 'pass_rush',
    position: 'ED',
    xMetric: xKey,
    yMetric: yKey,
    threshold: String(threshold),
    teams,
    players,
  });

  let trace = null;
  const original = Plotly.react;
  Plotly.react = (...args) => {
    trace = args[1][0];
    return original.apply(Plotly, args);
  };
  try {
    r.render();
  } catch (error) {
    // Only the trace matters here; anything thrown after it was handed to Plotly is not under test.
    if (!trace) throw error;
  } finally {
    Plotly.react = original;
  }

  const dimmedEnding = `,${c.DIM_OPACITY.label})`;
  return trace.text.map((label, i) => [label, trace.textfont.color[i].endsWith(dimmedEnding)]);
}
"""

# (player, team, opportunities). With a threshold of 100, E. Low is below threshold and is never plotted.
ROWS = [
    ("A. Buf", "BUF", 300),
    ("B. Buf", "BUF", 300),
    ("C. Mia", "MIA", 300),
    ("D. Mia", "MIA", 300),
    ("E. Low", "BUF", 50),
]
THRESHOLD = 100
PLOTTED = {"A. Buf", "B. Buf", "C. Mia", "D. Mia"}


def _spotlight(page, teams="", players=""):
    result = page.evaluate(SPOTLIGHT_JS, [ROWS, teams, players, THRESHOLD])
    plotted = {label for label, _ in result}

    highlighted = {label for label, dimmed in result if not dimmed}
    return plotted, highlighted


def test_teams_alone_highlight_their_players(page):
    plotted, highlighted = _spotlight(page, teams="BUF")

    assert plotted == PLOTTED
    assert highlighted == {"A. Buf", "B. Buf"}


def test_players_alone_highlight_only_those_players(page):
    _, highlighted = _spotlight(page, players="C. Mia")

    assert highlighted == {"C. Mia"}


def test_teams_and_players_combine_as_a_union(page):
    # An intersection would highlight nobody here: C. Mia is not on a selected team.
    _, highlighted = _spotlight(page, teams="BUF", players="C. Mia")

    assert highlighted == {"A. Buf", "B. Buf", "C. Mia"}


def test_nothing_selected_dims_everyone(page):
    plotted, highlighted = _spotlight(page)

    assert plotted == PLOTTED
    assert highlighted == set()


def test_selection_never_changes_who_is_plotted(page):
    # Teams and Players only dim. They never add or remove a point, so the percentile pool is untouched.
    for teams, players in [
        ("", ""),
        ("BUF", ""),
        ("MIA", ""),
        ("BUF,MIA", ""),
        ("", "C. Mia"),
        ("BUF", "C. Mia"),
    ]:
        plotted, _ = _spotlight(page, teams=teams, players=players)

        assert plotted == PLOTTED, (teams, players)


def test_threshold_is_a_hard_gate_even_for_a_selected_player_or_team(page):
    # E. Low is on a selected team and is also selected by name, yet stays out because it is below threshold.
    plotted, highlighted = _spotlight(page, teams="BUF", players="E. Low")

    assert "E. Low" not in plotted
    assert "E. Low" not in highlighted
