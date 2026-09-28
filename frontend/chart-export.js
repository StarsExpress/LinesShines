/* PNG export: chart rasterization + the shared credit-footer compositing
 * used by both the main chart's "Save Plot" and card-export.js's cards.
 * Split out of render.js purely to keep that file under the project's
 * 600-line guideline — no dependency on trace-building or logo placement,
 * so this was a cohesive, self-contained chunk rather than an arbitrary
 * line-count split.
 *
 * One deliberate exception to "no dependency on render.js": the bold/halo/
 * glow spotlighted-label emphasis (see render.js's applyLabelEmphasis) is
 * applied as inline SVG styles on the live, on-screen DOM — but
 * Plotly.toImage() regenerates its SVG from Plotly's own internal
 * layout/trace model, not from that live DOM, so none of it survives export
 * on its own (verified directly: the raw SVG toImage produces has zero
 * occurrences of the stroke/font-weight/filter styles that are clearly
 * present on screen at that exact moment). exportChartPngWithFooter() below
 * re-draws that same emphasis onto the export canvas itself via Canvas 2D
 * (which natively supports stroke-then-fill halos and shadow-blur glows —
 * no CSS/SVG trick needed), importing render.js's emphasis constants so the
 * two never drift apart into two different-looking versions of "spotlighted".
 */
import {
  POINT_LABEL_FONT_SIZE,
  LABEL_EMPHASIS_WEIGHT,
  LABEL_HALO_WIDTH,
  LABEL_HALO_COLOR,
  LABEL_GLOW_BLUR,
  LABEL_GLOW_COLOR,
  LABEL_FILL_RGB,
} from "./render.js";

