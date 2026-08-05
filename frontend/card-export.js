/* Per-card PNG export — Save button shared by all three card types (Player,
 * Merge, Linemate). Captures the card's own DOM node via the vendored
 * html2canvas (frontend/vendor/html2canvas.min.js, loaded as the `html2canvas`
 * global by index.html — no bundler here, same reasoning as Plotly's own
 * vendored script), excluding each card's own chrome (close/fold/resize
 * handles/this button itself), then composites the exact same credit-line
 * footer the main chart export uses (render.js's compositeFooterCanvas) so
 * every PNG this app produces — chart or card — carries the same brand
 * footer. Depends on render.js (one-directional: render.js never imports
 * this module), not on any of the three card modules, so scout-card.js/
 * merge-card.js/linemate-card.js can each import attachCardSave() without
 * adding a new cycle.
 */
import { compositeFooterCanvas, downloadCanvasAsPng, sanitizeForFilename } from "./render.js";

export { sanitizeForFilename };

// Matches exportChartPngWithFooter's scale:2 (see main.js's Save Plot
// handler) so card and chart exports come out at the same pixel density.
const CARD_EXPORT_SCALE = 2;

// .scout-card-panel's real background is a translucent gradient meant to be
// blurred against whatever sits behind it on screen (backdrop-filter, which
// html2canvas can't render) — without a solid backing color here, html2canvas
// would composite that translucency onto white instead. Matches --turf-800,
// the same color main.js's Save Plot swap uses for the chart's own bg.
const CARD_EXPORT_BG = "#16301f";

// Rough allowance for .scout-card-body's own horizontal padding (16px each
// side) plus the panel's 1px border, added on top of a scroll strip's
// measured scrollWidth when widening the card to fit it — a few stray px of
// extra right-edge background is harmless, clipping the content isn't.
const CARD_HORIZONTAL_PADDING = 40;

// Every card's own close/fold/resize chrome, this Save button itself, and
// Linemate Card's "See more" toggle (meaningless once buildExportClone below
// force-expands the roster to its full length — see linemate-card.js's
// prepareClone) shouldn't appear in the exported image. html2canvas's
// ignoreElements is the standard way to exclude specific nodes from a
// capture without a hide-then-restore choreography.
function shouldIgnoreForExport(el) {
  return (
    el.classList &&
    (el.classList.contains("scout-close") ||
      el.classList.contains("scout-fold") ||
      el.classList.contains("scout-resize-handle") ||
      el.classList.contains("card-save-btn") ||
      el.classList.contains("linemate-see-more"))
  );
}

// html2canvas paints exactly the DOM's current *visual* state, not the data
// underneath it — a folded card, one dragged/resized narrower or shorter
// than its content, or any of the card's own internal overflow:auto
// scrollers (the panel's own 480px height cap shared by every card type,
// Merge Card's horizontally-scrolling metric columns, Linemate Card's
// horizontally-scrolling Line Summary table) would otherwise export exactly
// whatever's clipped/scrolled out of view on screen right now, not the full
// card. Rather than mutating the live card the user is looking at (hide →
// capture → restore has a flicker/timing window, and drag/resize state is
// awkward to snapshot and faithfully undo), this clones the card off-screen
// and resets only the CLONE to a "complete" state before handing it to
// html2canvas — the on-screen card is never touched, so the user's current
// fold/resize/scroll arrangement survives the export untouched.
function buildExportClone(cardEl) {
  const clone = cardEl.cloneNode(true);
  // Drops every inline style cloneNode copied over — drag's left/top,
  // resize's width, bringToFront's z-index — none of which should carry
  // into an off-screen export clone.
  clone.style.cssText = "";
  clone.style.position = "fixed";
  clone.style.top = "0";
  clone.style.left = "-99999px";
  // Must be attached before any scrollWidth read below reflects real
  // layout — a detached node always reports 0.
  document.body.appendChild(clone);

  clone.classList.remove("is-folded", "is-dragging", "is-resizing");

  const panelEl = clone.querySelector(".scout-card-panel");
  if (panelEl) panelEl.style.cssText = "height: auto; max-height: none; overflow: visible;";

  // Merge Card's frozen Player/Team/Linemates columns (BLUEPRINT.md's Excel
  // frozen-pane treatment) are position:sticky — turns out that does NOT
  // gracefully fall back to their normal flow position once their scroll
  // container stops scrolling, at least not for this off-screen fixed-
  // position clone: measured directly, they get shoved to sit near the far
  // right edge of the widened row instead of staying put at the left,
  // because a sticky element still hunts for a scrolling ancestor (falling
  // back to the page itself, whose scroll position has nothing to do with
  // this off-screen clone) and clamps to whatever position that leaves
  // reachable within its own cell. Forcing position:static (clearing the
  // sticky left offset with it) sidesteps that entirely — with nothing
  // scrolling underneath them in the export, sticky was only ever pinning
  // them to their own already-correct flow position anyway.
  clone.querySelectorAll(".merge-table-frozen").forEach((cell) => {
    cell.style.position = "static";
    cell.style.left = "";
  });

  // Lays every column flat in one row instead of clipping to whatever was
  // scrolled into view, then widens the card itself to fit.
  let requiredWidth = 0;
  clone.querySelectorAll(".merge-table-wrap, .linemate-summary-wrap").forEach((scrollEl) => {
    scrollEl.style.overflow = "visible";
    requiredWidth = Math.max(requiredWidth, scrollEl.scrollWidth);
  });
  if (requiredWidth > 0) {
    clone.style.maxWidth = "none";
    clone.style.width = `${requiredWidth + CARD_HORIZONTAL_PADDING}px`;
  }

  return clone;
}

// `prepareClone(clone)`, if given, runs after the generic reset above —
// Linemate Card uses it to force-render its full roster (bypassing "See
// more") straight into the clone; Player/Merge Cards don't need it, since
// nothing on them is conditionally left un-rendered the way a collapsed
// roster is.
export async function exportCardPng(cardEl, filename, prepareClone) {
  const clone = buildExportClone(cardEl);
  try {
    if (prepareClone) prepareClone(clone);
    const sourceCanvas = await window.html2canvas(clone, {
      backgroundColor: CARD_EXPORT_BG,
      scale: CARD_EXPORT_SCALE,
      ignoreElements: shouldIgnoreForExport,
    });
    await downloadCanvasAsPng(compositeFooterCanvas(sourceCanvas, CARD_EXPORT_SCALE), filename);
  } finally {
    clone.remove();
  }
}

// Wires a card's .card-save-btn once, at open/mount time — same as the
// fold/close/drag listeners each card type already wires once in its own
// open*Card()/mountMergeCardElement(). `getFilename` is called fresh on
// every click (not captured once) so a Merge Card's filename reflects
// whatever its current membership is, even after an Edit popup add/remove —
// see the callers in merge-card.js.
export function attachCardSave(cardEl, getFilename, prepareClone) {
  const btn = cardEl.querySelector(".card-save-btn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    try {
      await exportCardPng(cardEl, getFilename(), prepareClone);
    } catch (err) {
      // Best-effort convenience feature — same swallow-and-log pattern as
      // loadMetadata()'s own top-level .catch() in main.js, not a popup.
      console.error("Card PNG export failed:", err);
    } finally {
      btn.disabled = false;
    }
  });
}
