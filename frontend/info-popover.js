/* Shared InfoPopover trigger — the (i) buttons on the Players filter header,
 * the Linemate Card's RSWA column header, and the X/Y axis metric-formula
 * triggers (main.js) all build off this. Unlike linemate-card.js's
 * attachAppTooltip() (hover/focus only), this is click-toggled: several
 * callers (Players filter, axis controls) are visible on touch devices
 * where there's no cursor to dwell for a hover-only popup. Dependency-free
 * like dom.js/config.js, so any layer can import it.
 *
 * The popup is appended to document.body rather than the trigger's own DOM
 * subtree, same reasoning as attachAppTooltip's app-tooltip: it has to
 * survive being triggered from inside a scrolling ancestor
 * (.linemate-summary-wrap) without getting clipped.
 *
 * Content is normally a static string. The axis triggers instead pass a
 * function returning `{ imgSrc, imgAlt }` — see createInfoPopover()'s own
 * comment for why (the underlying <select>'s value can change after the
 * trigger button is built).
 */

let openPopup = null;
let openTrigger = null;

function closeInfoPopover() {
  if (openPopup) openPopup.remove();
  if (openTrigger) openTrigger.setAttribute("aria-expanded", "false");
  openPopup = null;
  openTrigger = null;
  document.removeEventListener("mousedown", onDocMouseDown, true);
  document.removeEventListener("keydown", onDocKeyDown, true);
}

function onDocMouseDown(e) {
  if (openTrigger && (e.target === openTrigger || openTrigger.contains(e.target))) return;
  if (openPopup && openPopup.contains(e.target)) return;
  closeInfoPopover();
}

function onDocKeyDown(e) {
  if (e.key === "Escape") closeInfoPopover();
}

function positionInfoPopover(triggerEl, popupEl) {
  const triggerRect = triggerEl.getBoundingClientRect();
  const popupRect = popupEl.getBoundingClientRect();
  const left = Math.min(Math.max(triggerRect.left, 8), window.innerWidth - popupRect.width - 8);
  const above = triggerRect.top - popupRect.height - 8;
  const top = above >= 8 ? above : triggerRect.bottom + 8;
  popupEl.style.left = `${left}px`;
  popupEl.style.top = `${top}px`;
}

function openInfoPopover(triggerEl, content, { formula } = {}) {
  const popup = document.createElement("div");
  popup.className = formula ? "info-popover-content info-popover-content--formula" : "info-popover-content";
  popup.setAttribute("role", "dialog");

  // `content` is a plain string for every caller that existed before the
  // metric-formula popovers (Players union rule, RSWA header) — resolved
  // once at creation time, same as always: normalized to `{ text }` below,
  // one <p>, unchanged from before this object form existed. A formula
  // popover instead passes a function, called here (at open time, not
  // creation time) so it always reflects whichever metric is currently
  // selected in the X/Y axis dropdown rather than a value frozen when the
  // trigger button was first built — returning `{ imgSrc, imgAlt }` (a
  // rendered formula) or `{ text }` (a metric with no rendered formula,
  // falling back to its short description). Either form may also carry
  // `extraText` — a second paragraph appended below, e.g. the shared
  // TPS_NOTE appended under a TPS-variant metric's own formula/description
  // (see main.js's axisFormulaContent()) — kept as a distinct field rather
  // than concatenated into `text`/`imgAlt` so it renders as its own visually
  // separated paragraph instead of a run-on sentence.
  const resolved = typeof content === "function" ? content() : content;
  const parts = typeof resolved === "string" ? { text: resolved } : resolved || {};
  if (parts.imgSrc) {
    const img = document.createElement("img");
    img.className = "info-popover-formula-img";
    img.alt = parts.imgAlt || "";
    // positionInfoPopover() below runs immediately after this function
    // appends the popup, using getBoundingClientRect() — but an <img> has
    // no size until its request resolves, so that first measurement sees a
    // near-zero box and the popup gets left-anchored as if it were much
    // narrower than the formula it's about to render, overflowing the
    // right edge once the SVG actually loads and the box expands. Only
    // `src` triggers the load, so it's set last, after this listener is
    // already attached — reposition once true dimensions are known.
    img.addEventListener("load", () => {
      if (openPopup === popup) positionInfoPopover(triggerEl, popup);
    });
    img.src = parts.imgSrc;
    popup.appendChild(img);
  } else if (parts.text) {
    const body = document.createElement("p");
    body.className = "info-popover-text";
    body.textContent = parts.text;
    popup.appendChild(body);
  }
  if (parts.extraText) {
    const extra = document.createElement("p");
    extra.className = "info-popover-text info-popover-extra-text";
    extra.textContent = parts.extraText;
    popup.appendChild(extra);
  }

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "info-popover-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", closeInfoPopover);
  popup.appendChild(closeBtn);

  document.body.appendChild(popup);
  positionInfoPopover(triggerEl, popup);

  openPopup = popup;
  openTrigger = triggerEl;
  triggerEl.setAttribute("aria-expanded", "true");

  document.addEventListener("mousedown", onDocMouseDown, true);
  document.addEventListener("keydown", onDocKeyDown, true);
}

// Builds a button that toggles a click-dismissible popup showing `content`.
// `content` is normally a plain string, resolved once, right here, at
// creation time. Pass a function instead when the popup must reflect
// something that can change after the trigger is built without the trigger
// itself being recreated (e.g. the X/Y axis metric-formula popovers below,
// where the underlying <select>'s value can change at any time) — it's
// called fresh every time the popup opens, in openInfoPopover(), and may
// return either a string or `{ imgSrc, imgAlt }` to show a formula image
// instead of text. Pass `formula: true` alongside a function that returns
// `{ imgSrc, imgAlt }` so the popup gets the wider `--formula` box instead
// of the standard 240px text box (see style.css).
// When `label` is given, that's the button's entire visible content — no "i"
// icon — bordered the same as any other button in the row/header it sits in,
// so it reads as a normal clickable label rather than needing a separate
// icon to flag it as interactive. `labelId`, if given, is set on the label
// span so an unrelated element elsewhere (e.g. the Players toggle button/
// input) can still point at this text via aria-labelledby even though it now
// lives inside this button rather than a standalone <label>. Returns the
// button for the caller to place wherever the trigger belongs — a filter
// header, a table header cell, etc. Only one popover is open at a time
// app-wide; opening a second (or re-clicking the open one's own trigger)
// closes whatever's open first.
export function createInfoPopover(content, { ariaLabel, label, labelId, formula } = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "info-popover-trigger";
  btn.setAttribute("aria-haspopup", "dialog");
  btn.setAttribute("aria-expanded", "false");
  // A function's return value isn't known at creation time, so a dynamic
  // popover must pass its own `ariaLabel` — fall back to `label` alone
  // (never the unresolved function) rather than stringifying it.
  const staticText = typeof content === "string" ? content : "";
  btn.setAttribute(
    "aria-label",
    ariaLabel || (label ? `${label}${staticText ? `: ${staticText}` : ""}` : staticText) || "More info"
  );

  if (label) {
    const labelSpan = document.createElement("span");
    labelSpan.className = "info-popover-label";
    if (labelId) labelSpan.id = labelId;
    labelSpan.textContent = label;
    btn.appendChild(labelSpan);
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const reopening = openTrigger === btn;
    closeInfoPopover();
    if (!reopening) openInfoPopover(btn, content, { formula });
  });
  return btn;
}
