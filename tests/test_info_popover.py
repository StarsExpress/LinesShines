"""The shared info popover (info-popover.js): how its content forms render."""

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

        yield pg
        browser.close()


# Builds a trigger the way the app does, opens it with a click, and reads what the popup holds.
OPEN_JS = """
async ([content]) => {
  const m = await import('/info-popover.js');
  const trigger = m.createInfoPopover(content, { label: 'ⓘ' });
  document.body.appendChild(trigger);
  trigger.click();

  const popup = document.querySelector('.info-popover-content');
  const texts = (selector) => [...popup.querySelectorAll(selector)].map((e) => e.textContent);
  return {
    items: texts('li'),
    paragraphs: texts('p'),
    lists: popup.querySelectorAll('ul').length,
  };
}
"""

POINTS = [
    "Read: players as columns and metrics as rows. No sorting in this mode.",
    "Sort: players as rows and metrics as columns. Click column header to order players by that metric.",
]


def _open(page, content):
    return page.evaluate(OPEN_JS, [content])


def test_bullets_render_as_one_list_with_one_item_per_point(page):
    out = _open(page, {"bullets": POINTS})

    assert out["lists"] == 1
    assert out["items"] == POINTS
    assert out["paragraphs"] == []


def test_a_plain_string_is_still_one_paragraph(page):
    out = _open(page, "Just one explanation.")

    assert out["paragraphs"] == ["Just one explanation."]
    assert out["lists"] == 0
    assert out["items"] == []


def test_bullets_can_sit_beside_a_text_paragraph(page):
    out = _open(page, {"text": "Intro.", "bullets": POINTS})

    assert out["paragraphs"] == ["Intro."]
    assert out["items"] == POINTS
