"""Visual-viewport-aware popup placement: pure clamp math + close-on-viewport-change."""

from __future__ import annotations
import itertools

import pytest

LAYOUT_W, LAYOUT_H = 1024, 768


@pytest.fixture()
def page(live_server_url):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": LAYOUT_W, "height": LAYOUT_H})
        pg.goto(live_server_url)
        pg.locator("#hero-install-slot .info-popover-trigger").wait_for(state="visible")

        yield pg
        browser.close()


def _place(page, **kwargs):
    return page.evaluate(
        """async args => {
            const m = await import('/popup-position.js');
            return m.computePopupPlacement(args);
        }""",
        kwargs,
    )


def _scenarios():
    margin = 8
    for scale in (1, 2, 3):
        vw, vh = LAYOUT_W / scale, LAYOUT_H / scale

        # Visual viewport can sit anywhere inside the layout viewport.
        for fx, fy in itertools.product((0, 0.5, 1), repeat=2):
            ox, oy = (LAYOUT_W - vw) * fx, (LAYOUT_H - vh) * fy
            viewport = dict(
                offsetLeft=ox, offsetTop=oy, width=vw, height=vh, scale=scale
            )

            # Anchors: near each corner of the layout viewport (often off-screen
            # for the visual viewport) and in the middle.
            for ax, ay in itertools.product(
                (0, 500, LAYOUT_W - 40), (0, 300, LAYOUT_H - 30)
            ):
                anchor = dict(left=ax, right=ax + 40, top=ay, bottom=ay + 30)
                for popup_w in (
                    240,
                    420,
                    900,
                ):  # Last one is wider than any zoomed viewport.
                    for align in ("left", "right", "center"):
                        yield viewport, anchor, dict(
                            width=popup_w, height=120
                        ), align, margin


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_placement_stays_inside_visual_viewport(page, scale):
    checked = 0

    for viewport, anchor, popup, align, margin in _scenarios():
        if viewport["scale"] != scale:
            continue

        out = _place(page, viewport=viewport, anchor=anchor, popup=popup, align=align)
        m = margin / scale
        eps = 1e-6

        left_edge, right_edge = (
            viewport["offsetLeft"],
            viewport["offsetLeft"] + viewport["width"],
        )

        top_edge, bottom_edge = (
            viewport["offsetTop"],
            viewport["offsetTop"] + viewport["height"],
        )

        assert out["width"] <= min(popup["width"], viewport["width"] - 2 * m) + eps

        assert out["left"] >= left_edge + m - eps
        assert out["left"] + out["width"] <= right_edge - m + eps

        assert out["top"] >= top_edge + m - eps
        assert out["top"] + popup["height"] <= bottom_edge - m + eps

        checked += 1

    assert checked > 100


def test_unconstrained_popup_keeps_its_width_and_anchor(page):
    viewport = dict(offsetLeft=0, offsetTop=0, width=1024, height=768, scale=1)
    anchor = dict(left=400, right=440, top=300, bottom=330)

    out = _place(
        page,
        viewport=viewport,
        anchor=anchor,
        popup=dict(width=240, height=100),
        align="left",
    )

    assert out["width"] == 240
    assert out["left"] == 400
    assert out["top"] == 300 - 100 - 8  # Above the anchor.


def test_fallback_viewport_without_visual_viewport_api(page):
    page.evaluate(
        "Object.defineProperty(window, 'visualViewport', { value: undefined })"
    )

    vp = page.evaluate("import('/popup-position.js').then(m => m.getViewportRect())")

    assert vp["scale"] == 1 and vp["offsetLeft"] == 0 and vp["offsetTop"] == 0
    assert vp["width"] == LAYOUT_W


def test_popup_closes_on_visual_viewport_resize_and_scroll(page):
    trigger = page.locator("#hero-install-slot .info-popover-trigger")
    popup = page.locator(".info-popover-content")

    for event in ("resize", "scroll"):
        trigger.click()
        assert popup.is_visible()

        page.evaluate(f"window.visualViewport.dispatchEvent(new Event('{event}'))")
        assert popup.count() == 0
        assert trigger.get_attribute("aria-expanded") == "false"


def test_existing_open_close_behavior_unchanged(page):
    trigger = page.locator("#hero-install-slot .info-popover-trigger")
    popup = page.locator(".info-popover-content")

    trigger.click()
    trigger.click()
    assert popup.count() == 0

    trigger.click()
    page.keyboard.press("Escape")
    assert popup.count() == 0

    trigger.click()
    page.mouse.click(300, 400)
    assert popup.count() == 0
