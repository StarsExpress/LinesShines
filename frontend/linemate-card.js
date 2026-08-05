/* Linemate Association Cards — pure leaf among the three card types: no
 * dependency on scout-card.js or merge-card.js (this is what makes the
 * recursion guard in openLinemateCard()/attachAppTooltip() etc. trivial — a
 * Linemate Card renders no linemate toggle of its own). Also owns the small
 * hover-tooltip helpers (showAppTooltip/hideAppTooltip/attachAppTooltip),
 * whose only consumer in the original app.js was this section.
 * Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3 step 5 — done
 * before scout-card.js/merge-card.js since nothing depends on it in return,
 * the lowest-risk way to validate cards-base.js's boundary.
 */
import { els } from "./dom.js";
import {
  appliedCategoryMeta,
  appliedFilters,
  currentRecords,
  positionPool,
  rankAndPercentile,
  median,
  thresholdFieldLabel,
  logoSrc,
  teamColor,
  teamName,
} from "./data.js";
import { LINEMATE_POSITIONS, LINEMATE_CAP, LINEMATE_VISIBLE_DEFAULT } from "./config.js";
import {
  isDesktopScoutLayout,
  ordinal,
  nextCardId,
  cascadeScoutCardPosition,
  bringScoutCardToFront,
  attachScoutResize,
  toggleCardFold,
  beginScoutDrag,
  onScoutDragMove,
  endScoutDrag,
  updateScoutEmptyHint,
} from "./cards-base.js";
import { attachCardSave, sanitizeForFilename } from "./card-export.js";

// Open Linemate Association Cards, keyed by the anchor's player string — one
// per anchor regardless of whether the toggle that opened it lives on a
// Player Card or a Merge Card member row. This is what makes BLUEPRINT.md
// §2.3's recursion guard trivial: a Linemate Card never renders a linemate
// toggle of its own, so there's no second layer of anchors to key around.
// Entry: { id, origin:'linemate', anchorKey, anchorRecord, roster, el,
// folded, seeMore }. anchorRecord/roster are read and overwritten by
// renderLinemateCardBody() on every open/refresh — see refreshOpenLinemateCards().
export const linemateCards = new Map();

// Closes every Linemate Card — only for a season/category/position change
// (BLUEPRINT.md §4). A threshold-only change no longer dissolves them; see
// refreshOpenLinemateCards(), called from applyFilters() instead.
export function clearLinemateCards() {
  linemateCards.forEach((entry) => entry.el.remove());
  linemateCards.clear();
  updateScoutEmptyHint();
}

// Small, reliable hover/focus tooltip for elements where the native `title`
// attribute isn't good enough — either the trigger is small (a percentile
// badge, an info icon) so the browser's dwell-time-before-showing makes it
// feel broken, or the trigger lives inside a scrolling ancestor
// (.linemate-summary-wrap, .scout-card-panel) whose overflow would clip a
// CSS ::after popup the way .info-hint uses elsewhere. Appending straight to
// document.body sidesteps both: it paints immediately on hover/focus and no
// ancestor's overflow can clip it. `title` is still set alongside this as a
// plain-text fallback for screen readers and no-hover touch devices.
let appTooltipEl = null;

export function showAppTooltip(triggerEl, text) {
  hideAppTooltip();
  const tip = document.createElement("div");
  tip.className = "app-tooltip";
  tip.textContent = text;
  document.body.appendChild(tip);

  const triggerRect = triggerEl.getBoundingClientRect();
  const tipRect = tip.getBoundingClientRect();
  const left = Math.min(
    Math.max(triggerRect.left + triggerRect.width / 2 - tipRect.width / 2, 8),
    window.innerWidth - tipRect.width - 8
  );
  const above = triggerRect.top - tipRect.height - 8;
  const top = above >= 8 ? above : triggerRect.bottom + 8;
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
  appTooltipEl = tip;
}

export function hideAppTooltip() {
  if (appTooltipEl) {
    appTooltipEl.remove();
    appTooltipEl = null;
  }
}

export function attachAppTooltip(el, text) {
  el.title = text;
  el.addEventListener("mouseenter", () => showAppTooltip(el, text));
  el.addEventListener("mouseleave", hideAppTooltip);
  el.addEventListener("focus", () => showAppTooltip(el, text));
  el.addEventListener("blur", hideAppTooltip);
}

// --- Linemate Association Cards (BLUEPRINT.md §2) ---------------------------

