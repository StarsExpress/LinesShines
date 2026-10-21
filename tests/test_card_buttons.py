"""Card corner buttons (Save, Fold, Close): size, distinct colours, contrast. Reads the real style.css."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "style.css").read_text(
    encoding="utf-8"
)
VARIABLES = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", CSS))
BUTTONS = ["card-save-btn", "scout-fold", "scout-close"]
CARD_BACKGROUND = VARIABLES["turf-700"]  # The lightest part of the card gradient.


def _luminance(hex_):
    chans = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]

    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(hex_a, hex_b):
    hi, lo = sorted((_luminance(hex_a), _luminance(hex_b)), reverse=True)

    return (hi + 0.05) / (lo + 0.05)


def _rule(cls):
    match = re.search(rf"\.{cls}\s*\{{([^}}]*)\}}", CSS)
    assert match, f".{cls} is missing from style.css"

    return match.group(1)


def _prop(cls, prop):
    match = re.search(rf"(?<![\w-]){prop}:\s*([^;]+);", _rule(cls))
    assert match, f".{cls} has no {prop}"

    return match.group(1).strip()


def _colour(value):
    """A hex colour, whether written as #rrggbb or var(--name); a border's colour is its last word."""
    value = value.split()[-1]
    named = re.fullmatch(r"var\(--([\w-]+)\)", value)

    colour = VARIABLES[named.group(1)] if named else value
    if re.fullmatch(r"#[0-9a-fA-F]{3}", colour):  # #000 -> #000000
        colour = "#" + "".join(ch * 2 for ch in colour[1:])

    return colour.lower()


def _fill(cls):
    return _colour(_prop(cls, "background"))


def _edge(cls):
    return _colour(_prop(cls, "border"))


def _icon(cls):
    return _colour(_prop(cls, "color"))


@pytest.mark.parametrize("cls", BUTTONS)
def test_buttons_are_24px(cls):
    assert _prop(cls, "width") == "24px"
    assert _prop(cls, "height") == "24px"


def test_the_three_buttons_have_different_fills():
    fills = [_fill(cls) for cls in BUTTONS]
    assert len(set(fills)) == 3, f"two buttons share a fill: {fills}"


@pytest.mark.parametrize("cls", BUTTONS)
def test_icon_is_readable_on_its_button(cls):
    assert _contrast(_icon(cls), _fill(cls)) >= 4.5


@pytest.mark.parametrize("cls", BUTTONS)
def test_button_edge_stands_out_from_the_card(cls):
    assert _contrast(_edge(cls), CARD_BACKGROUND) >= 3


def test_save_keeps_the_black_fill_and_light_outline():
    assert _fill("card-save-btn") == "#000000"
    assert _edge("card-save-btn") == "#f0ede4"
