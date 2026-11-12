"""How an exported PNG reaches the user: a download on desktop, the share sheet (or Copy) on a touch device."""

from __future__ import annotations

import pytest
from conftest import RECORDS_READY_JS
from database.db_models import NFLPassRushStat
from main import SessionLocal

BAR = "#export-status"
SAVE_BUTTON = ".scout-card.is-active .card-save-btn"


@pytest.fixture()
def page(live_server_url, open_page):
    page = open_page(
        live_server_url,
        viewport={"width": 1280, "height": 900},
        ready_js=RECORDS_READY_JS,
    )
    page.evaluate("""
        async () => {
          const d = await import('/data.js');
          const s = await import('/scout-card.js');
          s.closeAllScoutCards();
          s.viewFloatingCard(d.currentRecords[0]);
        }
        """)
    page.wait_for_selector(SAVE_BUTTON)
    return page


# Makes the page look like a phone that can share files. `tapIsFresh` is what
# navigator.userActivation.isActive reports; `shareError` makes share() reject with that error name.
TOUCH_JS = """
({ tapIsFresh, canCopy, shareError }) => {
  window.__calls = { share: [], copied: [] };

  const realMatchMedia = window.matchMedia.bind(window);
  window.matchMedia = (query) =>
    query.includes('pointer: coarse')
      ? { matches: true, media: query, addEventListener() {}, removeEventListener() {} }
      : realMatchMedia(query);

  navigator.canShare = () => true;
  navigator.share = async (data) => {
    if (shareError) throw new DOMException('refused', shareError);
    window.__calls.share.push(data.files.map((f) => ({ name: f.name, type: f.type, size: f.size })));
  };
  Object.defineProperty(navigator, 'userActivation', { value: { isActive: tapIsFresh }, configurable: true });

  if (canCopy) {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        write: async (items) => {
          const blob = await items[0].getType('image/png');
          window.__calls.copied.push(blob.size);
        },
      },
    });
  } else {
    window.ClipboardItem = undefined;
  }
}
"""


def _touch(page, tap_is_fresh, can_copy=True, share_error=None):
    page.evaluate(
        TOUCH_JS,
        {"tapIsFresh": tap_is_fresh, "canCopy": can_copy, "shareError": share_error},
    )


def _save(page):
    page.locator(SAVE_BUTTON).first.click()


def _bar_text(page):
    return page.inner_text(BAR)


def _wait_ready(page):
    page.wait_for_selector(f"{BAR} .export-status-btn", state="visible")


def test_on_desktop_the_card_is_downloaded_as_a_png(page):
    with page.expect_download() as info:
        _save(page)

    assert info.value.suggested_filename.endswith(".png")


def test_the_download_link_is_not_revoked_right_after_the_click(page):
    # Revoking it at once can cancel the download on Safari.
    page.evaluate("""
        () => {
          window.__revoked = 0;
          const real = URL.revokeObjectURL.bind(URL);
          URL.revokeObjectURL = (url) => { window.__revoked += 1; return real(url); };
        }
        """)

    with page.expect_download():
        _save(page)

    assert page.evaluate("window.__revoked") == 0


def test_the_bar_says_preparing_while_the_export_runs_and_is_gone_after(page):
    page.evaluate("""
        () => {
          const real = window.html2canvas;
          window.html2canvas = async (...args) => {
            await new Promise((resolve) => setTimeout(resolve, 600));
            return real(...args);
          };
        }
        """)

    with page.expect_download():
        _save(page)
        page.wait_for_selector(BAR, state="visible", timeout=2000)
        assert _bar_text(page) == "Preparing image…"

    page.wait_for_selector(BAR, state="hidden")


def test_a_failed_export_says_so_and_frees_the_button(page):
    page.evaluate(
        "() => { window.html2canvas = async () => { throw new Error('boom'); }; }"
    )

    _save(page)

    page.wait_for_function(
        f"document.querySelector('{BAR}')?.textContent.includes('Could not create')"
    )
    assert page.locator(SAVE_BUTTON).first.is_enabled()


def test_on_a_phone_with_a_fresh_tap_the_share_sheet_opens_at_once(page):
    _touch(page, tap_is_fresh=True)

    _save(page)

    page.wait_for_function("window.__calls.share.length === 1")
    shared = page.evaluate("window.__calls.share[0]")
    assert (
        len(shared) == 1
        and shared[0]["type"] == "image/png"
        and shared[0]["name"].endswith(".png")
    )
    assert shared[0]["size"] > 0
    page.wait_for_selector(BAR, state="hidden")