// Metric labels can contain "%" or "/" (e.g. "Pressure %"), which aren't
// safe/clean in a downloaded filename — collapse any run of non-alphanumeric
// characters to a single underscore.
export function sanitizeForFilename(value) {
  return String(value).trim().replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

// Credit strip baked into exported PNGs only — the on-screen chart never
// shows this (the page's own .meta-band already covers it for site
// visitors). Drawn via canvas rather than a Plotly annotation: an in-chart
// annotation would still need its own margin math duplicated here, which is
// fragile to keep in sync with render()'s own margin.b — layering a
// fixed-height strip onto the finished raster is simpler and pixel-exact
// regardless of what layout produced it.
export const EXPORT_FOOTER_TEXT = "LinesShines · www.lines-shines.com · Source: PFF Premium Stats";
export const EXPORT_FOOTER_HEIGHT = 30; // logical px, pre-scale
export const EXPORT_FOOTER_FONT_SIZE = 12; // logical px, pre-scale — chart-annotation size
export const EXPORT_FOOTER_PADDING_X = 16; // logical px, pre-scale
export const EXPORT_FOOTER_BG = "#16301f"; // matches --turf-800, same swap render() does for export bg
export const EXPORT_FOOTER_COLOR = "rgba(169, 182, 169, 0.75)"; // --chalk-dim, muted so it doesn't compete with the plot

// Composites the credit-line footer onto a canvas already sized to include
// the extra footerPx strip beneath sourceHeight — split out of
// exportChartPngWithFooter so card-export.js's html2canvas-based exports can
// draw the exact same footer without duplicating this, keeping every PNG the
// app produces (chart or card) on one shared brand footer.
export function drawExportFooter(ctx, canvasWidth, sourceHeight, footerPx, scale) {
  ctx.fillStyle = EXPORT_FOOTER_COLOR;
  ctx.font = `${Math.round(EXPORT_FOOTER_FONT_SIZE * scale)}px Inter, sans-serif`;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  ctx.fillText(
    EXPORT_FOOTER_TEXT,
    canvasWidth - Math.round(EXPORT_FOOTER_PADDING_X * scale),
    sourceHeight + footerPx / 2
  );
}

// EXPORT_FOOTER_TEXT's own rendered width, at a given export scale — used
// by compositeFooterCanvas below to guarantee the canvas is wide enough to
// hold it. A throwaway canvas 2d context is the standard way to measure text
// without touching the DOM; harmless to create one per export click.
function measureFooterTextWidth(scale) {
  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = `${Math.round(EXPORT_FOOTER_FONT_SIZE * scale)}px Inter, sans-serif`;
  return ctx.measureText(EXPORT_FOOTER_TEXT).width;
}

// Returns a new canvas: `sourceCanvas` with EXPORT_FOOTER_BG behind it (so
// any transparent source pixels don't fall back to white) and the credit
// line drawn into the extra strip below. The main chart export is always
// comfortably wider than the footer text needs, but a narrower per-card
// export (card-export.js — a Player Card in particular, ~380px wide) can be
// narrower than the footer's own rendered width, silently clipping its left
// edge off the canvas entirely. Widening the canvas to at least fit the
// footer (with the source image centered in the extra room, rather than
// left-aligned with a lopsided gap on the right) fixes that for every card
// type/width at once instead of hardcoding a wider minimum per card type.
export function compositeFooterCanvas(sourceCanvas, scale) {
  const footerPx = Math.round(EXPORT_FOOTER_HEIGHT * scale);
  const paddingPx = Math.round(EXPORT_FOOTER_PADDING_X * scale);
  // +4px/scale safety margin: measureText's result depends on Inter having
  // actually finished loading by click time — a fallback-font measurement
  // fractionally narrower than the real render shouldn't reintroduce a
  // hairline clip.
  const minWidthForFooter = Math.ceil(measureFooterTextWidth(scale)) + paddingPx * 2 + Math.round(4 * scale);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(sourceCanvas.width, minWidthForFooter);
  canvas.height = sourceCanvas.height + footerPx;

  const ctx = canvas.getContext("2d");
  ctx.fillStyle = EXPORT_FOOTER_BG;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(sourceCanvas, Math.round((canvas.width - sourceCanvas.width) / 2), 0);
  drawExportFooter(ctx, canvas.width, sourceCanvas.height, footerPx, scale);
  return canvas;
}

export function downloadCanvasAsPng(canvas, filename) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("canvas.toBlob returned null"));
        return;
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${filename}.png`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      resolve();
    }, "image/png");
  });
}

// Plotly.toImage() re-derives its SVG from chartDiv's data/layout at
// whatever {width, height} is requested — not a simple scale of whatever's
// currently on screen, since font-relative margins/tick spacing/etc. can
// all shift at a different logical size. So to know where each spotlighted
// label will actually land in the export, we have to briefly lay the live
// chart out at that exact size ourselves and read Plotly's own computed
// positions back from the DOM, rather than guessing/re-deriving them.
// Returns {name, x, y} for every currently-spotlighted, currently-visible
// (non-blanked-by-declutter) label — matched via the same data-unformatted
// attribute applyLabelEmphasis() itself matches against, so this only ever
// captures labels that are genuinely emphasized on screen right now.
// `filterNames`, when given, only returns positions for those names — used
// on the export clone below, where nodes don't carry applyLabelEmphasis's
// own stroke styling (a fresh Plotly.newPlot never ran it), so "is this
// node spotlighted" has to be answered by name membership instead of by
// reading a style property that simply isn't there on that instance.
//
// A <text> node's own x/y attributes are in its *local* coordinate space,
// not final on-screen pixels — Plotly nests each label inside two transformed
// <g> groups (one for the textposition offset from its marker, one for the
// plot area's margin) that its raw x/y attributes don't account for at all.
// Confirmed directly: using the raw attributes put every drawn dot ~15-60px
// off from the real label. getCTM() resolves through however many ancestor
// transforms exist, however they're expressed — translate(), matrix(),
// nested arbitrarily — rather than us manually parsing and summing
// translate() strings, which would quietly break the moment Plotly's
// internal DOM structure changes in some future version.
function captureSpotlightedLabelPositions(chartDiv, filterNames) {
  const nodes = chartDiv.querySelectorAll(".scatterlayer text");
  const positions = [];
  nodes.forEach((node) => {
    const name = node.getAttribute("data-unformatted");
    if (!name) return;
    const spotlighted = filterNames ? filterNames.has(name) : !!node.style.stroke;
    if (!spotlighted) return;
    const localX = parseFloat(node.getAttribute("x"));
    const localY = parseFloat(node.getAttribute("y"));
    const ctm = node.getCTM();
    positions.push({
      name,
      x: ctm.a * localX + ctm.c * localY + ctm.e,
      y: ctm.b * localX + ctm.d * localY + ctm.f,
    });
  });
  return positions;
}

// Manually re-draws the same bold + halo + glow treatment applyLabelEmphasis
// applies on screen, straight onto the export canvas — see this file's
// header comment for why that's necessary at all. SVG text's default
// baseline is "alphabetic" with no dominant-baseline override on these
// nodes (confirmed from the live markup), which is also Canvas 2D's default
// textBaseline, so the captured x/y can be used as the fillText/strokeText
// anchor directly with no manual baseline correction.
function drawLabelEmphasisOverlay(ctx, positions, scale) {
  ctx.save();
  ctx.textAlign = "center";
  ctx.font = `${LABEL_EMPHASIS_WEIGHT} ${POINT_LABEL_FONT_SIZE * scale}px Oswald, sans-serif`;
  ctx.lineJoin = "round";
  ctx.lineWidth = LABEL_HALO_WIDTH * scale;
  ctx.strokeStyle = LABEL_HALO_COLOR;
  ctx.shadowBlur = LABEL_GLOW_BLUR * scale;
  ctx.shadowColor = LABEL_GLOW_COLOR;
  positions.forEach(({ name, x, y }) => {
    ctx.strokeText(name, x * scale, y * scale); // halo (+ glow, via shadowBlur) first
  });
  ctx.shadowBlur = 0; // fill pass shouldn't double the glow on top of the stroke pass's
  ctx.fillStyle = `rgb(${LABEL_FILL_RGB})`;
  positions.forEach(({ name, x, y }) => {
    ctx.fillText(name, x * scale, y * scale);
  });
  ctx.restore();
}

// Builds a fully separate, off-screen Plotly instance at the export's exact
// {width, height} and returns it. Earlier attempts to just relayout the
// *live* chartDiv to {width, height} and read positions back from it turned
// out to be unreliable: `responsive` (which this app runs with) is a plot
// **config** option, set in render.js's Plotly.react() call — not a layout
// attribute — so `Plotly.relayout(chartDiv, {width, height})` is silently
// fought by responsive's own resize handling and the live DOM snaps right
// back to the container's natural size instead of actually reaching the
// requested dimensions (confirmed directly: the live chart's
// getBoundingClientRect() never changed from its on-screen size no matter
// what was relaid out). Plotly.toImage() itself isn't subject to that,
// since it doesn't have a container to be responsive *to* — so the sizes
// the two ended up disagreeing on caused visibly duplicated/misaligned
// labels in testing. A dedicated, unattached clone sidesteps all of that:
// it has no responsive config and no container fighting it, so whatever
// size we ask for is the size it actually renders at, guaranteed consistent
// with what we read back for the overlay. Bonus: the live, on-screen chart
// is never touched at all, so there's no resize flash and nothing to
// restore afterward either.
//
// chartDiv.data/.layout are passed through a deep clone rather than handed
// to Plotly.newPlot() directly — confirmed the hard way that
// Plotly.newPlot(clone, chartDiv.data, ...) does NOT deep-clone the trace:
// clone.data[0] ends up being the literal same object as chartDiv.data[0],
// down to shared array references like textfont.color. Any restyle() this
// file later does on the clone (e.g. blanking spotlighted labels' native
// color before rasterizing, so our overlay isn't ghosted by them) was then
// silently corrupting the *live* chart's own trace data too — invisible
// until the next redraw touched it, which is exactly what made spotlighted
// players' labels vanish from the live page after an export while the
// downloaded PNG itself looked fine. Every value here (numbers, strings,
// nested arrays) is plain structured-cloneable data, so this is a fully
// faithful, reference-free copy.
function deepClone(value) {
  return typeof structuredClone === "function" ? structuredClone(value) : JSON.parse(JSON.stringify(value));
}

async function buildExportClone(chartDiv, width, height) {
  const clone = document.createElement("div");
  // Off-screen, not display:none — Plotly needs real layout/rendering to
  // measure text and lay out axes correctly, which a non-rendered
  // (display:none) element can't reliably provide.
  clone.style.position = "fixed";
  clone.style.left = "-99999px";
  clone.style.top = "0";
  clone.style.width = `${width}px`;
  clone.style.height = `${height}px`;
  document.body.appendChild(clone);
  await Plotly.newPlot(
    clone,
    deepClone(chartDiv.data),
    { ...deepClone(chartDiv.layout), width, height },
    { displayModeBar: false, responsive: false, staticPlot: true }
  );
  return clone;
}

// Renders the chart to a PNG via an off-screen export clone (see
// buildExportClone), re-draws the spotlighted-label emphasis on top of that
// render (see this file's header comment for why that redraw is necessary
// at all), then composites a footer strip onto a taller canvas before
// triggering the download — keeps the credit line out of the on-screen/
// exported-without-footer chart state.
export async function exportChartPngWithFooter(chartDiv, { width, height, scale, filename }) {
  const spotlightNames = new Set(captureSpotlightedLabelPositions(chartDiv).map((p) => p.name));
  const clone = await buildExportClone(chartDiv, width, height);
  try {
    const positions = captureSpotlightedLabelPositions(clone, spotlightNames);
    // Blank the clone's own native rendering for exactly these labels before
    // rasterizing — otherwise Plotly's thinner, non-bold native text is
    // still there underneath our bold+haloed overlay, and even pixel-perfect
    // alignment leaves a faint "ghost" of it peeking out around the edges
    // (confirmed directly: normal and 600-weight glyphs measure to slightly
    // different widths, so the native text's edges don't fully hide behind
    // ours). Only spotlighted labels are blanked — dimmed labels have no
    // overlay counterpart, so their native (faded) rendering is left alone.
    const cloneText = clone.data[0].text;
    const transparentColors = clone.data[0].textfont.color.map((color, i) =>
      spotlightNames.has(cloneText[i]) ? "rgba(0,0,0,0)" : color
    );
    await Plotly.restyle(clone, { "textfont.color": [transparentColors] }, [0]);
    const dataUrl = await Plotly.toImage(clone, { format: "png", scale });
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("Failed to load rendered chart image"));
      el.src = dataUrl;
    });
    const sourceCanvas = document.createElement("canvas");
    sourceCanvas.width = img.width;
    sourceCanvas.height = img.height;
    const ctx = sourceCanvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    await document.fonts.ready; // guards against a fallback-font flash if Oswald somehow hasn't finished loading yet
    drawLabelEmphasisOverlay(ctx, positions, scale);
    await downloadCanvasAsPng(compositeFooterCanvas(sourceCanvas, scale), filename);
  } finally {
    Plotly.purge(clone);
    clone.remove();
  }
}
