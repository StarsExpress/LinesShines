"""Comparison (Merge) Card table: the Read and Sort layouts come from one model."""

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


# The model on its own: plain strings stand in for players.
MODEL_JS = """
async ([players, thresholdField, metricKeys]) => {
  const m = await import('/merge-table-model.js');
  const model = m.buildMergeTableModel(players, thresholdField, metricKeys);
  const sort = m.sortLayout(model);
  const read = m.readLayout(model);
  const cell = (c) => [c.player, c.column.key];
  const row = (r) => ({ column: r.column.key, cells: r.cells.map(cell) });
  return {
    columns: model.columns.map((c) => [c.key, c.kind]),
    sortHead: sort.head.map((c) => c.key),
    sortBody: sort.body.map((r) => ({ player: r.player, cells: r.cells.map(cell) })),
    readHead: read.head.map(row),
    readBody: read.body.map(row),
  };
}
"""

# The real renderer on a detached card, using the app's own modules and metadata.
# Returns the table as text grids plus what the layout classes say.
RENDER_JS = """
async ([sort, mode, rows]) => {
  const d = await import('/data.js');
  const m = await import('/merge-card.js');
  const cat = d.metadata.pass_rush;
  const metricKeys = Object.keys(cat.metrics);
  const records = rows.map(([player, team, games, opportunities, base]) => ({
    player,
    abbr_name: player,
    team,
    position: 'ED',
    games,
    [cat.threshold_field]: opportunities,
    ...Object.fromEntries(metricKeys.map((key, i) => [key, base + i])),
  }));
  d.setCurrentSlice(records, 'pass_rush');
  d.setAppliedFilters({ ...d.appliedFilters, category: 'pass_rush', position: 'ED', threshold: '100' });

  const el = (cls, tag = 'div') => {
    const e = document.createElement(tag);
    e.className = cls;
    return e;
  };
  const card = el('scout-card scout-card--merge', 'aside');
  const table = el('merge-table', 'table');
  card.append(el('merge-card-title'), el('merge-card-subtitle'), el('merge-card-pool'), table);

  const sortState = { key: sort.key, dir: sort.dir };
  if (mode == null) m.renderMergeCardBody(card, records, sortState);
  else m.renderMergeCardBody(card, records, sortState, mode);

  const grid = (section) =>
    section
      ? [...section.querySelectorAll('tr')].map((tr) =>
          [...tr.children].map((c) => c.textContent.replace(/[▲▼]/g, '').trim())
        )
      : [];
  return {
    metricKeys,
    thresholdField: cat.threshold_field,
    tableIsRead: table.classList.contains('merge-table--read'),
    cardIsRead: card.classList.contains('is-read'),
    cardIsSort: card.classList.contains('is-sort'),
    head: grid(table.querySelector('thead')),
    body: grid(table.querySelector('tbody')),
    sortableHeaders: table.querySelectorAll('thead .sortable-th').length,
    sortStateAfter: sortState,
  };
}
"""

# (player, team, games, opportunities, base value). Every metric is base + its position, so the
# players rank the same way on each higher-is-better metric.
ROWS = [
    ("A. Alpha", "BUF", 7, 300, 10),
    ("B. Bravo", "MIA", 3, 280, 30),
    ("C. Charlie", "BUF", 9, 310, 20),
]
NO_SORT = {"key": None, "dir": "asc"}


def _model(page, players, threshold_field="PR Opp", metric_keys=("M1", "M2", "M3")):
    return page.evaluate(MODEL_JS, [players, threshold_field, list(metric_keys)])


def _render(page, sort=NO_SORT, mode=None):
    return page.evaluate(RENDER_JS, [sort, mode, ROWS])


def _names(result):
    """Player names in the order the table shows them, for either layout."""
    if result["tableIsRead"]:
        return result["head"][0][1:]

    return [row[0] for row in result["body"]]


def test_sort_layout_is_one_head_row_of_columns_and_one_row_per_player(page):
    out = _model(page, ["B", "A", "C"])

    assert out["sortHead"] == [
        "Player",
        "Team",
        "Linemates",
        "Games",
        "PR Opp",
        "M1",
        "M2",
        "M3",
    ]
    assert [row["player"] for row in out["sortBody"]] == ["B", "A", "C"]
    assert all(len(row["cells"]) == 8 for row in out["sortBody"])


def test_read_layout_heads_each_player_with_name_team_and_linemates(page):
    out = _model(page, ["B", "A", "C"])

    assert [row["column"] for row in out["readHead"]] == ["Player", "Team", "Linemates"]
    assert all(len(row["cells"]) == 3 for row in out["readHead"])


def test_read_layout_rows_are_games_the_threshold_field_then_the_metrics(page):
    out = _model(page, ["B", "A", "C"])

    assert [row["column"] for row in out["readBody"]] == [
        "Games",
        "PR Opp",
        "M1",
        "M2",
        "M3",
    ]


