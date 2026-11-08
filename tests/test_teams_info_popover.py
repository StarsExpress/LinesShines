"""The Teams label's (i) button exists and a click opens its explanation popup."""

from __future__ import annotations

import pytest

TEAMS_INFO_TEXT = (
    "Select teams to highlight their players in the plot. "
    "Everyone else stays in the comparison pool, so percentiles don't change."
)


def test_teams_info_button_opens_popup_with_copy(live_server_url, open_page):
    page = open_page(live_server_url)

    trigger = page.locator("#teams-info-slot .info-popover-trigger")
    trigger.wait_for(state="visible")

    assert trigger.text_content().strip() == "ⓘ"
    assert page.locator(".info-popover-content").count() == 0

    trigger.click()
    popup = page.locator(".info-popover-content")
    popup.wait_for(state="visible")
    assert TEAMS_INFO_TEXT in popup.inner_text()

    trigger.click()  # Click again toggles it closed (no hover-only behavior).
    assert page.locator(".info-popover-content").count() == 0