// Same-team, same-season, same-category roster around `anchorRecord`,
// including same-position linemates (BLUEPRINT.md §2.2's position table),
// excluding the anchor himself and anyone below the applied snap threshold,
// then sorts by snap count (the category's threshold_field, the only volume
// stat available per player) descending and caps at the category's limit —
// dropping the lowest first, no positional reservation.
export function computeLinemateRoster(anchorRecord) {
  const cat = appliedCategoryMeta();
  const positions = LINEMATE_POSITIONS[appliedFilters.category];
  const threshold = Number(appliedFilters.threshold);

  const qualifying = currentRecords.filter(
    (r) =>
      positions.includes(r.position) &&
      r.team === anchorRecord.team &&
      r.player !== anchorRecord.player &&
      r[cat.threshold_field] >= threshold
  );

  const sorted = qualifying.slice().sort((a, b) => b[cat.threshold_field] - a[cat.threshold_field]);
  const cap = LINEMATE_CAP[appliedFilters.category];

  return sorted.slice(0, cap);
}

// Min/Median/RSWA/Max per metric over `rosterRecords` — always the full
// capped roster, regardless of "See more" state (BLUEPRINT.md §2.5: that
// control is display-only). RSWA (Relative Snaps Weighted Average) weights
// each linemate's percentile by his own share of the roster's total snaps —
// weight[t] = snaps[t] / sum(snaps) — exactly the formula in BLUEPRINT.md
// §2.5, so a linemate who played more snaps alongside the anchor's unit
// counts for more of the summary.
export function computeThreeMRSWA(rosterRecords, cat) {
  const perPlayer = rosterRecords.map((t) => {
    const pool = positionPool(t.position);
    const percentiles = {};
    Object.entries(cat.metrics).forEach(([key, meta]) => {
      const rank = rankAndPercentile(pool, key, meta.higher_is_better, t[key]);
      percentiles[key] = rank ? rank.percentile : null;
    });
    return { percentiles, snaps: t[cat.threshold_field] || 0 };
  });

  const totalSnaps = perPlayer.reduce((sum, p) => sum + p.snaps, 0);

  const results = {};
  Object.keys(cat.metrics).forEach((key) => {
    const values = perPlayer.map((p) => p.percentiles[key]).filter((v) => v != null);
    let rswa = null;
    if (totalSnaps > 0) {
      rswa = perPlayer.reduce((sum, p) => sum + (p.percentiles[key] ?? 0) * (p.snaps / totalSnaps), 0);
      rswa = Math.round(rswa * 10) / 10;
    }
    results[key] = {
      min: values.length ? Math.min(...values) : null,
      median: median(values),
      max: values.length ? Math.max(...values) : null,
      rswa,
    };
  });
  return results;
}

export function toggleLinemateCard(anchorRecord) {
  if (!isDesktopScoutLayout()) return;
  if (linemateCards.has(anchorRecord.player)) {
    closeLinemateCard(anchorRecord.player);
  } else {
    openLinemateCard(anchorRecord);
  }
}

export function closeLinemateCard(anchorKey) {
  const entry = linemateCards.get(anchorKey);
  if (!entry) return;
  entry.el.remove();
  linemateCards.delete(anchorKey);
  updateScoutEmptyHint();
}

// Renders the visible slice of the roster (first 5 by snap count, or all of
// it once "See more" is toggled) into listEl — percentiles only, each
// against the linemate's own position pool, with the pool denominator shown
// per BLUEPRINT.md §2.4.
export function renderLinemateRoster(entry, roster, listEl) {
  const cat = appliedCategoryMeta();
  listEl.innerHTML = "";
  const visibleCount = entry.seeMore ? roster.length : Math.min(LINEMATE_VISIBLE_DEFAULT, roster.length);

  roster.slice(0, visibleCount).forEach((t) => {
    const pool = positionPool(t.position);
    const row = document.createElement("div");
    row.className = "linemate-row";

    const nameWrap = document.createElement("div");
    nameWrap.className = "linemate-row-name-wrap";

    const name = document.createElement("span");
    name.className = "linemate-row-name";
    name.textContent = `${t.position} — ${t.abbr_name || t.player}`;
    nameWrap.appendChild(name);

    // Same fa-circle-info + attachAppTooltip pattern as the card title hint
    // and the summary table's RSWA header hint — not the CSS-only
    // .info-hint::after popup the Players filter uses, since that would get
    // clipped by this list's own scrolling ancestor.
    const snapsHint = document.createElement("i");
    snapsHint.className = "fa-solid fa-circle-info linemate-row-hint";
    const snapsText = `${t[cat.threshold_field]} ${thresholdFieldLabel(cat)}.`;
    snapsHint.setAttribute("aria-label", snapsText);
    attachAppTooltip(snapsHint, snapsText);
    nameWrap.appendChild(snapsHint);

    row.appendChild(nameWrap);

    const cellsWrap = document.createElement("div");
    cellsWrap.className = "linemate-row-cells";
    Object.entries(cat.metrics).forEach(([key, meta]) => {
      const rank = rankAndPercentile(pool, key, meta.higher_is_better, t[key]);
      const cell = document.createElement("span");
      cell.className = "linemate-cell";
      cell.textContent = rank ? ordinal(rank.percentile) : "—";
      attachAppTooltip(
        cell,
        rank ? `${key}:\n#${rank.rank}/${rank.n} ${cat.positions[t.position] || t.position}` : key
      );
      cellsWrap.appendChild(cell);
    });
    row.appendChild(cellsWrap);

    listEl.appendChild(row);
  });
}