def test_read_layout_is_the_sort_layout_turned_on_its_side(page):
    players = ["B", "A", "C"]
    out = _model(page, players)
    read_rows = {
        row["column"]: row["cells"] for row in out["readHead"] + out["readBody"]
    }

    assert set(read_rows) == set(out["sortHead"])
    for i, sort_row in enumerate(out["sortBody"]):
        for j, column in enumerate(out["sortHead"]):
            assert read_rows[column][i] == sort_row["cells"][j] == [players[i], column]


def test_both_layouts_keep_the_player_order_they_are_given(page):
    out = _model(page, ["C", "A", "B"])

    assert [row["player"] for row in out["sortBody"]] == ["C", "A", "B"]
    for row in out["readHead"] + out["readBody"]:
        assert [player for player, _ in row["cells"]] == ["C", "A", "B"]


def test_with_no_players_both_layouts_are_empty_but_keep_their_rows(page):
    out = _model(page, [])

    assert out["sortBody"] == []
    assert [row["column"] for row in out["readHead"]] == ["Player", "Team", "Linemates"]
    assert all(row["cells"] == [] for row in out["readHead"] + out["readBody"])


def test_the_card_opens_in_read_by_default(page):
    out = _render(page)

    assert out["tableIsRead"] and out["cardIsRead"]
    assert not out["cardIsSort"]


def test_read_turns_the_table_on_its_side(page):
    out = _render(page, mode="read")

    assert [row[0] for row in out["head"]] == ["Player", "Team", "Linemates"]
    assert out["head"][0][1:] == ["A. Alpha", "B. Bravo", "C. Charlie"]
    assert out["head"][1][1:] == ["BUF", "MIA", "BUF"]
    assert out["head"][2][1:] == ["", "", ""]  # The Linemates buttons carry no text.
    assert [row[0] for row in out["body"]] == [
        "Games",
        out["thresholdField"],
        *out["metricKeys"],
    ]
    assert out["body"][0][1:] == ["7", "3", "9"]
    assert out["body"][1][1:] == ["300", "280", "310"]
    assert all(len(row) == 4 for row in out["head"] + out["body"])


def test_sort_keeps_the_original_layout(page):
    out = _render(page, mode="sort")

    assert not out["tableIsRead"] and out["cardIsSort"] and not out["cardIsRead"]
    assert out["head"] == [
        [
            "Player",
            "Team",
            "Linemates",
            "Games",
            out["thresholdField"],
            *out["metricKeys"],
        ]
    ]
    assert [row[0] for row in out["body"]] == ["A. Alpha", "B. Bravo", "C. Charlie"]
    assert all(len(row) == 5 + len(out["metricKeys"]) for row in out["body"])


def test_only_sort_has_sortable_headers(page):
    read = _render(page, mode="read")
    sort = _render(page, mode="sort")

    assert read["sortableHeaders"] == 0
    # Every column sorts except Linemates, which holds a button, not data.
    assert sort["sortableHeaders"] == 4 + len(sort["metricKeys"])


def test_read_follows_the_current_sort_order(page):
    by_metric = {"key": "M-placeholder", "dir": "desc"}
    first_metric = _render(page, mode="read")["metricKeys"][0]
    by_metric["key"] = first_metric

    read = _render(page, sort=by_metric, mode="read")
    sort = _render(page, sort=by_metric, mode="sort")

    assert _names(read) == _names(sort) == ["B. Bravo", "C. Charlie", "A. Alpha"]


def test_read_and_sort_follow_every_sort_the_same_way(page):
    for state, expected in [
        (NO_SORT, ["A. Alpha", "B. Bravo", "C. Charlie"]),
        ({"key": "Player", "dir": "desc"}, ["C. Charlie", "B. Bravo", "A. Alpha"]),
        ({"key": "Games", "dir": "desc"}, ["C. Charlie", "A. Alpha", "B. Bravo"]),
    ]:
        assert _names(_render(page, sort=state, mode="read")) == expected, state
        assert _names(_render(page, sort=state, mode="sort")) == expected, state


def test_read_and_sort_show_the_same_percentiles(page):
    read = _render(page, mode="read")
    sort = _render(page, mode="sort")

    metric_count = len(sort["metricKeys"])
    for i, row in enumerate(sort["body"]):
        player = row[0]
        for j in range(metric_count):
            column = read["head"][0][1:].index(player)
            assert read["body"][2 + j][1 + column] == row[5 + j], (player, j)


def test_rendering_never_changes_the_sort_state(page):
    state = {"key": "Games", "dir": "desc"}

    assert _render(page, sort=state, mode="read")["sortStateAfter"] == state
    assert _render(page, sort=state, mode="sort")["sortStateAfter"] == state
