/* Shared positioning system for all three card types (Player, Merge,
 * Linemate) — drag, resize, fold, cascade, z-index, and the shared
 * {id, origin, folded} shape's supporting helpers (ordinal(), used by every
 * card's percentile display; withTrailingPeriod(), used by the quota-full
 * messages in merge-card.js/workspace.js). Card-type-agnostic — operates on
 * the shared .scout-card class, never imports a card type's own module for
 * its own logic. Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3
 * step 4.
 *
 * openCardsCount(), updateScoutEmptyHint(), and clearScoutCardDragPositions()
 * are the one place this module reads scoutCards/mergeCards/linemateCards —
 * maps owned by scout-card.js/merge-card.js/linemate-card.js respectively —
 * which makes this a deliberate three-way circular import (cards-base.js ↔
 * scout-card.js, ↔ merge-card.js, ↔ linemate-card.js). This is safe: every
 * use is inside a function body, never at module-evaluation time, so by the
 * time any of these run (a user interaction, always after full page load)
 * every module in the cycle has already finished loading and every binding
 * is live. This is NOT the cycle MODULARIZATION.md §4 warns against (a
 * Linemate Card importing merge-card.js directly) — linemate-card.js never
 * imports scout-card.js or merge-card.js here or anywhere else.
 */
import { els } from "./dom.js";
import { scoutCards } from "./scout-card.js";
import { mergeCards } from "./merge-card.js";
import { linemateCards } from "./linemate-card.js";

// Below 860px scouting cards are static blocks stacked under the chart (see
// the @media (max-width: 860px) rules in style.css), not floating overlays
// — dragging/cascading only makes sense above that breakpoint, same cutoff
// targetLogoPx() already uses for the desktop/mobile split.
export function isDesktopScoutLayout() {
  return window.innerWidth >= 860;
}

