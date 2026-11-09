"""The NFL Teams checklist: conference and division headers select or clear a whole group."""

from __future__ import annotations

import pytest
from conftest import APP_READY_JS

AFC_EAST = ["BUF", "MIA", "NE", "NYJ"]


@pytest.fixture()
def page(live_server_url, open_page):
    page = open_page(
        f"{live_server_url}/",
        viewport={"width": 1280, "height": 900},
        ready_js=APP_READY_JS,
    )
    page.click("#teams-toggle-btn")
    page.click("#teams-select-none")
    return page


def _checked_teams(page):
    return page.eval_on_selector_all(
        "#teams-checklist input:checked", "boxes => boxes.map(box => box.value)"
    )


def _conference_header(page, conference):
    return page.locator(f"button[aria-label='Toggle all of {conference}']")


def _division_header(page, conference, division):
    return page.locator(f"button[aria-label='Toggle all of {conference} {division}']")


def test_a_conference_header_selects_that_whole_conference_only(page):
    _conference_header(page, "AFC").click()

    checked = _checked_teams(page)

    assert len(checked) == 16
    assert "BUF" in checked and "KC" in checked
    assert "DAL" not in checked and "SF" not in checked


def test_a_second_click_on_a_conference_header_clears_it(page):
    _conference_header(page, "NFC").click()
    _conference_header(page, "NFC").click()

    assert _checked_teams(page) == []


def test_a_division_header_selects_just_its_four_teams(page):
    _division_header(page, "AFC", "East").click()

    assert sorted(_checked_teams(page)) == AFC_EAST


def test_a_division_toggle_leaves_the_rest_of_the_conference_alone(page):
    _conference_header(page, "AFC").click()

    _division_header(page, "AFC", "East").click()

    checked = _checked_teams(page)
    assert len(checked) == 12
    assert not set(AFC_EAST) & set(checked)


def test_a_partly_ticked_group_is_completed_not_cleared(page):
    page.check("#teams-checklist input[value='BUF']")

    _division_header(page, "AFC", "East").click()

    assert sorted(_checked_teams(page)) == AFC_EAST


def test_the_summary_follows_a_group_click(page):
    _conference_header(page, "AFC").click()

    assert page.inner_text("#teams-select-summary") == "16 Teams"


def test_a_group_box_shows_empty_half_and_full(page):
    east = _division_header(page, "AFC", "East")
    afc = _conference_header(page, "AFC")
    assert east.get_attribute("aria-checked") == "false"

    page.check("#teams-checklist input[value='BUF']")
    assert east.get_attribute("aria-checked") == "mixed"
    assert afc.get_attribute("aria-checked") == "mixed"

    east.click()
    assert east.get_attribute("aria-checked") == "true"
    assert afc.get_attribute("aria-checked") == "mixed"

    page.click("#teams-select-all")
    assert afc.get_attribute("aria-checked") == "true"


def test_group_boxes_are_not_counted_as_teams(page):
    assert page.locator("#teams-checklist input").count() == 32
