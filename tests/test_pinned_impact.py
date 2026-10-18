"""evaluatePinnedImpact(): which Apply outcome a final filter combination implies."""

from __future__ import annotations

import re
from pathlib import Path

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


def _full(page, applied, pending, pinned, pool, comparisons=()):
    return page.evaluate(
        """async args => {
            const m = await import('/pinned-impact.js');
            return m.evaluatePinnedImpact(
                args.applied, args.pending, args.pinned, args.pool, args.field,
                args.comparisons);
        }""",
        dict(
            applied=applied,
            pending=pending,
            pinned=pinned,
            pool=pool,
            field=FIELD,
            comparisons=[dict(id=i, memberKeys=m) for i, m in comparisons],
        ),
    )


def _evaluate(page, applied, pending, pinned, pool):
    return _full(page, applied, pending, pinned, pool)["outcome"]


def _partition(page, names, pool, position="ED", threshold=230):
    return page.evaluate(
        """async args => {
            const m = await import('/pinned-impact.js');
            return m.partitionByEligibility(
                args.names, args.pool, args.position, args.threshold, args.field);
        }""",
        dict(
            names=names, pool=pool, position=position, threshold=threshold, field=FIELD
        ),
    )


def _notice(page, names):
    return page.evaluate(
        """async names => {
            const m = await import('/pinned-impact.js');
            return m.removedPlayersNotice(names);
        }""",
        names,
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


def test_threshold_tightened_one_falls_short_is_partial(page):
    out = _evaluate(page, _state(), _state(threshold=241), ["A", "B", "C"], POOL)
    assert out == "partial"


def test_tighten_pinned_player_missing_from_pool_resets(page):
    out = _evaluate(page, _state(), _state(threshold=240), ["ghost"], POOL)
    assert out == "reset"


def test_season_change_all_present_is_refresh(page):
    pool = [_rec("A", 260), _rec("B", 230)]
    out = _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert out == "refresh"  # B exactly on the (230) threshold: inclusive.


def test_season_change_player_absent_is_partial(page):
    pool = [_rec("A", 260)]
    out = _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert out == "partial"


def test_season_change_player_changed_position_is_partial(page):
    pool = [_rec("A", 260), _rec("B", 300, position="DI")]  # ED -> DI.
    out = _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert out == "partial"


def test_season_change_uses_clamped_threshold(page):
    # Raw 230 would fail B (200); the clamped/defaulted 150 lets it through.
    pool = [_rec("A", 260), _rec("B", 200)]
    assert _evaluate(page, _state(), _state(season=2024), ["A", "B"], pool) == "partial"

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


# --- Partial removal. -------------------------------------------------------

NEXT = _state(
    threshold=240
)  # Same season, tighter bar: B (250) and A (300) pass, C (240) too.


def _partial_pool(**opp):
    return [_rec(p, v) for p, v in opp.items()]


def test_partial_removes_only_failing_players(page):
    pool = _partial_pool(A=300, B=250, C=100)
    r = _full(page, _state(), NEXT, ["A", "B", "C"], pool)
    assert r["outcome"] == "partial"
    assert r["kept"] == ["A", "B"] and r["removed"] == ["C"]


def test_all_failing_is_reset_not_partial(page):
    pool = _partial_pool(A=10, B=20)
    r = _full(page, _state(), NEXT, ["A", "B"], pool)
    assert r["outcome"] == "reset"
    assert r["kept"] == []


def test_partial_on_season_change_with_absent_player(page):
    pool = _partial_pool(A=300)
    r = _full(page, _state(), _state(season=2024), ["A", "B"], pool)
    assert (r["outcome"], r["kept"], r["removed"]) == ("partial", ["A"], ["B"])


def test_category_and_position_change_reset_with_everyone_removed(page):
    for pending in (_state(category="pass_block"), _state(position="DI")):
        r = _full(page, _state(), pending, ["A", "B"], POOL)
        assert r["outcome"] == "reset" and r["removed"] == ["A", "B"]


def test_comparison_shrinks_to_two_members_boundary(page):
    pool = _partial_pool(A=300, B=250, C=100)
    r = _full(page, _state(), NEXT, ["A", "B", "C"], pool, [("m1", ["A", "B", "C"])])

    assert r["comparisons"]["dissolved"] == []
    (s,) = r["comparisons"]["shrunk"]
    assert s["id"] == "m1" and s["kept"] == ["A", "B"] and s["removed"] == ["C"]


def test_comparison_with_one_left_is_dissolved(page):
    pool = _partial_pool(A=300, B=100, C=100)
    r = _full(page, _state(), NEXT, ["A", "B", "C"], pool, [("m1", ["A", "B"])])
    assert r["comparisons"]["shrunk"] == []
    (d,) = r["comparisons"]["dissolved"]
    assert d["id"] == "m1" and d["survivors"] == ["A"]


def test_comparison_with_none_left_is_dissolved(page):
    pool = _partial_pool(A=300, B=100, C=100)
    r = _full(page, _state(), NEXT, ["A", "B", "C"], pool, [("m1", ["B", "C"])])

    (d,) = r["comparisons"]["dissolved"]
    assert d["survivors"] == []


def test_same_player_in_several_comparisons(page):
    pool = _partial_pool(A=300, B=250, C=100, D=260)
    comps = [("m1", ["A", "B", "C"]), ("m2", ["C", "D"]), ("m3", ["A", "D"])]

    r = _full(page, _state(), NEXT, ["A", "B", "C", "D"], pool, comps)

    assert [s["id"] for s in r["comparisons"]["shrunk"]] == ["m1"]
    assert [d["id"] for d in r["comparisons"]["dissolved"]] == ["m2"]  # m3 untouched.


def test_shrunk_comparison_duplicating_another_is_dissolved(page):
    pool = _partial_pool(A=300, B=250, C=100)
    comps = [("m1", ["A", "B", "C"]), ("m2", ["A", "B"])]

    r = _full(page, _state(), NEXT, ["A", "B", "C"], pool, comps)
    assert r["comparisons"]["shrunk"] == []

    (d,) = r["comparisons"]["dissolved"]
    assert d["id"] == "m1" and d["duplicate"] is True


def test_shrunk_comparisons_equal_to_each_other_keep_only_the_first(page):
    pool = _partial_pool(A=300, B=250, C=100, D=100)
    comps = [
        ("m1", ["A", "B", "C"]),
        ("m2", ["A", "B", "D"]),
        ("m3", ["B", "A", "C", "D"]),
    ]

    r = _full(page, _state(), NEXT, ["A", "B", "C", "D"], pool, comps)
    assert [s["id"] for s in r["comparisons"]["shrunk"]] == ["m1"]

    dissolved = r["comparisons"]["dissolved"]
    assert [d["id"] for d in dissolved] == ["m2", "m3"]
    assert all(d["duplicate"] for d in dissolved)


def test_quick_set_only_commits_without_confirm_on_unaffected_or_refresh(page):
    out = page.evaluate("""async () => {
            const m = await import('/pinned-impact.js');
            return ['unaffected', 'refresh', 'partial', 'reset'].map(m.mayApplyWithoutConfirm);
        }""")

    assert out == [True, True, False, False]


# --- Confirm copy. ----------------------------------------------------------


def _message(page, result):
    return page.evaluate(
        """async r => {
            const m = await import('/pinned-impact.js');
            return m.impactConfirmMessage(r);
        }""",
        result,
    )


def _result(removed, shrunk=(), dissolved=()):
    return dict(
        outcome="partial",
        kept=["K"],
        removed=removed,
        comparisons=dict(shrunk=list(shrunk), dissolved=list(dissolved)),
    )


def _row(before, after=None, status=None):
    return dict(before=before, after=after, status=status)


def test_message_title_and_button_fixed_in_every_case(page):
    cases = [
        _result(["A"]),
        _result(["A"], shrunk=[dict(id="1", members=["A", "B", "C"], kept=["B", "C"])]),
        dict(
            outcome="reset",
            kept=[],
            removed=["A", "B"],
            comparisons={"shrunk": [], "dissolved": []},
        ),
    ]

    for case in cases:
        msg = _message(page, case)
        assert msg["title"] == "New Filters Cause Removals"
        assert msg["confirmLabel"] == "REMOVE & APPLY"
        assert msg["removedLabel"] == "REMOVED"
        assert msg["comparisonsLabel"] == "AFFECTED COMPARISONS"
        assert msg["note"] == "This can’t be undone."


def test_message_lists_only_removed_players(page):
    msg = _message(page, _result(["A. Smith", "B. Jones"]))
    assert msg["removedNames"] == ["A. Smith", "B. Jones"]
    assert msg["comparisonRows"] == []


def test_message_never_truncates_players(page):
    names = [f"P{i}" for i in range(12)]
    assert _message(page, _result(names))["removedNames"] == names


def test_reset_lists_all_pinned_players(page):
    everyone = [f"P{i}" for i in range(8)]
    result = dict(
        outcome="reset",
        kept=[],
        removed=everyone,
        comparisons={"shrunk": [], "dissolved": []},
    )

    msg = _message(page, result)
    assert msg["removedNames"] == everyone
    assert msg["comparisonRows"] == []


def test_comparison_row_shrunk(page):
    msg = _message(
        page,
        _result(["X"], shrunk=[dict(id="1", members=["A", "B", "X"], kept=["A", "B"])]),
    )
    assert msg["comparisonRows"] == [_row(["A", "B", "X"], ["A", "B"])]


def test_comparison_row_dissolved(page):
    msg = _message(
        page,
        _result(["X"], dissolved=[dict(id="2", members=["C", "X"], survivors=["C"])]),
    )
    assert msg["comparisonRows"] == [_row(["C", "X"], None, "dissolved")]


def test_comparison_row_merged_because_duplicate(page):
    msg = _message(
        page,
        _result(
            ["X"],
            dissolved=[
                dict(
                    id="3",
                    members=["A", "B", "X"],
                    survivors=["A", "B"],
                    duplicate=True,
                )
            ],
        ),
    )
    assert msg["comparisonRows"] == [
        _row(["A", "B", "X"], None, "merged into an identical comparison")
    ]


def test_many_comparisons_are_not_truncated(page):
    shrunk = [
        dict(id=str(i), members=["A", "B", "X"], kept=["A", "B"]) for i in range(7)
    ]
    assert len(_message(page, _result(["X"], shrunk=shrunk))["comparisonRows"]) == 7


def test_message_uses_display_names(page):
    msg = page.evaluate(
        """async r => {
            const m = await import('/pinned-impact.js');
            return m.impactConfirmMessage(r, k => k.toUpperCase());
        }""",
        _result(["a"]),
    )
    assert msg["removedNames"] == ["A"]


_RENDER_JS = """async content => {
    const ws = await import('/workspace.js');
    const pending = ws.showMergeInvalidationConfirm(content);
    const body = document.getElementById('merge-confirm-body');
    const scroll = document.getElementById('merge-confirm-scroll');
    const snap = {
        labels: [...body.querySelectorAll('.merge-confirm-label')].map(e => e.textContent),
        removedItems: [...body.querySelectorAll('section:first-child li')].map(e => e.textContent),
        comparisonItems: [...body.querySelectorAll('.merge-confirm-comparison')].map(li => ({
            lines: [...li.children].map(c => c.textContent),
            bulletsInside: li.querySelectorAll('li').length,
        })),
        sections: body.querySelectorAll('section').length,
        injected: body.querySelectorAll('b').length,
        nowrap: getComputedStyle(body.querySelector('.merge-confirm-name')).whiteSpace,
        overflowY: getComputedStyle(body).overflowY,
        overscroll: getComputedStyle(body).overscrollBehaviorY,
        tabindex: body.getAttribute('tabindex'),
        ariaLabel: body.getAttribute('aria-label'),
        noteInBody: body.contains(document.getElementById('merge-confirm-note')),
        note: document.getElementById('merge-confirm-note').textContent,
        noteColor: getComputedStyle(document.getElementById('merge-confirm-note')).color,
        hasMore: scroll.classList.contains('has-more'),
        maxHeight: parseFloat(getComputedStyle(body).maxHeight),
        viewport: innerHeight,
    };
    document.getElementById('merge-confirm-cancel').click();
    snap.resolved = await pending;
    return snap;
}"""


def _content(page, removed, shrunk=(), dissolved=()):
    return page.evaluate(
        """async r => {
            const m = await import('/pinned-impact.js');
            return m.impactConfirmMessage(r);
        }""",
        _result(removed, shrunk, dissolved),
    )


def test_confirm_dialog_renders_bullets_counts_and_fixed_parts(page):
    content = _content(
        page,
        ["<b>x</b>", "B", "C", "D", "E"],
        shrunk=[dict(id="1", members=["A", "B", "C"], kept=["A"])],
        dissolved=[dict(id="2", members=["D", "B"], survivors=["D"], duplicate=True)],
    )
    out = page.evaluate(_RENDER_JS, content)

    assert out["labels"] == ["REMOVED · 5", "AFFECTED COMPARISONS · 2"]
    assert out["removedItems"] == [
        "<b>x</b>",
        "B",
        "C",
        "D",
        "E",
    ]  # All 5, no "and N more".

    assert out["injected"] == 0  # textContent, never innerHTML.

    # One bullet per Comparison, the outcome line inside the same bullet.
    assert out["comparisonItems"] == [
        {"lines": ["A + B + C", "→ A"], "bulletsInside": 0},
        {
            "lines": ["D + B", "→ merged into an identical comparison"],
            "bulletsInside": 0,
        },
    ]

    assert out["nowrap"] == "nowrap"
    assert out["overflowY"] == "auto" and out["overscroll"] == "contain"
    assert out["tabindex"] == "0" and out["ariaLabel"]
    assert out["maxHeight"] <= out["viewport"] * 0.6 + 1

    assert out["noteInBody"] is False  # Fixed area, outside the scroller.
    assert out["note"] == "This can’t be undone."
    assert out["noteColor"] == "rgb(255, 138, 117)"
    assert out["resolved"] is False


def test_confirm_dialog_omits_comparisons_block_when_none(page):
    out = page.evaluate(_RENDER_JS, _content(page, ["A", "B"]))
    assert out["labels"] == ["REMOVED · 2"]
    assert out["sections"] == 1
    assert out["comparisonItems"] == []


def test_confirm_dialog_shows_fade_only_when_content_overflows(page):
    few = page.evaluate(_RENDER_JS, _content(page, ["A"]))
    many = page.evaluate(_RENDER_JS, _content(page, [f"Player {i}" for i in range(60)]))
    assert few["hasMore"] is False
    assert many["hasMore"] is True


def test_alert_coral_meets_contrast_on_lightest_box_background():
    def lum(hex_):
        chans = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans
        ]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted(
        (lum("#ff8a75"), lum("#1e3d28")), reverse=True
    )  # --turf-700 is the lightest stop.

    assert (hi + 0.05) / (lo + 0.05) >= 4.5


