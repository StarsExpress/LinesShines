"""Card PNG exports: a square white frame on the image's outermost edge; the chart export has none but shares the gold credit band."""

from __future__ import annotations

import base64

import pytest

FRAME = [240, 237, 228]  # #f0ede4.
BACKGROUND = [22, 48, 31]  # #16301f.
GOLD = [211, 167, 61]  # #d3a73d.


@pytest.fixture()
def page(live_server_url):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(live_server_url)

        # App has finished loading once it holds its metadata, its applied filters and a slice of records.
        pg.wait_for_function(
            "async () => { const d = await import('/data.js'); return !!(d.metadata && d.appliedFilters && d.currentRecords.length); }"
        )

        yield pg
        browser.close()


# Pixels on the four edges (first and last pixel of the middle of each side, to stay clear of
# the corners) and the four corners of a canvas or a decoded PNG, as [r, g, b] lists.
SAMPLE_JS = """
(canvas) => {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const at = (x, y) => Array.from(ctx.getImageData(x, y, 1, 1).data.slice(0, 3));
  return {
    width: w, height: h,
    corners: [at(0, 0), at(w - 1, 0), at(0, h - 1), at(w - 1, h - 1)],
    edges: [at(w >> 1, 0), at(w >> 1, h - 1), at(0, h >> 1), at(w - 1, h >> 1)],
    // Just inside the frame at both ends of the credit strip, clear of the right-aligned text.
    band: [at(8, h - 12), at(w - 9, h - 12)],
    alpha: [ctx.getImageData(0, 0, 1, 1).data[3], ctx.getImageData(w - 1, h - 1, 1, 1).data[3]],
  };
}
"""

COMPOSITE_JS = """
async ({ frame, creditBand, notesDivider, notes, sourceWidth }) => {
  const c = await import('/chart-export.js');
  const source = document.createElement('canvas');
  source.width = sourceWidth;
  source.height = 300;
  const sctx = source.getContext('2d');
  sctx.fillStyle = '#1e3d28';
  sctx.fillRect(0, 0, source.width, source.height);

  const out = c.compositeFooterCanvas(source, 2, { appendixNotes: notes, frame, creditBand, notesDivider });
  const result = (%s)(out);
  // The row where the notes strip starts (the source image is 300 high): is it dashed, how many dashes?
  const row = out.getContext('2d').getImageData(0, 300, out.width, 1).data;
  let lit = 0, gaps = 0, dashes = 0, prev = false;
  for (let x = 40; x < out.width - 40; x++) {
    const isLit = row[x * 4] > 60;
    if (isLit) lit++; else gaps++;
    if (isLit && !prev) dashes++;
    prev = isLit;
  }
  return { ...result, lit, gaps, dashes };
}
""" % SAMPLE_JS.strip()

# Decodes a downloaded PNG (as base64) and samples it the same way.
DECODE_JS = """
async (b64) => {
  const img = new Image();
  img.src = 'data:image/png;base64,' + b64;
  await img.decode();
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  canvas.getContext('2d').drawImage(img, 0, 0);
  return (%s)(canvas);
}
""" % SAMPLE_JS.strip()

NOTES = [
    "Pass rush win rate: a note long enough to wrap on a narrow card when the canvas is small.",
    "Second note.",
]


def _composite(page, **kwargs):
    return page.evaluate(
        COMPOSITE_JS,
        {
            "frame": False,
            "creditBand": False,
            "notesDivider": False,
            "notes": [],
            "sourceWidth": 800,
            **kwargs,
        },
    )


def _all_frame(sample):
    return all(p == FRAME for p in sample["corners"] + sample["edges"])


def _none_frame(sample):
    return all(p != FRAME for p in sample["corners"] + sample["edges"])


@pytest.mark.parametrize("notes", [[], NOTES], ids=["no-notes", "with-notes"])
@pytest.mark.parametrize("source_width", [800, 380], ids=["wide-card", "narrow-card"])
def test_frame_option_puts_the_frame_on_every_outer_edge_and_corner(
    page, notes, source_width
):
    # 380 is narrower than credit line, so the canvas is widened and the card centred.
    sample = _composite(page, frame=True, notes=notes, sourceWidth=source_width)

    assert _all_frame(sample), sample
    assert sample["alpha"] == [255, 255], "corners must be opaque, not transparent"


def test_without_the_frame_option_the_edges_are_the_plain_background(page):
    # Chart export — Save Plot — calls compositeFooterCanvas without `frame`: no frame on it.
    sample = _composite(page, sourceWidth=380)

    assert _none_frame(sample), sample
    assert sample["corners"][2] == BACKGROUND and sample["corners"][3] == BACKGROUND


