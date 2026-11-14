"""The browser tests never wait for a host outside the live server (the fonts and icons CDNs)."""

from __future__ import annotations

from conftest import APP_READY_JS, wait_until

ABORTED = "net::ERR_FAILED"


def _external_failures(page, url: str) -> list[tuple[str, str]]:
    failures = []
    page.on(
        "requestfailed",
        lambda request: failures.append((request.url, request.failure)),
    )
    page.goto(url)
    wait_until(page, APP_READY_JS)

    return [(u, f) for u, f in failures if "127.0.0.1" not in u]


def test_a_page_fails_the_cdn_requests_at_once_instead_of_waiting_for_them(
    live_server_url, chromium_browser
):
    page = chromium_browser.new_page()

    failures = _external_failures(page, live_server_url)

    hosts = {url.split("/")[2] for url, _ in failures}
    assert {"fonts.googleapis.com", "cdnjs.cloudflare.com"} <= hosts
    assert all(failure == ABORTED for _, failure in failures)


def test_a_context_made_by_hand_is_kept_local_too(live_server_url, chromium_browser):
    context = chromium_browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    failures = _external_failures(page, live_server_url)

    assert failures
    assert all(failure == ABORTED for _, failure in failures)