export function ordinal(n) {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

// Avoids a stray double period in messages that tack a full stop onto a
// player name — "Jr."/"Sr." suffixes (and any other name already ending in
// a period) don't get a second one.
export function withTrailingPeriod(text) {
  return text.endsWith(".") ? text : `${text}.`;
}

// Shared incrementing counter so whichever card was most recently opened,
// clicked, or dragged gets bumped above every other open card — otherwise
// overlapping cards would stack in open-order forever with no way to bring
// an older one back to the front.
export let scoutZCounter = 10;

// --- Card identity (Player / Merge / Linemate) ------------------------------
//
// Every open card gets a stable {id, origin} pair per BLUEPRINT.md §5, so a
// future recommender (v2.0.0) can read merge provenance without a card's
// identity depending on its current member set. origin is 'seed' for a
// Player Card the user opened directly off the chart, 'merge' for one built
// via the Merge button, 'linemate' for a Linemate Association Card.
export let cardSeq = 0;
export function nextCardId() {
  cardSeq += 1;
  return `card-${cardSeq}`;
}

// Merge Card entries can outlive their floating view (closeMergeCardFloating()
// leaves the row in mergeCards with entry.el === null), so counting mergeCards.size
// directly would overcount what's actually on screen — only count its open entries.
export function openCardsCount() {
  let openMergeCount = 0;
  mergeCards.forEach((entry) => {
    if (entry.el) openMergeCount += 1;
  });
  return scoutCards.size + openMergeCount + linemateCards.size;
}

export function updateScoutEmptyHint() {
  els.scoutEmptyHint.hidden = openCardsCount() > 0;
}

// Every open card gets a higher inline z-index than anything opened,
// clicked, or dragged before it, so the one the user is currently paying
// attention to always renders on top of any it overlaps.
export function bringScoutCardToFront(cardEl) {
  scoutZCounter += 1;
  cardEl.style.zIndex = String(scoutZCounter);
}

// The first card opened keeps the CSS default top-right anchor (top:24,
// right:24) — same spot the single card always used to appear. Every card
// after that gets an explicit inline left/top, nudged down-left a bit
// further per already-open card (Player, Merge, or Linemate — they all share
// this one cascade sequence), so opening several in a row fans them out
// instead of stacking them exactly on top of each other. They're still
// fully draggable afterward, and dragging one on top of another is exactly
// the overlap the user asked to allow.
export const SCOUT_CASCADE_STEP = 28;
export const SCOUT_CASCADE_WRAP = 8; // wrap the offset so a long run of opens can't drift off-panel
export function cascadeScoutCardPosition(cardEl) {
  if (openCardsCount() === 0 || !isDesktopScoutLayout()) return;
  const panelRect = els.chartPanel.getBoundingClientRect();
  const cardRect = cardEl.getBoundingClientRect();
  const offset = (openCardsCount() % SCOUT_CASCADE_WRAP) * SCOUT_CASCADE_STEP;
  const maxLeft = Math.max(panelRect.width - cardRect.width, 0);
  const maxTop = Math.max(panelRect.height - cardRect.height, 0);
  cardEl.style.left = `${Math.min(Math.max(panelRect.width - cardRect.width - 24 - offset, 0), maxLeft)}px`;
  cardEl.style.top = `${Math.min(24 + offset, maxTop)}px`;
  cardEl.style.right = "auto";
}

// Applies fold/unfold visuals for whatever state.folded currently holds —
// shared by the explicit fold-button click (toggleCardFold) and the
// resize-driven auto fold/unfold below (setCardFolded), so both paths stay
// in sync on the same CSS class, icon, and stashed-height behavior. Folding
// hides the metric body via CSS (.is-folded); a card the user has edge-
// resized taller would otherwise leave a tall dead gap under the header once
// that body disappears, so its inline panel height is stashed here and
// restored on unfold rather than lost. `onUnfold` lets a Linemate Card reset
// its "See more" state back to collapsed every time it re-expands (§2.5).
export function applyCardFoldVisual(cardEl, state, onUnfold) {
  cardEl.classList.toggle("is-folded", state.folded);
  const foldBtn = cardEl.querySelector(".scout-fold");
  const icon = foldBtn && foldBtn.querySelector("i");
  if (icon) icon.className = state.folded ? "fa-solid fa-chevron-down" : "fa-solid fa-chevron-up";
  if (foldBtn) foldBtn.setAttribute("aria-label", state.folded ? "Unfold card" : "Fold card");

  const panelEl = cardEl.querySelector(".scout-card-panel");
  if (panelEl) {
    if (state.folded) {
      if (panelEl.style.height) panelEl.dataset.resizedHeight = panelEl.style.height;
      panelEl.style.height = "";
      panelEl.style.maxHeight = "";
    } else if (panelEl.dataset.resizedHeight) {
      panelEl.style.height = panelEl.dataset.resizedHeight;
      panelEl.style.maxHeight = "none";
    }
  }

  if (!state.folded && onUnfold) onUnfold();
}

// Wired to every card type's fold button — flips state.folded and applies it.
export function toggleCardFold(cardEl, state, onUnfold) {
  state.folded = !state.folded;
  applyCardFoldVisual(cardEl, state, onUnfold);
}

// Wired to the resize handles (see beginScoutResize/endScoutResize below) so
// a pull/push can drive fold state directly instead of only the button —
// dragging a folded card's edge auto-unfolds it (there's nothing to reveal
// while its body is display:none), and pushing an unfolded card's edge back
// down to the resize floor auto-folds it. No-ops if already in that state.
export function setCardFolded(cardEl, state, folded, onUnfold) {
  if (state.folded === folded) return;
  state.folded = folded;
  applyCardFoldVisual(cardEl, state, onUnfold);
}

// Inline left/top/width/height (set by dragging, edge-resizing, or
// cascadeScoutCardPosition) sit at higher specificity than the mobile media
// query's `top: auto; right: auto; width: auto;` reset, so they'd otherwise
// survive a resize down to mobile and break the stacked layout. Clearing
// them lets the stylesheet's position/size rules take back over for every
// currently-open card of every type.
export function clearScoutCardDragPositions() {
  [...scoutCards.values(), ...mergeCards.values(), ...linemateCards.values()].forEach((entry) => {
    if (!entry.el) return; // a Merge Card row can survive its floating view being closed, see closeMergeCardFloating()
    entry.el.style.left = "";
    entry.el.style.top = "";
    entry.el.style.right = "";
    entry.el.style.width = "";
    const panelEl = entry.el.querySelector(".scout-card-panel");
    if (panelEl) {
      panelEl.style.height = "";
      panelEl.style.maxHeight = "";
      delete panelEl.dataset.resizedHeight;
    }
  });
}

// Drag state for the one pointer currently moving a card, or null. Only one
// drag can be in progress at a time — the pointerId lets move/end handlers
// ignore any other pointer that fires while a drag is active (e.g. a second
// touch point) — but which card it's moving is per-drag, so several cards
// can each be dragged in turn without interfering with each other.
export let scoutDragState = null;

export function beginScoutDrag(e, cardEl) {
  if (!isDesktopScoutLayout()) return;
  const panelRect = els.chartPanel.getBoundingClientRect();
  const cardRect = cardEl.getBoundingClientRect();
  scoutDragState = {
    cardEl,
    pointerId: e.pointerId,
    startX: e.clientX,
    startY: e.clientY,
    startLeft: cardRect.left - panelRect.left,
    startTop: cardRect.top - panelRect.top,
    // Clamp targets, computed once at drag start rather than every move —
    // the panel doesn't resize mid-drag.
    maxLeft: Math.max(panelRect.width - cardRect.width, 0),
    maxTop: Math.max(panelRect.height - cardRect.height, 0),
  };
  // Switch from the default top/right anchor to an explicit left/top so
  // the card can move freely; keeps it exactly where it already was.
  cardEl.style.left = `${scoutDragState.startLeft}px`;
  cardEl.style.top = `${scoutDragState.startTop}px`;
  cardEl.style.right = "auto";
  cardEl.classList.add("is-dragging");
  bringScoutCardToFront(cardEl);
  e.currentTarget.setPointerCapture(e.pointerId);
}

export function onScoutDragMove(e) {
  if (!scoutDragState || e.pointerId !== scoutDragState.pointerId) return;
  const dx = e.clientX - scoutDragState.startX;
  const dy = e.clientY - scoutDragState.startY;
  const left = Math.min(Math.max(scoutDragState.startLeft + dx, 0), scoutDragState.maxLeft);
  const top = Math.min(Math.max(scoutDragState.startTop + dy, 0), scoutDragState.maxTop);
  scoutDragState.cardEl.style.left = `${left}px`;
  scoutDragState.cardEl.style.top = `${top}px`;
}

export function endScoutDrag(e) {
  if (!scoutDragState || e.pointerId !== scoutDragState.pointerId) return;
  e.currentTarget.releasePointerCapture(e.pointerId);
  scoutDragState.cardEl.classList.remove("is-dragging");
  scoutDragState = null;
}

// Edge/corner resize — pulled to expand, pushed to shrink, like a native
// window. Shared by every card type via .scout-card/.scout-card-panel, same
// as the drag/fold/cascade systems above. Width lives on the card itself;
// height lives on .scout-card-panel (the element that actually owns the
// visible box + the open/close max-height transition), so growing/shrinking
// vertically overrides that transition's cap directly instead of fighting it.
export const SCOUT_RESIZE_DIRS = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
export const SCOUT_RESIZE_MIN_HEIGHT = 160;

// `state`/`onUnfold` are the same fold-state object and callback the card's
// fold button was wired with (see toggleCardFold) — passed through so a
// pull/push on the resize handles can drive fold state too, see
// beginScoutResize/endScoutResize below.
export function attachScoutResize(cardEl, state, onUnfold) {
  SCOUT_RESIZE_DIRS.forEach((dir) => {
    const handle = document.createElement("div");
    handle.className = `scout-resize-handle scout-resize-${dir}`;
    handle.addEventListener("pointerdown", (e) => beginScoutResize(e, cardEl, dir, state, onUnfold));
    handle.addEventListener("pointermove", onScoutResizeMove);
    handle.addEventListener("pointerup", endScoutResize);
    handle.addEventListener("pointercancel", endScoutResize);
    cardEl.appendChild(handle);
  });
}

// Resize state for the one pointer currently resizing a card, or null — same
// single-gesture-at-a-time shape as scoutDragState above.
export let scoutResizeState = null;

export function beginScoutResize(e, cardEl, dir, state, onUnfold) {
  if (!isDesktopScoutLayout()) return;
  e.stopPropagation();
  e.preventDefault();
  // A folded card's body is display:none (see .is-folded in style.css), so
  // dragging its height open wouldn't reveal anything without also
  // unfolding it first — do that before measuring rects below, so the
  // gesture's start height/width reflect the now-unfolded layout instead of
  // the collapsed header-only one.
  if ((dir.includes("n") || dir.includes("s")) && state && state.folded) {
    setCardFolded(cardEl, state, false, onUnfold);
  }
  const panelEl = cardEl.querySelector(".scout-card-panel");
  const panelRect = els.chartPanel.getBoundingClientRect();
  const cardRect = cardEl.getBoundingClientRect();
  const computed = getComputedStyle(cardEl);
  const left = cardRect.left - panelRect.left;
  const top = cardRect.top - panelRect.top;
  scoutResizeState = {
    cardEl,
    panelEl,
    dir,
    state,
    onUnfold,
    pointerId: e.pointerId,
    startX: e.clientX,
    startY: e.clientY,
    startWidth: cardRect.width,
    startHeight: panelEl.getBoundingClientRect().height,
    startLeft: left,
    startTop: top,
    // Clamp targets computed once at resize start, not every move — the
    // surrounding chart panel doesn't itself resize mid-gesture.
    minWidth: parseFloat(computed.minWidth) || 260,
    maxWidth: parseFloat(computed.maxWidth) || 640,
    panelWidth: panelRect.width,
    panelHeight: panelRect.height,
  };
  // Switch from the default top/right anchor to an explicit left/top, same
  // as beginScoutDrag — growing from the north/west edge needs a fixed point
  // to grow from.
  cardEl.style.left = `${left}px`;
  cardEl.style.top = `${top}px`;
  cardEl.style.right = "auto";
  cardEl.classList.add("is-resizing");
  bringScoutCardToFront(cardEl);
  e.currentTarget.setPointerCapture(e.pointerId);
}

export function onScoutResizeMove(e) {
  const s = scoutResizeState;
  if (!s || e.pointerId !== s.pointerId) return;
  const dx = e.clientX - s.startX;
  const dy = e.clientY - s.startY;
  const dir = s.dir;

  if (dir.includes("e")) {
    const rawWidth = Math.min(Math.max(s.startWidth + dx, s.minWidth), s.maxWidth);
    const width = Math.min(rawWidth, s.panelWidth - s.startLeft);
    s.cardEl.style.width = `${width}px`;
  } else if (dir.includes("w")) {
    const rawWidth = Math.min(Math.max(s.startWidth - dx, s.minWidth), s.maxWidth);
    const left = Math.max(s.startLeft + (s.startWidth - rawWidth), 0);
    const width = s.startLeft + s.startWidth - left;
    s.cardEl.style.width = `${width}px`;
    s.cardEl.style.left = `${left}px`;
  }

  if (dir.includes("s")) {
    const rawHeight = Math.max(s.startHeight + dy, SCOUT_RESIZE_MIN_HEIGHT);
    const height = Math.min(rawHeight, s.panelHeight - s.startTop);
    s.panelEl.style.maxHeight = "none";
    s.panelEl.style.height = `${height}px`;
  } else if (dir.includes("n")) {
    const rawHeight = Math.max(s.startHeight - dy, SCOUT_RESIZE_MIN_HEIGHT);
    const top = Math.max(s.startTop + (s.startHeight - rawHeight), 0);
    const height = s.startTop + s.startHeight - top;
    s.panelEl.style.maxHeight = "none";
    s.panelEl.style.height = `${height}px`;
    s.cardEl.style.top = `${top}px`;
  }
}

export function endScoutResize(e) {
  const s = scoutResizeState;
  if (!s || e.pointerId !== s.pointerId) return;
  e.currentTarget.releasePointerCapture(e.pointerId);
  s.cardEl.classList.remove("is-resizing");
  // Pushed all the way down to the resize floor reads as "collapse this" —
  // auto-fold rather than leaving it sitting open at its smallest size, and
  // flip the fold button to match.
  if (s.state && (s.dir.includes("n") || s.dir.includes("s"))) {
    const currentHeight = parseFloat(s.panelEl.style.height);
    if (currentHeight <= SCOUT_RESIZE_MIN_HEIGHT) {
      setCardFolded(s.cardEl, s.state, true, s.onUnfold);
    }
  }
  scoutResizeState = null;
}
