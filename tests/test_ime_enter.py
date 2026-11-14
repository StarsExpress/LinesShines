"""Enter in a name search must not pick a suggestion while an input method is composing.

A Chinese, Japanese or Korean input method uses Enter to confirm the text it is composing. The
four name-search inputs (Players filter, Single Cards add, Create comparison, Edit comparison)
pick the top suggestion on Enter, so without the check that Enter would pick a player as well.
Safari fires compositionend before the keydown of that Enter (isComposing is already false), which
is why keyCode 229 is checked too. Reuses the seeded page of `test_browser_smoke.py`.
"""

from __future__ import annotations

from test_browser_smoke import (  # noqa: F401 (fixtures and helpers)
    add_to_players_filter,
    chip_names,
    create_comparison,
    page,
    pinned_names,
    seeded_smoke_db,
)

KEY_JS = """([selector, init]) => {
  const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, ...init });
  document.querySelector(selector).dispatchEvent(event);
  return event.defaultPrevented;
}"""

NAME = "Aaron Able"


def _press(page, selector: str, **init) -> bool:
    """Dispatches an Enter keydown; returns whether the page handled (and cancelled) it."""
    return page.evaluate(KEY_JS, [selector, init])


def _members(page, selector: str) -> str:
    return page.locator(selector).text_content()


def _open_players(page) -> None:
    page.click("#players-toggle-btn")
    page.fill("#players-input", NAME)
    page.locator(
        "#players-dropdown .player-option-name", has_text=NAME
    ).first.wait_for()


def _open_pcs_add(page) -> None:
    page.fill("#pcs-add-input", NAME)
    page.locator(
        "#pcs-add-dropdown .player-option-name", has_text=NAME
    ).first.wait_for()


def _open_create(page) -> None:
    page.click("#pcs-create-btn")
    page.fill("#merge-create-input", NAME)
    page.locator(
        "#merge-create-dropdown .player-option-name", has_text=NAME
    ).first.wait_for()


def _open_edit(page) -> None:
    create_comparison(page, ["Brian Baker", "Carl Cole"])
    page.click(".pcs-row-edit")
    page.fill("#merge-edit-input", NAME)
    page.locator(
        "#merge-edit-dropdown .player-option-name", has_text=NAME
    ).first.wait_for()


# (input, how to open it with a suggestion showing, what shows the pick happened)
CASES = {
    "players": (
        "#players-input",
        _open_players,
        lambda page: chip_names(page),
    ),
    "pcs_add": (
        "#pcs-add-input",
        _open_pcs_add,
        lambda page: pinned_names(page),
    ),
    "create": (
        "#merge-create-input",
        _open_create,
        lambda page: _members(page, "#merge-create-members"),
    ),
    "edit": (
        "#merge-edit-input",
        _open_edit,
        lambda page: _members(page, "#merge-edit-members"),
    ),
}


def _picked(page, name: str) -> bool:
    _, _, shows = CASES[name]
    return "Able" in str(shows(page))


def _check(page, name: str, composing: dict) -> None:
    selector, open_it, _ = CASES[name]
    open_it(page)

    handled = _press(page, selector, **composing)

    assert handled is False, "the Enter of a composition was taken by the page"
    assert not _picked(page, name)

    # The same Enter outside a composition still picks the top suggestion.
    assert _press(page, selector) is True
    assert _picked(page, name)


def test_the_enter_that_confirms_a_composition_picks_nobody_in_every_name_search(page):
    for name in CASES:
        _check(page, name, {"isComposing": True})
        page.reload()
        page.wait_for_function("document.querySelector('#chart')")


def test_safari_enter_after_compositionend_is_recognised_by_its_key_code(page):
    for name in CASES:
        _check(page, name, {"keyCode": 229})
        page.reload()
        page.wait_for_function("document.querySelector('#chart')")


def test_escape_during_a_composition_leaves_the_players_panel_open(page):
    _open_players(page)

    page.evaluate(
        """() => document.querySelector('#players-input').dispatchEvent(
            new KeyboardEvent('keydown', { key: 'Escape', isComposing: true, bubbles: true, cancelable: true }))"""
    )

    assert page.locator("#players-dropdown .player-option-name").first.is_visible()
    assert page.locator("#players-panel").is_visible()
