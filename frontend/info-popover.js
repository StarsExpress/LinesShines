/* Shared InfoPopover trigger — the (i) buttons on the Players filter header
 * and the Linemate Card's RSWA column header both build off this. Unlike
 * linemate-card.js's attachAppTooltip() (hover/focus only), this is
 * click-toggled: the Players filter is desktop/tablet-only already, and a
 * hover-only popup is unreachable on a touch device with no cursor to
 * dwell. Dependency-free like dom.js/config.js, so any layer can import it.
 *
 * The popup is appended to document.body rather than the trigger's own DOM
 * subtree, same reasoning as attachAppTooltip's app-tooltip: it has to
 * survive being triggered from inside a scrolling ancestor
 * (.linemate-summary-wrap) without getting clipped.
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

function openInfoPopover(triggerEl, text) {
  const popup = document.createElement("div");
  popup.className = "info-popover-content";
  popup.setAttribute("role", "dialog");

  const body = document.createElement("p");
  body.className = "info-popover-text";
  body.textContent = text;
  popup.appendChild(body);

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

// Builds a labeled "i" button that toggles a click-dismissible popup showing
// `text`. Returns the button for the caller to place wherever the trigger
// belongs — a filter header, a table header cell, etc. Only one popover is
// open at a time app-wide; opening a second (or re-clicking the open one's
// own trigger) closes whatever's open first.
export function createInfoPopover(text, { ariaLabel } = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "info-popover-trigger";
  btn.textContent = "i";
  btn.setAttribute("aria-haspopup", "dialog");
  btn.setAttribute("aria-expanded", "false");
  btn.setAttribute("aria-label", ariaLabel || text);
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const reopening = openTrigger === btn;
    closeInfoPopover();
    if (!reopening) openInfoPopover(btn, text);
  });
  return btn;
}