def _luminance(hex_):
    chans = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]

    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(hex_a, hex_b):
    hi, lo = sorted((_luminance(hex_a), _luminance(hex_b)), reverse=True)

    return (hi + 0.05) / (lo + 0.05)


def test_warning_notice_colours_meet_contrast():
    """Reads the real style.css, so changing the rule or the palette is checked."""
    css = (Path(__file__).resolve().parent.parent / "frontend" / "style.css").read_text(
        encoding="utf-8"
    )
    variables = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", css))
    rule = re.search(r"\.pinned-refresh-notice\.is-warning\s*\{([^}]*)\}", css)
    assert rule, "the warning variant of the notice is missing from style.css"

    def colour(prop):
        value = re.search(rf"(?<![\w-]){prop}:\s*([^;]+);", rule.group(1)).group(1)
        named = re.fullmatch(r"var\(--([\w-]+)\)", value.strip())

        return variables[named.group(1)] if named else value.strip()

    assert _contrast(colour("color"), colour("background")) >= 4.5


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


def test_eligibility_keeps_players_who_clear_the_threshold(page):
    out = _partition(page, ["A", "B", "C"], POOL, threshold=245)

    assert out == {"kept": ["A", "B"], "removed": ["C"]}


def test_eligibility_threshold_is_inclusive(page):
    out = _partition(page, ["A", "B", "C"], POOL, threshold=250)

    assert out["kept"] == ["A", "B"]


