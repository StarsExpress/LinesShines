/* Shared placement for every floating popup (info-popover.js's click popovers,
 * linemate-card.js's hover tooltip). Dependency-free leaf, like dom.js/config.js.
 *
 * Popups are `position: fixed`, whose coordinates (like getBoundingClientRect())
 * are relative to the *layout* viewport. After a pinch-zoom the user only sees
 * the *visual* viewport — a window (offsetLeft/offsetTop, width x height in CSS
 * px, already divided by `scale`) that can sit anywhere inside the layout
 * viewport — so clamping against window.innerWidth can park a popup off-screen.
 * computePopupPlacement() is the pure clamp; placePopup() feeds it live DOM
 * measurements. Without window.visualViewport the viewport falls back to the
 * previous behavior (horizontal clamp against innerWidth, no vertical clamp).
 */

export const POPUP_MARGIN = 8;

// Pure. All inputs share one coordinate space (layout-viewport CSS px):
//   viewport: { offsetLeft, offsetTop, width, height, scale }  (visual viewport)
//   anchor:   { left, right, top, bottom }                     (trigger rect)
//   popup:    { width, height }                                (natural size)
//   align:    "left" | "right" | "center"                      (vs. the anchor)
// The margin is divided by `scale` so it stays ~`margin` *screen* px when zoomed.
// Returns { left, top, width }, width <= viewport.width - 2*margin, and left/top
// inside the viewport minus margins whenever the popup fits at all.
export function computePopupPlacement({ viewport, anchor, popup, align = "left", margin = POPUP_MARGIN }) {
  const m = margin / (viewport.scale || 1);
  const width = Math.min(popup.width, Math.max(viewport.width - 2 * m, 0));

  let wantedLeft = anchor.left;
  if (align === "right") wantedLeft = anchor.right - width;
  else if (align === "center") wantedLeft = (anchor.left + anchor.right) / 2 - width / 2;
  const minLeft = viewport.offsetLeft + m;
  const maxLeft = viewport.offsetLeft + viewport.width - m - width;
  const left = Math.max(minLeft, Math.min(wantedLeft, maxLeft));

  // Prefer above the anchor, else below it; then clamp into the viewport.
  const minTop = viewport.offsetTop + m;
  const maxTop = viewport.offsetTop + viewport.height - m - popup.height;
  const above = anchor.top - popup.height - m;
  const wantedTop = above >= minTop ? above : anchor.bottom + m;
  const top = Math.max(minTop, Math.min(wantedTop, maxTop));

  return { left, top, width };
}

export function getViewportRect() {
  const vv = window.visualViewport;
  if (vv) {
    return { offsetLeft: vv.offsetLeft, offsetTop: vv.offsetTop, width: vv.width, height: vv.height, scale: vv.scale };
  }
  return { offsetLeft: 0, offsetTop: 0, width: window.innerWidth, height: Infinity, scale: 1 };
}

// Measures `popupEl` (already in the DOM, position: fixed) and places it next
// to `anchorEl`. If the viewport is narrower than the popup, narrows it and
// re-measures (a narrower box wraps taller). Safe to call again, e.g. once an
// <img> inside the popup has loaded.
export function placePopup(anchorEl, popupEl, { align = "left" } = {}) {
  popupEl.style.width = "";
  const anchor = anchorEl.getBoundingClientRect();
  const viewport = getViewportRect();
  let rect = popupEl.getBoundingClientRect();
  let placed = computePopupPlacement({ viewport, anchor, popup: rect, align });
  if (placed.width < rect.width) {
    popupEl.style.boxSizing = "border-box";
    popupEl.style.width = `${placed.width}px`;
    rect = popupEl.getBoundingClientRect();
    placed = computePopupPlacement({ viewport, anchor, popup: rect, align });
  }
  popupEl.style.left = `${placed.left}px`;
  popupEl.style.top = `${placed.top}px`;
}

// Calls `onChange` when the visual viewport resizes or scrolls (pinch-zoom,
// pan, URL-bar collapse). Returns an unsubscribe function; a no-op without
// visualViewport.
export function watchViewport(onChange) {
  const vv = window.visualViewport;
  if (!vv) return () => {};
  vv.addEventListener("resize", onChange);
  vv.addEventListener("scroll", onChange);
  return () => {
    vv.removeEventListener("resize", onChange);
    vv.removeEventListener("scroll", onChange);
  };
}