// Fully rebuilds a Linemate Card's title tooltip, roster, and Line Summary
// table from entry.anchorRecord's current team/position/category/threshold —
// used both to build a freshly opened card and to refresh an already-open
// one after a threshold-only Apply (which doesn't dissolve Linemate Cards,
// only a season/category/position change does — see applyFilters()). A
// threshold change moves who qualifies, so a card left showing the old
// roster/percentiles would be silently wrong, not just stale display.
export function renderLinemateCardBody(entry) {
  const cat = appliedCategoryMeta();
  const cardEl = entry.el;
  const titleEl = cardEl.querySelector(".linemate-card-title");
  const listEl = cardEl.querySelector(".linemate-roster");
  const seeMoreBtn = cardEl.querySelector(".linemate-see-more");
  const summaryTable = cardEl.querySelector(".linemate-summary-table");

  entry.roster = computeLinemateRoster(entry.anchorRecord);
  const roster = entry.roster;

  titleEl.textContent = `${entry.anchorRecord.player} Linemates`; // season now lives on .linemate-card-meta, set once at open
  // The roster-size/threshold sentence used to sit on its own line under the
  // title; it's now a tooltip on this icon instead, freeing that line for
  // the "All numbers are..." disclaimer and the "Tooltip each percentile..."
  // hint below it.
  const rosterSummary = `${roster.length} linemate${roster.length === 1 ? "" : "s"} ≥ ${appliedFilters.threshold} ${thresholdFieldLabel(cat)}.`;
  const titleHint = document.createElement("i");
  titleHint.className = "fa-solid fa-circle-info linemate-card-title-hint";
  titleHint.setAttribute("aria-label", rosterSummary);
  attachAppTooltip(titleHint, rosterSummary);
  titleEl.appendChild(titleHint);

  // A refresh that shrinks the roster to <= the default visible count
  // resets "See more" back to collapsed — there's nothing left to hide, so
  // a lingering "See less" state would just be confusing.
  if (roster.length <= LINEMATE_VISIBLE_DEFAULT) entry.seeMore = false;
  renderLinemateRoster(entry, roster, listEl);
  seeMoreBtn.hidden = roster.length <= LINEMATE_VISIBLE_DEFAULT;
  seeMoreBtn.textContent = entry.seeMore ? "See less" : "See more";

  // 3M + RSWA summary, computed over every qualifying (capped) linemate
  // regardless of "See more" state.
  const summary = computeThreeMRSWA(roster, cat);
  summaryTable.innerHTML = "";
  const theadRow = document.createElement("tr");
  const RSWA_TOOLTIP =
    "Relative Snaps Weighted Average — each linemate's percentile weighted by his own " +
    `share of roster's total ${thresholdFieldLabel(cat)} (weight = his snaps ÷ the filtered roster's ` +
    "total snaps), so a linemate who played more counts for more of line summary.";
  [
    { label: "Metric" },
    { label: "Min" },
    { label: "Median" },
    { label: "RSWA", title: RSWA_TOOLTIP },
    { label: "Max" },
  ].forEach(({ label, title }) => {
    const th = document.createElement("th");
    th.appendChild(document.createTextNode(label));
    if (title) {
      // A plain `title` on the <th> alone is easy to miss — nothing next to
      // the text signals it's hoverable. The icon is the visible affordance;
      // attachAppTooltip() (not the native title's dwell-time popup, and not
      // the app's usual .info-hint ::after) is what actually shows the
      // explanation, since .linemate-summary-wrap scrolls with
      // overflow-x:auto and would otherwise clip it.
      const hint = document.createElement("i");
      hint.className = "fa-solid fa-circle-info linemate-summary-hint";
      hint.setAttribute("aria-label", title);
      attachAppTooltip(hint, title);
      th.appendChild(hint);
    }
    theadRow.appendChild(th);
  });
  const thead = document.createElement("thead");
  thead.appendChild(theadRow);

  const tbody = document.createElement("tbody");
  Object.keys(cat.metrics).forEach((key) => {
    const row = summary[key];
    const tr = document.createElement("tr");
    const labelTd = document.createElement("td");
    labelTd.className = "linemate-summary-metric";
    labelTd.textContent = key;
    tr.appendChild(labelTd);
    [row.min, row.median, row.rswa, row.max].forEach((v) => {
      const td = document.createElement("td");
      td.textContent = v == null ? "—" : ordinal(Math.round(v));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  summaryTable.appendChild(thead);
  summaryTable.appendChild(tbody);
}

// Re-renders every open Linemate Card in place against the current
// threshold/category/season — called after every render() in applyFilters()
// alongside refreshOpenScoutCards(). Safe to call unconditionally: if a
// slice change dissolved every card first, this is just an empty loop.
export function refreshOpenLinemateCards() {
  linemateCards.forEach((entry) => renderLinemateCardBody(entry));
}

export function openLinemateCard(anchorRecord) {
  const cardEl = els.linemateCardTemplate.content.firstElementChild.cloneNode(true);

  const closeBtn = cardEl.querySelector(".scout-close");
  const foldBtn = cardEl.querySelector(".scout-fold");
  const dragHandle = cardEl.querySelector(".scout-drag-handle");
  const listEl = cardEl.querySelector(".linemate-roster");
  const seeMoreBtn = cardEl.querySelector(".linemate-see-more");
  const logoImg = cardEl.querySelector(".scout-logo");
  const badge = cardEl.querySelector(".scout-badge");
  const metaEl = cardEl.querySelector(".linemate-card-meta");

  // Team/season are fixed for this card's lifetime (a season/category/
  // position change dissolves every Linemate Card — see clearLinemateCards()
  // — so unlike the title, this never needs to be re-set by
  // renderLinemateCardBody()'s refresh path). Mirrors openScoutCard()'s own
  // logo/badge wiring.
  const color = teamColor(anchorRecord.team);
  logoImg.src = logoSrc(anchorRecord.team);
  logoImg.alt = `${anchorRecord.team} logo`;
  logoImg.hidden = false;
  badge.hidden = true;
  logoImg.onerror = () => {
    logoImg.hidden = true;
    badge.hidden = false;
    badge.textContent = anchorRecord.team;
    badge.style.background = color;
  };
  metaEl.textContent = `${teamName(anchorRecord.team)} · ${appliedFilters.season}`;

  const id = nextCardId();
  const entry = {
    id,
    origin: "linemate",
    anchorKey: anchorRecord.player,
    anchorRecord,
    roster: [],
    el: cardEl,
    folded: false,
    seeMore: false,
  };

  // Wired once — reads entry.roster/entry.seeMore fresh on every click, so
  // it keeps working correctly across renderLinemateCardBody() refreshes
  // without needing to be re-attached.
  seeMoreBtn.addEventListener("click", () => {
    entry.seeMore = !entry.seeMore;
    seeMoreBtn.textContent = entry.seeMore ? "See less" : "See more";
    renderLinemateRoster(entry, entry.roster, listEl);
  });

  renderLinemateCardBody(entry);

  els.scoutCards.appendChild(cardEl);
  cascadeScoutCardPosition(cardEl); // must run before linemateCards.set() below
  cardEl.classList.add("is-active");
  bringScoutCardToFront(cardEl);

  // Shared by the fold button and the resize-driven auto-unfold (see
  // beginScoutResize) so both paths reset "See more" the same way.
  const onUnfold = () => {
    entry.seeMore = false;
    seeMoreBtn.textContent = "See more";
    renderLinemateRoster(entry, entry.roster, listEl);
  };
  attachScoutResize(cardEl, entry, onUnfold);

  closeBtn.addEventListener("click", () => closeLinemateCard(anchorRecord.player));
  foldBtn.addEventListener("click", () => toggleCardFold(cardEl, entry, onUnfold));
  dragHandle.addEventListener("pointerdown", (e) => beginScoutDrag(e, cardEl));
  dragHandle.addEventListener("pointermove", onScoutDragMove);
  dragHandle.addEventListener("pointerup", endScoutDrag);
  dragHandle.addEventListener("pointercancel", endScoutDrag);
  cardEl.addEventListener("pointerdown", () => bringScoutCardToFront(cardEl));
  attachCardSave(
    cardEl,
    () => `LinesShines_${sanitizeForFilename(anchorRecord.player)}_Linemates_${appliedFilters.season}`,
    // "See more" only ever renders roster.slice(0, visibleCount) into the DOM
    // in the first place (see renderLinemateRoster) — a collapsed roster's
    // hidden rows don't exist for html2canvas to reveal via CSS. Re-render
    // straight into the clone's own roster element with seeMore forced on,
    // same entry.roster the live card already computed, so the export always
    // shows the full capped roster regardless of the on-screen toggle state.
    (clone) => {
      const cloneListEl = clone.querySelector(".linemate-roster");
      if (cloneListEl) renderLinemateRoster({ seeMore: true }, entry.roster, cloneListEl);
    }
  );

  linemateCards.set(anchorRecord.player, entry);
  updateScoutEmptyHint();
}