def test_on_a_phone_with_an_expired_tap_the_bar_asks_for_a_new_one(page):
    _touch(page, tap_is_fresh=False)

    _save(page)
    _wait_ready(page)

    assert page.evaluate("window.__calls.share.length") == 0
    assert "Image ready" in _bar_text(page)

    page.click(f"{BAR} >> text='Share / Save'")

    page.wait_for_function("window.__calls.share.length === 1")
    page.wait_for_selector(BAR, state="hidden")


def test_the_ready_popup_sits_in_the_middle_of_the_screen(page):
    page.set_viewport_size({"width": 390, "height": 844})
    _touch(page, tap_is_fresh=False)

    _save(page)
    _wait_ready(page)

    box = page.locator(BAR).bounding_box()

    assert abs(box["x"] + box["width"] / 2 - 390 / 2) <= 2
    assert abs(box["y"] + box["height"] / 2 - 844 / 2) <= 2
    # Big enough to hit: every button is at least 44px tall, the touch-target minimum.
    for button in page.locator(f"{BAR} .export-status-btn").all():
        assert button.bounding_box()["height"] >= 44


def test_the_ready_bar_can_copy_the_image(page):
    _touch(page, tap_is_fresh=False)

    _save(page)
    _wait_ready(page)
    page.click(f"{BAR} >> text='Copy'")

    page.wait_for_function("window.__calls.copied.length === 1")
    assert page.evaluate("window.__calls.copied[0]") > 0
    assert "Image copied" in _bar_text(page)


def test_there_is_no_copy_button_where_the_clipboard_cannot_take_an_image(page):
    _touch(page, tap_is_fresh=False, can_copy=False)

    _save(page)
    _wait_ready(page)

    assert page.locator(f"{BAR} >> text='Copy'").count() == 0


def test_a_refused_share_falls_back_to_the_ready_bar(page):
    _touch(page, tap_is_fresh=True, share_error="NotAllowedError")

    _save(page)
    _wait_ready(page)

    assert "Image ready" in _bar_text(page)


def test_closing_the_share_sheet_leaves_no_bar_behind(page):
    _touch(page, tap_is_fresh=True, share_error="AbortError")

    _save(page)

    page.wait_for_selector(BAR, state="hidden")


def test_the_close_button_hides_the_ready_bar(page):
    _touch(page, tap_is_fresh=False)

    _save(page)
    _wait_ready(page)
    page.click(f"{BAR} >> text='Close'")

    page.wait_for_selector(BAR, state="hidden")


# The export clones sit off-screen at left -99999px; a count of them at the moment the PNG is handed over.
CLONES_AT_DELIVERY_JS = """
() => {
  window.__clonesAtDelivery = [];
  const realClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    const clones = [...document.body.children].filter((el) => el.style.left === '-99999px');
    window.__clonesAtDelivery.push(clones.length);
    return realClick.call(this);
  };
}
"""


def _add_a_second_edge_rusher() -> None:
    with SessionLocal() as sess:
        first = sess.query(NFLPassRushStat).filter_by(position="ED").first()
        values = {
            column.name: getattr(first, column.name)
            for column in NFLPassRushStat.__table__.columns
            if column.name != "id"
        }
        values.update(
            player="S. Second", abbr_name="S. Second", player_id=first.player_id + 1
        )
        sess.add(NFLPassRushStat(**values))
        sess.commit()


def test_the_card_export_clone_is_gone_before_the_png_is_handed_over(page):
    page.evaluate(CLONES_AT_DELIVERY_JS)

    with page.expect_download():
        _save(page)

    assert page.evaluate("window.__clonesAtDelivery") == [0]


def test_the_chart_export_clone_is_gone_before_the_png_is_handed_over(page):
    # The chart needs two players to draw, and the seeded season has one edge rusher.
    _add_a_second_edge_rusher()
    page.reload()
    page.wait_for_selector("#save-png-btn:not([disabled])")
    page.evaluate(CLONES_AT_DELIVERY_JS)

    with page.expect_download():
        page.click("#save-png-btn")

    assert page.evaluate("window.__clonesAtDelivery") == [0]