def test_eligibility_removes_a_player_missing_from_the_pool(page):
    out = _partition(page, ["A", "Z"], POOL, threshold=0)

    assert out == {"kept": ["A"], "removed": ["Z"]}


def test_eligibility_removes_a_player_at_another_position(page):
    pool = [_rec("A", 300), _rec("D", 300, position="DI")]
    out = _partition(page, ["A", "D"], pool, position="ED", threshold=0)

    assert out == {"kept": ["A"], "removed": ["D"]}


def test_eligibility_removes_a_player_with_no_value(page):
    pool = [_rec("A", 300), {"player": "N", "position": "ED", FIELD: None}]
    out = _partition(page, ["A", "N"], pool, threshold=0)

    assert out == {"kept": ["A"], "removed": ["N"]}


def test_eligibility_keeps_the_order_it_was_given(page):
    out = _partition(page, ["C", "A", "B"], POOL, threshold=0)

    assert out["kept"] == ["C", "A", "B"]


def test_eligibility_with_an_empty_pool_removes_everyone(page):
    for pool in ([], None):
        out = _partition(page, ["A", "B"], pool, threshold=0)

        assert out == {"kept": [], "removed": ["A", "B"]}


def test_pinned_impact_and_players_filter_share_one_eligibility_rule(page):
    # 250 is exactly B's value, so a boundary that drifted in either place shows up.
    pinned = ["A", "B", "C"]
    impact = _full(page, _state(), _state(threshold=250), pinned, POOL)
    shared = _partition(page, pinned, POOL, threshold=250)

    assert impact["outcome"] == "partial"
    assert shared == {"kept": ["A", "B"], "removed": ["C"]}
    assert (impact["kept"], impact["removed"]) == (shared["kept"], shared["removed"])


def test_removed_players_notice_is_empty_when_nobody_was_removed(page):
    assert _notice(page, []) == ""


def test_removed_players_notice_names_one_player(page):
    out = _notice(page, ["W. Anderson Jr."])

    assert out == "Removed from Players: W. Anderson Jr. — no longer eligible."


def test_removed_players_notice_lists_up_to_three_names(page):
    out = _notice(page, ["A", "B", "C"])

    assert out == "Removed from Players: A, B, C — no longer eligible."
    assert "more" not in out


def test_removed_players_notice_shortens_a_longer_list(page):
    four = _notice(page, ["A", "B", "C", "D"])
    five = _notice(page, ["A", "B", "C", "D", "E"])

    assert four == "Removed from Players: A, B, C and 1 more — no longer eligible."
    assert five == "Removed from Players: A, B, C and 2 more — no longer eligible."
    assert "D" not in four.split(": ")[1]
