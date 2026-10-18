"""Percentile rules: a pool is one exact position above the threshold, and tied values share a rank."""

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


RANK_JS = """
async ([pool, key, higherIsBetter, value]) => {
  const d = await import('/data.js');
  return d.rankAndPercentile(pool, key, higherIsBetter, value);
}
"""

# Loads synthetic rows as the applied slice, then reads the ED and DI pools and one player's percentile.
POOLS_JS = """
async ([rows, selectedPosition, threshold]) => {
  const d = await import('/data.js');
  const thresholdField = d.metadata.pass_rush.threshold_field;
  d.setCurrentSlice(
    rows.map(([player, position, opportunities, m]) => ({ player, position, [thresholdField]: opportunities, m })),
    'pass_rush'
  );
  d.setAppliedFilters({
    ...d.appliedFilters,
    category: 'pass_rush',
    position: selectedPosition,
    threshold: String(threshold),
  });

  const names = (pool) => pool.map((r) => r.player);
  const ed = d.positionPool('ED');
  const di = d.positionPool('DI');
  const e2 = ed.find((r) => r.player === 'e2');
  return {
    ed: names(ed),
    di: names(di),
    edPercentile: e2 ? d.rankAndPercentile(ed, 'm', true, e2.m).percentile : null,
    combinedPercentile: e2 ? d.rankAndPercentile(ed.concat(di), 'm', true, e2.m).percentile : null,
  };
}
"""

# (player, position, opportunities, metric value). e4 falls below a threshold of 100.
ROWS = [
    ("e1", "ED", 300, 10),
    ("e2", "ED", 300, 20),
    ("e3", "ED", 300, 30),
    ("e4", "ED", 50, 99),
    ("d1", "DI", 300, 40),
    ("d2", "DI", 300, 50),
]


def _pool(*values):
    return [{"m": v} for v in values]


def _rank(page, pool, higher_is_better, value):
    return page.evaluate(RANK_JS, [pool, "m", higher_is_better, value])


def _pools(page, selected_position, threshold):
    return page.evaluate(POOLS_JS, [ROWS, selected_position, threshold])


def test_pool_holds_only_the_exact_position_above_the_threshold(page):
    result = _pools(page, "ED", 100)

    assert result["ed"] == ["e1", "e2", "e3"]
    assert result["di"] == ["d1", "d2"]


def test_threshold_is_a_hard_gate_on_pool_membership(page):
    assert _pools(page, "ED", 0)["ed"] == ["e1", "e2", "e3", "e4"]
    assert _pools(page, "ED", 400) == {
        "ed": [],
        "di": [],
        "edPercentile": None,
        "combinedPercentile": None,
    }


def test_percentile_is_the_same_whichever_position_is_selected(page):
    on_ed = _pools(page, "ED", 100)
    on_di = _pools(page, "DI", 100)

    assert on_ed["ed"] == on_di["ed"]
    assert on_ed["edPercentile"] == on_di["edPercentile"] == 50


def test_ranking_over_a_combined_pool_would_give_a_different_answer(page):
    # This is why pools are partitioned: e2 is 50th among the EDs but 25th once DIs are mixed in.
    result = _pools(page, "ED", 100)

    assert result["edPercentile"] == 50
    assert result["combinedPercentile"] == 25


def test_tied_values_share_one_rank_and_percentile(page):
    pool = _pool(10, 20, 20, 30)

    assert _rank(page, pool, True, 30) == {"rank": 1, "n": 4, "percentile": 100}
    assert _rank(page, pool, True, 20) == {"rank": 2, "n": 4, "percentile": 67}

    # Competition ranking: the next value skips rank 3, because two players share rank 2.
    assert _rank(page, pool, True, 10) == {"rank": 4, "n": 4, "percentile": 0}


def test_lower_is_better_flips_the_direction(page):
    pool = _pool(1, 2, 2, 3)

    assert _rank(page, pool, False, 1) == {"rank": 1, "n": 4, "percentile": 100}
    assert _rank(page, pool, False, 2) == {"rank": 2, "n": 4, "percentile": 67}
    assert _rank(page, pool, False, 3) == {"rank": 4, "n": 4, "percentile": 0}


def test_everyone_tied_shares_the_best_rank(page):
    assert _rank(page, _pool(5, 5, 5), True, 5) == {
        "rank": 1,
        "n": 3,
        "percentile": 100,
    }


def test_pool_order_never_changes_the_result(page):
    expected = {"rank": 2, "n": 4, "percentile": 67}

    for order in ([10, 20, 20, 30], [30, 20, 10, 20], [20, 30, 20, 10]):
        assert _rank(page, _pool(*order), True, 20) == expected


def test_missing_values_are_left_out_of_the_pool(page):
    pool = _pool(10, None, 20, 30)

    assert _rank(page, pool, True, 20) == {"rank": 2, "n": 3, "percentile": 50}


def test_no_result_without_a_value_or_without_two_players(page):
    assert _rank(page, _pool(10, 20), True, None) is None
    assert _rank(page, _pool(10), True, 10) is None
    assert _rank(page, [], True, 10) is None
