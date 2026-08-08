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
import { createInfoPopover } from "./info-popover.js";
import { sortRows, makeSortableHeader } from "./table-sort.js";

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
// (.scout-card-panel) whose overflow would clip a CSS ::after popup. This is
// the hover/focus-only sibling of info-popover.js's click-toggled
// InfoPopover (used by the RSWA header below and the Players filter) —
// appropriate here since a per-row/per-cell hint doesn't need touch support
// the way a header-level trigger does. Appending straight to document.body
// sidesteps both problems above: it paints immediately on hover/focus and no
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

// Freezes the Player/Position columns (both metadata, BLUEPRINT.md's Excel
// frozen-pane treatment) in place while Games/PR Opp and the metric columns
// scroll underneath — same technique as Merge Card's applyStickyMetaColumns()
// (merge-card.js), reimplemented locally rather than imported: this module
// stays a pure leaf with no dependency on merge-card.js (see file header
// comment). Measures each metadata column's actual rendered width off the
// header row (uniform per column across every row in a <table>) so it holds
// regardless of player-name length, same reasoning as Merge Card's version.
const LINEMATE_META_COLUMN_COUNT = 2;

function applyStickyLinemateColumns(table) {
  const headerCells = table.querySelectorAll("thead th");
  if (!headerCells.length) return;

  const offsets = [];
  let left = 0;
  for (let i = 0; i < LINEMATE_META_COLUMN_COUNT && i < headerCells.length; i++) {
    offsets.push(left);
    left += headerCells[i].getBoundingClientRect().width;
  }

  table.querySelectorAll("tr").forEach((tr) => {
    offsets.forEach((offsetLeft, i) => {
      const cell = tr.children[i];
      if (!cell) return;
      cell.classList.add("linemate-table-frozen");
      cell.classList.toggle("linemate-table-frozen-edge", i === offsets.length - 1);
      cell.style.left = `${offsetLeft}px`;
    });
  });
}

// Value a roster row sorts by for a given column label — text columns
// compare case-insensitively, Games/threshold_field/metric columns
// numerically. Metric columns sort by the same percentile shown on screen
// (never the raw stat), computed fresh per row since a metric's pool/rank
// depends on that row's own position.
function linemateSortValue(t, label, cat) {
  if (label === "Player") return (t.abbr_name || t.player).toLowerCase();
  if (label === "Position") return t.position;
  if (label === "Games") return t.games ?? null;
  if (label === cat.threshold_field) return t[cat.threshold_field] ?? null;
  const meta = cat.metrics[label];
  if (meta) {
    const pool = positionPool(t.position);
    const rank = rankAndPercentile(pool, label, meta.higher_is_better, t[label]);
    return rank ? rank.percentile : null;
  }
  return null;
}