@pytest.mark.parametrize("notes", [[], NOTES], ids=["no-notes", "with-notes"])
@pytest.mark.parametrize("source_width", [800, 380], ids=["wide-card", "narrow-card"])
def test_credit_band_option_fills_the_credit_strip_with_gold_inside_the_frame(
    page, notes, source_width
):
    sample = _composite(
        page, frame=True, creditBand=True, notes=notes, sourceWidth=source_width
    )

    assert sample["band"] == [GOLD, GOLD], sample
    assert _all_frame(sample), "the frame must stay on the outer edge over the band"


def test_without_the_credit_band_option_the_strip_is_the_plain_background(page):
    # Without the option, credit strip is gray text on plain background.
    sample = _composite(page, frame=True, sourceWidth=800)

    assert sample["band"] == [BACKGROUND, BACKGROUND], sample


@pytest.mark.parametrize("source_width", [800, 380], ids=["wide-card", "narrow-card"])
def test_notes_divider_option_draws_a_dashed_line_above_the_notes(page, source_width):
    sample = _composite(
        page, frame=True, notesDivider=True, notes=NOTES, sourceWidth=source_width
    )

    assert sample["dashes"] >= 5, sample
    assert (
        sample["lit"] > 0 and sample["gaps"] > 0
    ), "a dashed line has both dashes and gaps"

    # Dashes and gaps are the same length (4px at 2x = 8 device px each), so about half the row is lit.
    assert 0.35 < sample["lit"] / (sample["lit"] + sample["gaps"]) < 0.65, sample


def test_no_divider_without_the_option_or_without_notes(page):
    without_option = _composite(page, frame=True, notes=NOTES, sourceWidth=800)
    without_notes = _composite(page, frame=True, notesDivider=True, sourceWidth=800)

    assert without_option["lit"] == 0, without_option
    assert without_notes["lit"] == 0, without_notes


def test_the_notes_divider_adds_no_size(page):
    plain = _composite(page, frame=True, notes=NOTES, sourceWidth=800)
    divided = _composite(
        page, frame=True, notesDivider=True, notes=NOTES, sourceWidth=800
    )

    assert (plain["width"], plain["height"]) == (divided["width"], divided["height"])


def test_the_credit_band_adds_no_size(page):
    plain = _composite(page, frame=True, sourceWidth=800, notes=NOTES)
    banded = _composite(page, frame=True, creditBand=True, sourceWidth=800, notes=NOTES)

    assert (plain["width"], plain["height"]) == (banded["width"], banded["height"])


def test_the_frame_adds_no_size(page):
    plain = _composite(page, sourceWidth=800, notes=NOTES)
    framed = _composite(page, sourceWidth=800, notes=NOTES, frame=True)

    assert (plain["width"], plain["height"]) == (framed["width"], framed["height"])


# Opens a real Player Card, clicks its Save button and returns the downloaded PNG's bytes (base64).
def _export_player_card(page, with_notes):
    page.evaluate(
        """
        async (withNotes) => {
          const d = await import('/data.js');
          const s = await import('/scout-card.js');
          s.closeAllScoutCards();
          s.viewFloatingCard(d.currentRecords[0]);
          const toggle = document.getElementById('metric-notes-toggle');
          if (toggle) { toggle.checked = withNotes; toggle.dispatchEvent(new Event('change', { bubbles: true })); }
        }
        """,
        with_notes,
    )

    page.wait_for_selector(".scout-card.is-active .card-save-btn")

    with page.expect_download() as info:
        page.locator(".scout-card.is-active .card-save-btn").first.click()

    with open(info.value.path(), "rb") as f:
        return base64.b64encode(f.read()).decode()


@pytest.mark.parametrize("with_notes", [False, True], ids=["no-notes", "with-notes"])
def test_an_exported_player_card_png_has_the_frame_on_its_outer_edge(page, with_notes):
    sample = page.evaluate(DECODE_JS, _export_player_card(page, with_notes))

    assert _all_frame(sample), sample


@pytest.mark.parametrize("with_notes", [False, True], ids=["no-notes", "with-notes"])
def test_an_exported_player_card_png_has_the_gold_credit_band(page, with_notes):
    sample = page.evaluate(DECODE_JS, _export_player_card(page, with_notes))

    assert sample["band"] == [GOLD, GOLD], sample


# Save Plot's export (Plotly, not testable here) must share the gold credit band and must not get the frame
# or the notes divider. Checked on the call site's source.
def test_the_chart_export_call_site_passes_the_credit_band_only():
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "frontend" / "chart-export.js"
    ).read_text()

    # Prettier may wrap the call over several lines.
    match = re.search(
        r"compositeFooterCanvas\(sourceCanvas, scale, \{(.*?)\}\)", source, re.DOTALL
    )

    assert match, "the chart export's compositeFooterCanvas call was not found"
    call = match.group(1)

    assert "creditBand: true" in call
    assert "frame" not in call and "notesDivider" not in call
