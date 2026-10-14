"""Header Install button: one trigger, a popup of four PWA.md links with hints."""

from __future__ import annotations
import re

import pytest

PWA_URL = "https://github.com/StarsExpress/LinesShines/blob/main/PWA.md"
EXPECTED = {
    "iOS": (f"{PWA_URL}#ios", "Safari: Share → Add to Home Screen"),
    "Android": (f"{PWA_URL}#android", "Chrome: ⋮ → Install app"),
    "macOS": (f"{PWA_URL}#macos", "Safari: File → Add to Dock"),
    "Windows": (f"{PWA_URL}#windows", "Edge/Chrome: Install icon"),
}


@pytest.fixture()
def page(live_server_url):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": 1280, "height": 800})
        pg.goto(live_server_url)
        pg.locator("#hero-install-slot .info-popover-trigger").wait_for(state="visible")

        yield pg
        browser.close()


def test_install_button_exists_left_of_github(page):
    trigger = page.locator("#hero-install-slot .info-popover-trigger")
    assert trigger.text_content().strip() == "Install"
    assert trigger.get_attribute("aria-haspopup") == "dialog"
    assert trigger.get_attribute("aria-expanded") == "false"

    box, gh = trigger.bounding_box(), page.locator(".hero-github").bounding_box()
    assert box["x"] + box["width"] <= gh["x"]


def test_install_popup_links_and_hints(page):
    page.locator("#hero-install-slot .info-popover-trigger").click()
    links = page.locator(".info-popover-content a.info-popover-link")
    assert links.count() == 4

    for idx in range(4):
        link = links.nth(idx)
        label = link.text_content().strip()
        href, hint = EXPECTED[label]

        assert link.get_attribute("href") == href
        assert link.get_attribute("target") == "_blank"
        assert link.get_attribute("rel") == "noopener"
        assert hint in link.locator("xpath=..").inner_text()


def test_install_open_close_state(page):
    trigger = page.locator("#hero-install-slot .info-popover-trigger")
    popup = page.locator(".info-popover-content")

    trigger.click()
    assert popup.is_visible()
    assert trigger.get_attribute("aria-expanded") == "true"

    trigger.click()  # Toggle closed.
    assert popup.count() == 0
    assert trigger.get_attribute("aria-expanded") == "false"

    trigger.click()
    page.keyboard.press("Escape")
    assert popup.count() == 0
    assert trigger.get_attribute("aria-expanded") == "false"

    trigger.click()
    page.mouse.click(300, 400)  # Outside.
    assert popup.count() == 0

    trigger.click()

    # Picking an option closes it (swallow the new tab so the test stays local).
    page.context.route("**/github.com/**", lambda route: route.abort())
    with page.context.expect_page():
        page.locator(".info-popover-link").first.click()

    assert popup.count() == 0
    assert trigger.get_attribute("aria-expanded") == "false"


def test_install_popup_stays_inside_viewport(page):
    page.locator("#hero-install-slot .info-popover-trigger").click()
    box = page.locator(".info-popover-content").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 1280


def test_install_hidden_in_standalone_display_mode(client):
    # Headless Chromium can't emulate display-mode, so check the served rule.
    css = client.get("/style.css").text
    assert re.search(
        r"@media \(display-mode: standalone\)\s*\{\s*\.hero-install\s*\{\s*display:\s*none;",
        css,
    ), "standalone display-mode must hide .hero-install"


def test_install_hints_stay_on_one_line(page):
    page.locator("#hero-install-slot .info-popover-trigger").click()
    heights = page.locator(".info-popover-link-hint").evaluate_all(
        "els => els.map(e => e.getBoundingClientRect().height)"
    )
    assert max(heights) == min(heights), heights


LOGO_VARS = {
    "iOS": ["--logo-ios"],
    "macOS": ["--logo-macos"],
    "Android": ["--logo-android"],
    "Windows": [
        "--logo-windows-red",
        "--logo-windows-green",
        "--logo-windows-blue",
        "--logo-windows-yellow",
    ],
}
LOGO_COLORS = {
    "--logo-ios": "rgb(255, 255, 255)",
    "--logo-macos": "rgb(162, 170, 173)",
    "--logo-android": "rgb(61, 220, 132)",
    "--logo-windows-red": "rgb(242, 80, 34)",
    "--logo-windows-green": "rgb(127, 186, 0)",
    "--logo-windows-blue": "rgb(0, 164, 239)",
    "--logo-windows-yellow": "rgb(255, 185, 0)",
}


def test_install_options_have_decorative_colored_icon_label_and_href(page):
    page.locator("#hero-install-slot .info-popover-trigger").click()
    links = page.locator(".info-popover-content a.info-popover-link")
    assert links.count() == 4

    for idx in range(4):
        link = links.nth(idx)
        label = link.text_content().strip()
        assert link.get_attribute("href") == EXPECTED[label][0]

        icons = link.locator("svg")
        assert icons.count() == 1
        assert icons.get_attribute("aria-hidden") == "true"

        paths = icons.locator("path")
        fills = [paths.nth(j).get_attribute("fill") for j in range(paths.count())]
        assert fills == [f"var({v})" for v in LOGO_VARS[label]]
        assert "currentColor" not in fills

        # The painted color is what the CSS variable resolves to.
        painted = paths.evaluate_all("els => els.map(e => getComputedStyle(e).fill)")
        assert painted == [LOGO_COLORS[v] for v in LOGO_VARS[label]]


@pytest.mark.parametrize("width", [1280, 600])
def test_install_button_matches_github_button_height(live_server_url, width):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": width, "height": 800})
        pg.goto(live_server_url)

        trigger = pg.locator("#hero-install-slot .info-popover-trigger")
        trigger.wait_for(state="visible")
        install, gh = trigger.bounding_box(), pg.locator(".hero-github").bounding_box()
        browser.close()

    assert install["height"] == gh["height"]
    assert install["y"] == gh["y"]