// Renders the visible slice of the roster (first 5 by snap count, or all of
// it once "See more" is toggled — the DEFAULT order and cap; sorting via a
// header click, see sortRows()/makeSortableHeader() below, reorders the same
// capped roster for display, it never re-qualifies/re-caps who's on it) into
// tableEl as a DataFrame-style table — same column style/order as Merge
// Card's (renderMergeCardBody() in merge-card.js), minus the NFL Team column
// (redundant here — every roster row already shares the anchor's team by
// construction, see computeLinemateRoster()) and minus a per-row Linemates
// toggle (recursion guard, BLUEPRINT.md §2.3: this card never lets a row
// drill into another Linemate Card). Position gets its own column instead of
// NFL Team — a roster can mix positions (LINEMATE_POSITIONS) even though it
// can't mix teams. Percentiles are each computed against the linemate's own
// position pool.
export function renderLinemateRoster(entry, roster, tableEl) {
  const cat = appliedCategoryMeta();
  tableEl.innerHTML = "";
  const sortedRoster = sortRows(roster, entry.rosterSort, (t) => linemateSortValue(t, entry.rosterSort.key, cat));
  const visibleCount = entry.seeMore ? sortedRoster.length : Math.min(LINEMATE_VISIBLE_DEFAULT, sortedRoster.length);
  const metricKeys = Object.keys(cat.metrics);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Player", "Position", "Games", cat.threshold_field, ...metricKeys].forEach((label) => {
    headRow.appendChild(
      makeSortableHeader(label, label, entry.rosterSort, () => renderLinemateRoster(entry, roster, tableEl))
    );
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  sortedRoster.slice(0, visibleCount).forEach((t) => {
    const pool = positionPool(t.position);
    const tr = document.createElement("tr");

    // Frozen status (both this cell and Position below) is applied after
    // append, by applyStickyLinemateColumns() — see the rAF call at the
    // bottom of this function.
    const nameTd = document.createElement("td");
    nameTd.className = "linemate-table-name";
    nameTd.textContent = t.abbr_name || t.player;
    tr.appendChild(nameTd);

    const positionTd = document.createElement("td");
    positionTd.className = "linemate-table-position";
    positionTd.textContent = t.position;
    tr.appendChild(positionTd);

    const gamesTd = document.createElement("td");
    gamesTd.textContent = t.games ?? "—";
    tr.appendChild(gamesTd);

    const snapsTd = document.createElement("td");
    snapsTd.textContent = t[cat.threshold_field] ?? "—";
    tr.appendChild(snapsTd);

    metricKeys.forEach((key) => {
      const meta = cat.metrics[key];
      const rank = rankAndPercentile(pool, key, meta.higher_is_better, t[key]);
      const td = document.createElement("td");
      td.className = "linemate-metric-cell";
      td.textContent = rank ? ordinal(rank.percentile) : "—";
      // Displayed text stays percentile-only, same as Merge Card; the exact
      // #rank/N is still hover-only (attachAppTooltip), since the column
      // header already labels which metric this is — nothing left for a
      // "tooltip each percentile" disclaimer to explain.
      attachAppTooltip(
        td,
        rank ? `${key}:\n#${rank.rank}/${rank.n} ${cat.positions[t.position] || t.position}` : key
      );
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });

  tableEl.appendChild(thead);
  tableEl.appendChild(tbody);

  // On first build (openLinemateCard() calls this before appending cardEl to
  // the DOM), tableEl isn't connected yet — column widths aren't measurable
  // until a frame after that append lands, same reasoning as Merge Card's
  // own deferred applyStickyMetaColumns() call. Every other caller (See
  // more/unfold refreshes, and card-export.js's prepareClone rebuilding this
  // table inside an *already-attached* off-screen export clone) has tableEl
  // connected already, so measuring synchronously here — rather than always
  // deferring — matters: card-export.js calls html2canvas right after
  // prepareClone returns, with no frame in between for a deferred rAF to
  // fire, so a rebuild that ran through the connected branch is the only way
  // an export's roster table keeps its frozen columns.
  if (tableEl.isConnected) {
    applyStickyLinemateColumns(tableEl);
  } else {
    requestAnimationFrame(() => applyStickyLinemateColumns(tableEl));
  }
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
  const tableEl = cardEl.querySelector(".linemate-table");
  const seeMoreBtn = cardEl.querySelector(".linemate-see-more");
  const summaryTable = cardEl.querySelector(".linemate-summary-table");

  entry.roster = computeLinemateRoster(entry.anchorRecord);
  const roster = entry.roster;

  titleEl.textContent = `${entry.anchorRecord.player} Linemates`; // season now lives on .linemate-card-meta, set once at open
  // The roster-size/threshold sentence sits on its own line above the "All
  // numbers are..." disclaimer, rather than behind a hover-only info icon.
  const rosterNoteEl = cardEl.querySelector(".linemate-card-roster-note");
  rosterNoteEl.textContent = `${roster.length} linemate${roster.length === 1 ? "" : "s"} with ≥ ${appliedFilters.threshold} ${thresholdFieldLabel(cat)}.`;

  // A refresh that shrinks the roster to <= the default visible count
  // resets "See more" back to collapsed — there's nothing left to hide, so
  // a lingering "See less" state would just be confusing.
  if (roster.length <= LINEMATE_VISIBLE_DEFAULT) entry.seeMore = false;
  renderLinemateRoster(entry, roster, tableEl);
  seeMoreBtn.hidden = roster.length <= LINEMATE_VISIBLE_DEFAULT;
  seeMoreBtn.textContent = entry.seeMore ? "See less" : "See more";

  // 3M + RSWA summary, computed over every qualifying (capped) linemate
  // regardless of "See more" state.
  renderLinemateSummary(entry, roster, summaryTable);
}

// Value a Line Summary row sorts by for a given column label — "Metric"
// compares case-insensitively on the metric's own name, the four stat
// columns compare numerically on the same rounded percentile shown on
// screen.
function summarySortValue(row, label) {
  if (label === "Metric") return row.key.toLowerCase();
  if (label === "Min") return row.min;
  if (label === "Median") return row.median;
  if (label === "RSWA") return row.rswa;
  if (label === "Max") return row.max;
  return null;
}

// Renders the Line Summary table (Min/Median/RSWA/Max per metric) from
// `roster` — always the full capped roster regardless of "See more" state,
// see computeThreeMRSWA()'s own header comment. Extracted from
// renderLinemateCardBody() so a header click can re-run just this table
// (sortRows()/makeSortableHeader(), same pattern as renderLinemateRoster()
// above) without recomputing the roster table too.
export function renderLinemateSummary(entry, roster, summaryTable) {
  const cat = appliedCategoryMeta();
  const summary = computeThreeMRSWA(roster, cat);
  const summaryRows = Object.keys(cat.metrics).map((key) => ({ key, ...summary[key] }));
  const sortedRows = sortRows(summaryRows, entry.summarySort, (row) =>
    summarySortValue(row, entry.summarySort.key)
  );

  summaryTable.innerHTML = "";
  const RSWA_TOOLTIP =
    "Relative Snaps Weighted Average — each linemate's percentile weighted by his own " +
    `share of roster's total ${thresholdFieldLabel(cat)} (weight = his snaps ÷ the filtered roster's ` +
    "total snaps), so a linemate who played more counts for more of line summary.";
  const theadRow = document.createElement("tr");
  ["Metric", "Min", "Median", "RSWA", "Max"].forEach((label) => {
    const th = makeSortableHeader(label, label, entry.summarySort, () =>
      renderLinemateSummary(entry, roster, summaryTable)
    );
    if (label === "RSWA") {
      // Shared InfoPopover (same component as the Players filter header) —
      // click-toggled rather than attachAppTooltip's hover/focus, and its
      // own click-outside handler dismisses it regardless of
      // .linemate-summary-wrap's overflow-x:auto, unlike a hover popup which
      // would need to survive inside that scroll clip. stopPropagation()
      // inside info-popover.js's own click handler keeps this from also
      // toggling the header's sort. Swaps out makeSortableHeader()'s plain
      // "RSWA" text span for the InfoPopover trigger itself (label text +
      // icon in one bordered button) rather than appending the trigger
      // alongside it — a bare icon floating next to separately-styled plain
      // text isn't one clickable unit. The sort-indicator arrow (added after
      // this by makeSortableHeader when the column is the active sort) is
      // untouched, so clicking it still sorts.
      const plainLabel = th.querySelector("span:not(.sort-indicator)");
      th.replaceChild(
        createInfoPopover(RSWA_TOOLTIP, { ariaLabel: `RSWA: ${RSWA_TOOLTIP}`, label: "RSWA" }),
        plainLabel
      );
    }
    theadRow.appendChild(th);
  });
  const thead = document.createElement("thead");
  thead.appendChild(theadRow);

  const tbody = document.createElement("tbody");
  sortedRows.forEach((row) => {
    const tr = document.createElement("tr");
    const labelTd = document.createElement("td");
    labelTd.className = "linemate-summary-metric";
    labelTd.textContent = row.key;
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
  const tableEl = cardEl.querySelector(".linemate-table");
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
    // Excel-style click-to-sort state for the roster and Line Summary
    // tables (table-sort.js) — independent of each other and of seeMore,
    // and persists across a threshold-only refresh the same way seeMore
    // does (renderLinemateCardBody() never resets either).
    rosterSort: { key: null, dir: "asc" },
    summarySort: { key: null, dir: "asc" },
  };

  // Wired once — reads entry.roster/entry.seeMore fresh on every click, so
  // it keeps working correctly across renderLinemateCardBody() refreshes
  // without needing to be re-attached.
  seeMoreBtn.addEventListener("click", () => {
    entry.seeMore = !entry.seeMore;
    seeMoreBtn.textContent = entry.seeMore ? "See less" : "See more";
    renderLinemateRoster(entry, entry.roster, tableEl);
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
    renderLinemateRoster(entry, entry.roster, tableEl);
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
      const cloneTableEl = clone.querySelector(".linemate-table");
      // Carries the live card's current sort along into the export (its own
      // { key, dir } object, not a fresh one) rather than resetting it — the
      // export should look exactly like what's on screen, just unfolded.
      if (cloneTableEl) {
        renderLinemateRoster({ seeMore: true, rosterSort: entry.rosterSort }, entry.roster, cloneTableEl);
        // renderLinemateRoster() wipes and rebuilds every cell, which re-adds
        // .linemate-table-frozen (position:sticky) via applyStickyLinemateColumns()
        // — undoing buildExportClone()'s static-position fix, which only ever
        // touched the pre-rebuild cells it can no longer see. Re-apply it here
        // to the freshly built ones, or the Player/Position columns drift to
        // the row's right edge in the exported PNG (same failure mode
        // buildExportClone's own fix exists to prevent).
        cloneTableEl.querySelectorAll(".linemate-table-frozen").forEach((cell) => {
          cell.style.position = "static";
          cell.style.left = "";
        });
      }
    }
  );

  linemateCards.set(anchorRecord.player, entry);
  updateScoutEmptyHint();
}
