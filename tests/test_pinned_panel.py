"""Pinned Players panel: open on a first visit, remembered afterwards, Hide / Manage label."""

from __future__ import annotations

import pytest

PANEL = "#pcs-panel"
BUTTON = "#pcs-inspect-btn"
LABEL = "#pcs-inspect-btn .pcs-inspect-label"
SECTION = "#player-cards-space:not([hidden])"

# Storage that throws on every access, as in a private window with site data blocked.
BLOCK_STORAGE = """
Object.defineProperty(window, 'localStorage', {
  get() { throw new Error('storage blocked'); },
});
"""


@pytest.fixture()
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        yield b
        b.close()


def _open_app(context, url):
    # The panel is desktop and tablet only, so the viewport must be wide.
    page = context.new_page()
    page.goto(url)
    page.wait_for_selector(SECTION)

    return page


def _state(page):
    return dict(
        panel_hidden=page.locator(PANEL).evaluate("el => el.hidden"),
        # text_content() is the DOM text; inner_text() would return the CSS-uppercased "HIDE".
        label=page.locator(LABEL).text_content().strip(),
        expanded=page.locator(BUTTON).get_attribute("aria-expanded"),
    )


OPEN = dict(panel_hidden=False, label="Hide", expanded="true")
FOLDED = dict(panel_hidden=True, label="Manage", expanded="false")


def test_first_visit_starts_open_with_a_hide_button(browser, live_server_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = _open_app(context, live_server_url)

    assert _state(page) == OPEN


def test_folding_changes_the_label_and_is_remembered(browser, live_server_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = _open_app(context, live_server_url)

    page.click(BUTTON)
    assert _state(page) == FOLDED

    page.reload()
    page.wait_for_selector(SECTION)
    assert _state(page) == FOLDED, "the folded choice was not remembered"

    page.click(BUTTON)
    assert _state(page) == OPEN

    page.reload()
    page.wait_for_selector(SECTION)
    assert _state(page) == OPEN, "the open choice was not remembered"


def test_blocked_storage_still_works_and_starts_open(browser, live_server_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_init_script(BLOCK_STORAGE)
    page = _open_app(context, live_server_url)

    assert _state(page) == OPEN

    page.click(BUTTON)
    assert _state(page) == FOLDED, "the button must still work without storage"
