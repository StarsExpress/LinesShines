"""evaluatePinnedImpact(): which Apply outcome a final filter combination implies."""

from __future__ import annotations

import pytest

FIELD = "PR Opp"


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

        yield pg
        browser.close()


def _state(season=2025, position="ED", threshold=230, category="pass_rush"):
    return dict(
        category=category, season=str(season), position=position, threshold=threshold
    )


def _rec(player, opp, position="ED"):
    return {"player": player, "position": position, FIELD: opp}


def _evaluate(page, applied, pending, pinned, pool):
    return page.evaluate(
        """async args => {
            const m = await import('/pinned-impact.js');
            return m.evaluatePinnedImpact(
                args.applied, args.pending, args.pinned, args.pool, args.field);
        }""",
        dict(applied=applied, pending=pending, pinned=pinned, pool=pool, field=FIELD),
    )


POOL = [_rec("A", 300), _rec("B", 250), _rec("C", 240)]


def test_category_change_resets_without_data(page):
    out = _evaluate(
        page, _state(), _state(category="pass_block"), ["A"], []
    )  # Empty pool: step 1 must not need data.
    assert out == "reset"


def test_position_change_resets(page):
    assert _evaluate(page, _state(), _state(position="DI"), ["A"], POOL) == "reset"


def test_nothing_changed_is_unaffected(page):
    assert _evaluate(page, _state(), _state(), ["A"], POOL) == "unaffected"


def test_threshold_loosened_is_unaffected_even_if_pool_lacks_player(page):
    out = _evaluate(page, _state(), _state(threshold=100), ["ghost"], POOL)
    assert out == "unaffected"


def test_threshold_tightened_all_clear(page):
    out = _evaluate(page, _state(), _state(threshold=240), ["A", "B", "C"], POOL)
    assert out == "unaffected"  # C is exactly 240: boundary is inclusive.


def test_threshold_tightened_one_falls_short(page):
    out = _evaluate(page, _state(), _state(threshold=241), ["A", "B", "C"], POOL)
    assert out == "reset"


def test_tighten_pinned_player_missing_from_pool_resets(page):
    out = _evaluate(page, _state(), _state(threshold=240), ["ghost"], POOL)
    assert out == "reset"


def test_season_change_all_present_is_refresh(page):
    pool = [_rec("A", 260), _rec("B", 230)]
    out = _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert out == "refresh"  # B exactly on the (230) threshold: inclusive.


def test_season_change_player_absent_resets(page):
    pool = [_rec("A", 260)]
    out = _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert out == "reset"


def test_season_change_player_changed_position_resets(page):
    pool = [_rec("A", 260), _rec("B", 300, position="DI")]  # ED -> DI.
    out = _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert out == "reset"


def test_season_change_uses_clamped_threshold(page):
    # Raw 230 would fail B (200); the clamped/defaulted 150 lets it through.
    pool = [_rec("A", 260), _rec("B", 200)]
    assert _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool) == "reset"

    out = _evaluate(
        page, _state(), _state(season=2024, threshold=150), ["A", "B"], pool
    )
    assert out == "refresh"


def test_season_change_with_tighter_threshold_checked_against_new_pool(page):
    pool = [_rec("A", 260)]
    out = _evaluate(page, _state(), _state(season=2024, threshold=261), ["A"], pool)
    assert out == "reset"


def test_season_change_nobody_pinned_is_refresh(page):
    assert _evaluate(page, _state(), _state(season=2024), [], []) == "refresh"


def test_app_boots_without_module_errors(live_server_url):
    """The new imports (filters.js <-> card modules) must not break module loading."""
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page()
        errors = []

        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(live_server_url)
        pg.wait_for_load_state("networkidle")
        browser.close()

    assert errors == []
