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
  teamLabel,
  metadata,
  appliedThreshold,
  thresholdPhrase,
} from "./data.js";
import { meetsThreshold } from "./pinned-impact.js";
import { LINEMATE_POSITIONS, LINEMATE_SIZE_REMINDER_AT } from "./config.js";
import {
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
import { categoryAppendixNotes } from "./metric-notes.js";
import { createInfoPopover } from "./info-popover.js";
import { TABLE_MODE_READ, buildPlayerTableModel, readLayout } from "./player-table-model.js";
import { placePopup } from "./popup-position.js";
import { sortRows, makeSortableHeader } from "./table-sort.js";

// Open Linemate Association Cards, keyed by the anchor's player string — one
// per anchor regardless of whether the toggle that opened it lives on a
// Player Card or a Merge Card member row. This is what makes the recursion guard
// trivial: a Linemate Card never renders a linemate
// toggle of its own, so there's no second layer of anchors to key around.
// Entry: { id, origin:'linemate', anchorKey, anchorRecord, roster, el,
// folded, includeAnchor }. anchorRecord/roster are read and
// overwritten by renderLinemateCardBody() on every open/refresh — see
// refreshOpenLinemateCards(). includeAnchor (default false, toggled by the
// card's own "Include anchor player" checkbox) persists across a refresh the
// same way rosterSort/summarySort do — renderLinemateCardBody()
// only ever reads it, never resets it.
export const linemateCards = new Map();

// Closes every Linemate Card — for a slice change that resets the Workspace
// (see applyFilters()). A threshold-only change, or a season change that
// pinned-impact.js judges "refresh", keeps them: they are re-pointed
// (retargetLinemateCard()) and recomputed by refreshOpenLinemateCards().
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

  placePopup(triggerEl, tip, { align: "center" });
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

// --- Linemate Association Cards ---------------------------

// Same-team, same-season, same-category roster around `anchorRecord`,
// including same-position linemates,
// excluding the anchor himself and anyone below the applied snap threshold,
// then sorts by snap count (the category's threshold_field, the only volume
// stat available per player) descending. No size limit: the threshold is the
// only gate, and every qualifying player is on the card.
export function computeLinemateRoster(anchorRecord) {
  const cat = appliedCategoryMeta();
  const positions = LINEMATE_POSITIONS[appliedFilters.category];
  const threshold = appliedThreshold();

  const qualifying = currentRecords.filter(
    (r) =>
      positions.includes(r.position) &&
      r.team === anchorRecord.team &&
      r.player !== anchorRecord.player &&
      meetsThreshold(r, cat.threshold_field, threshold)
  );

  return qualifying.slice().sort((a, b) => b[cat.threshold_field] - a[cat.threshold_field]);
}

// Rows actually shown/summarized — computeLinemateRoster()'s cap/threshold
// logic never sees the anchor (entry.roster stays teammates-only always, so
// the OL/DL cap is never affected by this toggle); this just inserts the
// anchor's own record into its rank position by the category's own
// threshold_field (snap count) when the card's "Include {player} into
// tables" checkbox is on — entry.roster is already sorted descending by
// that same field (see computeLinemateRoster()), so everyone (anchor
// included) reads as one snap-ranked line, not the anchor pinned to a fixed
// slot regardless of how many snaps he played. This is only the *default*
// order — a header click still re-sorts by whatever column via
// entry.rosterSort, same as any other row. Every render call site below
// reads through this rather than entry.roster directly, so the roster
// table, the Line Summary (via computeThreeMRSWA, which is otherwise
// anchor-agnostic — it just summarizes whatever records it's given), and
// the PNG export all pick up the anchor consistently with zero
// special-casing anywhere else.
function linemateDisplayRoster(entry) {
  if (!entry.includeAnchor) return entry.roster;

  const field = appliedCategoryMeta().threshold_field;
  const anchorValue = entry.anchorRecord[field] ?? 0;
  // roster is sorted descending by `field` already — insert just before the
  // first teammate whose value is strictly lower than the anchor's, so a
  // tie keeps the existing teammates-first order rather than jumping ahead.
  const insertAt = entry.roster.findIndex((t) => (t[field] ?? 0) < anchorValue);

  const combined = entry.roster.slice();
  if (insertAt === -1) combined.push(entry.anchorRecord);
  else combined.splice(insertAt, 0, entry.anchorRecord);
  return combined;
}

// The metrics the Line Summary covers: all of them except those flagged
// `line_summary: false` (Pass Cov Percent). A line mixes ED and DI, and their
// coverage shares sit in very different ranges, so a single Min/Median/Max/
// RSWA for it would compare them unfairly. The roster table still shows each
// player's own percentile among his position.
function summaryMetricEntries(cat) {
  return Object.entries(cat.metrics).filter(([, meta]) => meta.line_summary !== false);
}

// Min/Median/RSWA/Max per metric over `rosterRecords` — every player on the
// card. RSWA (Relative Snaps Weighted Average) weights
// each linemate's percentile by his own share of the roster's total snaps —
// weight[t] = snaps[t] / sum(snaps) — so a linemate who played more snaps alongside the anchor's unit
// counts for more of the summary.
export function computeThreeMRSWA(rosterRecords, cat) {
  const perPlayer = rosterRecords.map((t) => {
    const pool = positionPool(t.position);
    const percentiles = {};
    summaryMetricEntries(cat).forEach(([key, meta]) => {
      const rank = rankAndPercentile(pool, key, meta.higher_is_better, t[key]);
      percentiles[key] = rank ? rank.percentile : null;
    });
    return { percentiles, snaps: t[cat.threshold_field] || 0 };
  });

  const totalSnaps = perPlayer.reduce((sum, p) => sum + p.snaps, 0);

  const results = {};
  summaryMetricEntries(cat).forEach(([key]) => {
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

// No longer desktop/tablet-gated (originally scoped this
// alongside Merge Cards) — a Linemate Card is just another scrollable
// stats table, not a scatter plot, so it doesn't need the wide layout Merge
// Cards/Pinned Players still do. Dragging/cascading on the opened card still
// stay desktop-only: cascadeScoutCardPosition()/beginScoutDrag() (imported
// from cards-base.js, used below in openLinemateCard()) each self-guard on
// their own isDesktopScoutLayout() check, so nothing extra is needed here.
// Opens (or brings forward) a teammate's own Player Card from the "Card"
// button in each roster row. Injected by scout-card.js through
// setPlayerCardOpener() rather than imported, because scout-card.js already
// imports this module — importing it back would make a cycle and break this
// module's "pure leaf" rule (see the file header).
let openPlayerCard = null;

export function setPlayerCardOpener(fn) {
  openPlayerCard = fn;
}

export function toggleLinemateCard(anchorRecord) {
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

// Freezes the Player/Card/Position columns (all metadata, an Excel-style
// frozen-pane treatment) in place while Games/PR Opp and the metric columns
// scroll underneath — same technique as Merge Card's applyStickyMetaColumns()
// (merge-card.js), reimplemented locally rather than imported: this module
// stays a pure leaf with no dependency on merge-card.js (see file header
// comment). Measures each metadata column's actual rendered width off the
// header row (uniform per column across every row in a <table>) so it holds
// regardless of player-name length, same reasoning as Merge Card's version.
const LINEMATE_META_COLUMN_COUNT = 3;

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

// Percentile color coding (six bins) for the roster table's metric cells —
// same bins/colors/inset-chip treatment as Merge Card's percentileFillClass()
// (merge-card.js), reimplemented locally per this file's own leaf-module
// header comment rather than importing from merge-card.js. Reuses that same
// file's .merge-pct-chip/.merge-pct-* CSS classes directly (not a parallel
// linemate-prefixed copy) — same component, same visual language, only the
// JS mapping function is duplicated, mirroring how .sortable-th/.sort-arrow
// are already one shared CSS component across both card types. Deliberately
// NOT used for the Line Summary table below (Min/Median/RSWA/Max are order
// statistics across the roster, not an individual's performance grade — the
// same bins would just encode Min's structural bias toward low values and
// Max's toward high values, not real signal).
function percentileFillClass(percentile) {
  if (percentile < 35) return "merge-pct-red";
  if (percentile < 50) return "merge-pct-orange";
  if (percentile < 65) return "merge-pct-yellow";
  if (percentile < 75) return "merge-pct-lightblue";
  if (percentile < 90) return "merge-pct-darkblue";
  return "merge-pct-violet";
}

// Renders the whole roster (the DEFAULT order is snap count descending; sorting
// via a header click, see sortRows()/makeSortableHeader() below, reorders the
// same roster for display, it never changes who's on it) into
// tableEl as a DataFrame-style table — same column style/order as Merge
// Card's (renderMergeCardBody() in merge-card.js), minus the NFL Team column
// (redundant here — every roster row already shares the anchor's team by
// construction, see computeLinemateRoster()) and minus a per-row Linemates
// toggle (recursion guard: this card never lets a row
// drill into another Linemate Card; its per-row "Card" button opens that
// player's Player Card instead). Position gets its own column instead of
// NFL Team — a roster can mix positions (LINEMATE_POSITIONS) even though it
// can't mix teams. Percentiles are each computed against the linemate's own
// position pool.
// Header of the column that holds each row's "open this player's card" button.
const PLAYER_CARD_COLUMN = "Card";

// One roster cell, built the same way in both layouts. `column.kind` is one of
// name, position, card, games, snaps or metric (player-table-model.js).
function makeRosterCell(t, column, cat) {
  const td = document.createElement("td");

  if (column.kind === "name") {
    td.className = "linemate-table-name";
    td.textContent = t.abbr_name || t.player;
  } else if (column.kind === "position") {
    td.className = "linemate-table-position";
    td.textContent = t.position;
  } else if (column.kind === "card") {
    td.className = "linemate-table-card";
    const cardBtn = document.createElement("button");
    cardBtn.type = "button";
    cardBtn.className = "linemate-row-card-btn";
    cardBtn.innerHTML = '<i class="fa-solid fa-id-card"></i>';
    cardBtn.setAttribute("aria-label", `Open ${t.player}'s card`);
    cardBtn.title = `Open ${t.abbr_name || t.player}'s card`;
    cardBtn.addEventListener("click", () => {
      if (openPlayerCard) openPlayerCard(t);
    });
    td.appendChild(cardBtn);
  } else if (column.kind === "games") {
    td.textContent = t.games ?? "—";
  } else if (column.kind === "snaps") {
    td.textContent = t[cat.threshold_field] ?? "—";
  } else {
    const key = column.key;
    const meta = cat.metrics[key];
    const rank = rankAndPercentile(positionPool(t.position), key, meta.higher_is_better, t[key]);
    td.className = "linemate-metric-cell";
    if (rank) {
      const chip = document.createElement("span");
      chip.className = `merge-pct-chip ${meta.neutral === true ? "merge-pct-neutral" : percentileFillClass(rank.percentile)}`;
      chip.textContent = ordinal(rank.percentile);
      td.appendChild(chip);
    } else {
      td.textContent = "—";
    }
    // Displayed text stays percentile-only, same as Merge Card; the exact
    // #rank/N is still hover-only (attachAppTooltip), since the column
    // header already labels which metric this is — nothing left for a
    // "tooltip each percentile" disclaimer to explain.
    attachAppTooltip(td, rank ? `${key}:\n#${rank.rank}/${rank.n} ${cat.positions[t.position] || t.position}` : key);
  }
  return td;
}

// The Read layout's per-player head cells: name, position and the "Card" button.
const READ_IDENTITY_COLUMNS = [
  { key: "Player", kind: "name" },
  { key: "Position", kind: "position" },
  { key: PLAYER_CARD_COLUMN, kind: "card" },
];

// Read layout: players as columns, metrics as rows, grouped under Metadata /
// Required Metrics / Bonus Metrics headings like the Comparison Card's Read. The
// head block (name, position, Card button) is pinned at the top by CSS
// (.merge-read-frozen) while the rows scroll vertically with the card's panel;
// the card is sized to fit this table, so nothing scrolls sideways or freezes.
function renderLinemateReadTable(tableEl, players, cat) {
  const metricKeys = Object.keys(cat.metrics);
  const bonusKeys = metricKeys.filter((key) => cat.metrics[key].bonus);
  const model = buildPlayerTableModel(players, cat.threshold_field, metricKeys, bonusKeys, READ_IDENTITY_COLUMNS);
  const layout = readLayout(model);

  const labelCell = (column) => {
    const th = document.createElement("th");
    th.className = "linemate-read-label";
    th.textContent = column.key;
    return th;
  };

  const thead = document.createElement("thead");
  thead.classList.add("merge-read-frozen");
  layout.head.forEach((row) => {
    const tr = document.createElement("tr");
    if (row.column.kind === "card") tr.className = "linemate-read-card-row";
    tr.appendChild(labelCell(row.column));
    row.cells.forEach(({ player, column }) => {
      const td = makeRosterCell(player, column, cat);
      const th = document.createElement("th");
      th.className = td.className;
      while (td.firstChild) th.appendChild(td.firstChild);
      tr.appendChild(th);
    });
    thead.appendChild(tr);
  });

  const tbody = document.createElement("tbody");
  layout.sections.forEach((section) => {
    const headingRow = document.createElement("tr");
    headingRow.className = "linemate-read-section";
    const heading = document.createElement("th");
    heading.colSpan = 1 + players.length;
    heading.textContent = section.title;
    headingRow.appendChild(heading);
    tbody.appendChild(headingRow);

    section.rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.appendChild(labelCell(row.column));
      row.cells.forEach(({ player, column }) => tr.appendChild(makeRosterCell(player, column, cat)));
      tbody.appendChild(tr);
    });
  });

  tableEl.appendChild(thead);
  tableEl.appendChild(tbody);
}

export function renderLinemateRoster(entry, roster, tableEl) {
  const cat = appliedCategoryMeta();
  tableEl.innerHTML = "";
  const sortedRoster = sortRows(roster, entry.rosterSort, (t) => linemateSortValue(t, entry.rosterSort.key, cat));
  // Only an entry that asks for Read gets it; a bare { rosterSort } (tests, older callers) is Sort.
  const isRead = entry.mode === TABLE_MODE_READ;
  tableEl.classList.toggle("linemate-table--read", isRead);
  if (isRead) {
    // Nothing sorts in Read: the order is whatever sortRows() gave.
    renderLinemateReadTable(tableEl, sortedRoster, cat);
    return;
  }

  const metricKeys = Object.keys(cat.metrics);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Player", PLAYER_CARD_COLUMN, "Position", "Games", cat.threshold_field, ...metricKeys].forEach((label) => {
    // The button column has nothing to sort, so its header is plain text.
    if (label === PLAYER_CARD_COLUMN) {
      const th = document.createElement("th");
      th.className = "linemate-table-card-head";
      th.textContent = label;
      headRow.appendChild(th);
      return;
    }
    headRow.appendChild(
      makeSortableHeader(label, label, entry.rosterSort, () => renderLinemateRoster(entry, roster, tableEl))
    );
  });
  thead.appendChild(headRow);

  const columns = [
    { key: "Player", kind: "name" },
    { key: PLAYER_CARD_COLUMN, kind: "card" },
    { key: "Position", kind: "position" },
    { key: "Games", kind: "games" },
    { key: cat.threshold_field, kind: "snaps" },
    ...metricKeys.map((key) => ({ key, kind: "metric" })),
  ];
  const tbody = document.createElement("tbody");
  sortedRoster.forEach((t) => {
    // Frozen status (the Player, Card and Position cells) is applied after
    // append, by applyStickyLinemateColumns() — see the rAF call at the
    // bottom of this function.
    const tr = document.createElement("tr");
    columns.forEach((column) => tr.appendChild(makeRosterCell(t, column, cat)));
    tbody.appendChild(tr);
  });

  tableEl.appendChild(thead);
  tableEl.appendChild(tbody);

  // On first build (openLinemateCard() calls this before appending cardEl to
  // the DOM), tableEl isn't connected yet — column widths aren't measurable
  // until a frame after that append lands, same reasoning as Merge Card's
  // own deferred applyStickyMetaColumns() call. Every other caller (refreshes,
  // and card-export.js's prepareClone rebuilding this
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

// In Read, a roster with more players than fit the card's width scrolls
// sideways (the label column stays put, a hint says so). The card marks itself
// "is-wide" for that, and style.css does the rest. Measured, not computed: how
// wide the table is depends on how many players there are, the card's width and
// what the user dragged it to, so it runs after every render and whenever the
// card or its table changes size (see openLinemateCard()). A folded card has no
// layout to measure, so it keeps whatever it had.
export function updateLinemateReadOverflow(cardEl) {
  const wrapEl = cardEl.querySelector(".linemate-table-wrap");
  const tableEl = cardEl.querySelector(".linemate-table");
  if (!wrapEl || !tableEl || !wrapEl.offsetParent) return;

  const isWide = cardEl.classList.contains("is-read") && tableEl.offsetWidth > wrapEl.clientWidth + 1;
  cardEl.classList.toggle("is-wide", isWide);
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
  const summaryTable = cardEl.querySelector(".linemate-summary-table");

  entry.roster = computeLinemateRoster(entry.anchorRecord);
  const roster = entry.roster;
  // What actually renders — teammates, plus the anchor's own row when
  // "Include anchor player" is on. See linemateDisplayRoster()'s own
  // comment for why roster (threshold-relevant) and this stay separate.
  const displayRoster = linemateDisplayRoster(entry);

  titleEl.textContent = entry.includeAnchor
    ? `${entry.anchorRecord.player} & His Linemates`
    : `${entry.anchorRecord.player} Linemates`; // season now lives on .linemate-card-meta, set once at open
  // The roster-size/threshold sentence sits on its own line above the "All
  // numbers are..." disclaimer, rather than behind a hover-only info icon.
  // Always describes the teammates-only pool (roster, not displayRoster)
  // regardless of the anchor toggle — this is the threshold talking, not a
  // literal count of the table's current rows.
  const rosterNoteEl = cardEl.querySelector(".linemate-card-roster-note");
  rosterNoteEl.textContent = `${roster.length} linemate${roster.length === 1 ? "" : "s"} with ≥ ${thresholdPhrase(appliedThreshold())} ${thresholdFieldLabel(cat)}.`;

  // With no roster cap, a very low threshold puts many players on the card;
  // past the old cap's size the card says a higher threshold keeps it compact.
  const reminderEl = cardEl.querySelector(".linemate-card-size-reminder");
  reminderEl.textContent = `${roster.length} linemates qualify at this threshold. A higher threshold keeps the card compact.`;
  reminderEl.hidden = roster.length <= LINEMATE_SIZE_REMINDER_AT[appliedFilters.category];
  const isRead = entry.mode === TABLE_MODE_READ;
  cardEl.classList.toggle("is-read", isRead);
  cardEl.classList.toggle("is-sort", !isRead);
  cardEl.querySelectorAll(".merge-mode-btn").forEach((btn) => {
    const active = btn.dataset.mode === entry.mode;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
  renderLinemateRoster(entry, displayRoster, tableEl);
  updateLinemateReadOverflow(cardEl);

  // 3M + RSWA summary, computed over every qualifying linemate — plus the
  // anchor himself when the toggle is on.
  renderLinemateSummary(entry, displayRoster, summaryTable);
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
// `roster` — every player on the card, see computeThreeMRSWA()'s own header
// comment. Extracted from
// renderLinemateCardBody() so a header click can re-run just this table
// (sortRows()/makeSortableHeader(), same pattern as renderLinemateRoster()
// above) without recomputing the roster table too.
export function renderLinemateSummary(entry, roster, summaryTable) {
  const cat = appliedCategoryMeta();
  const summary = computeThreeMRSWA(roster, cat);
  const summaryRows = summaryMetricEntries(cat).map(([key]) => ({ key, ...summary[key] }));
  const sortedRows = sortRows(summaryRows, entry.summarySort, (row) => summarySortValue(row, entry.summarySort.key));

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

// Logo/badge + team · season line. Team and season are fixed until a "refresh"
// Apply carries the card to another season (retargetLinemateCard()).
function setLinemateCardIdentity(cardEl, anchorRecord) {
  const logoImg = cardEl.querySelector(".scout-logo");
  const badge = cardEl.querySelector(".scout-badge");
  const color = teamColor(anchorRecord.team);
  logoImg.src = logoSrc(anchorRecord.team);
  logoImg.alt = `${teamLabel(anchorRecord.team)} logo`;
  logoImg.hidden = false;
  badge.hidden = true;
  logoImg.onerror = () => {
    logoImg.hidden = true;
    badge.hidden = false;
    badge.textContent = teamLabel(anchorRecord.team);
    badge.style.background = color;
  };
  cardEl.querySelector(".linemate-card-meta").textContent = `${teamName(anchorRecord.team)} · ${appliedFilters.season}`;
}

// Re-points an open Linemate Card at the anchor's row in another season. The
// roster/summary are recomputed by the refreshOpenLinemateCards() that follows
// (the roster derives from the anchor + applied filters, so teammates are
// never checked individually).
export function retargetLinemateCard(entry, anchorRecord) {
  entry.anchorRecord = anchorRecord;
  setLinemateCardIdentity(entry.el, anchorRecord);
}

const MODE_SWITCH_HELP = [
  "Read: players as columns and metrics as rows. No sorting in this mode.",
  "Sort: players as rows and metrics as columns. Click a column header to order players by that metric.",
  "Only the Individual table switches; the Line Summary stays as it is.",
];

export function openLinemateCard(anchorRecord) {
  const cardEl = els.linemateCardTemplate.content.firstElementChild.cloneNode(true);

  const closeBtn = cardEl.querySelector(".scout-close");
  const foldBtn = cardEl.querySelector(".scout-fold");
  const dragHandle = cardEl.querySelector(".scout-drag-handle");
  const tableEl = cardEl.querySelector(".linemate-table");
  const anchorToggle = cardEl.querySelector(".linemate-anchor-checkbox");
  const anchorToggleLabel = cardEl.querySelector(".linemate-anchor-toggle-label");

  // Team/season only change via retargetLinemateCard() (a "refresh" Apply);
  // a category/position change or a "reset" dissolves the card instead.
  setLinemateCardIdentity(cardEl, anchorRecord);
  // Anchor name is fixed for the card's lifetime — set once here.
  anchorToggleLabel.textContent = `Include ${anchorRecord.player} into tables.`;

  const id = nextCardId();
  const entry = {
    id,
    origin: "linemate",
    anchorKey: anchorRecord.player,
    anchorRecord,
    roster: [],
    el: cardEl,
    folded: false,
    // The Individual table's layout (player-table-model.js): Read by default, kept across
    // refreshes, fold/unfold and "Include anchor" like the sort state is.
    mode: TABLE_MODE_READ,
    includeAnchor: false,
    // Excel-style click-to-sort state for the roster and Line Summary
    // tables (table-sort.js) — independent of each other, and persisted
    // across a threshold-only refresh (renderLinemateCardBody() never resets
    // either).
    rosterSort: { key: null, dir: "asc" },
    summarySort: { key: null, dir: "asc" },
  };

  // Full rebuild (title/roster/summary all depend on includeAnchor) rather
  // than a partial patch, same reason a threshold refresh reuses this whole
  // function too — entry.roster itself is untouched by this (computed fresh
  // from computeLinemateRoster() either way), so the roster never sees this
  // toggle.
  anchorToggle.addEventListener("change", () => {
    entry.includeAnchor = anchorToggle.checked;
    renderLinemateCardBody(entry);
  });

  // The Read | Sort switch on the "Individual" heading, and the (i) saying what it covers.
  const modeSwitch = cardEl.querySelector(".merge-mode-switch");
  modeSwitch
    .querySelector(".merge-mode-info")
    .appendChild(
      createInfoPopover({ bullets: MODE_SWITCH_HELP }, { ariaLabel: MODE_SWITCH_HELP.join(" "), label: "ⓘ" })
    );
  modeSwitch.querySelectorAll(".merge-mode-btn").forEach((btn) =>
    btn.addEventListener("click", () => {
      if (entry.mode === btn.dataset.mode) return;
      entry.mode = btn.dataset.mode;
      renderLinemateCardBody(entry);
    })
  );

  renderLinemateCardBody(entry);

  els.scoutCards.appendChild(cardEl);
  cascadeScoutCardPosition(cardEl); // must run before linemateCards.set() below
  cardEl.classList.add("is-active");
  bringScoutCardToFront(cardEl);

  attachScoutResize(cardEl, entry);

  // The table's width follows its players and the card's width follows the user's
  // dragging, so the sideways-scroll state is re-measured whenever either changes.
  // ResizeObserver is missing in very old browsers, where the render-time call is all it gets.
  if (typeof ResizeObserver === "function") {
    const overflowObserver = new ResizeObserver(() => updateLinemateReadOverflow(cardEl));
    overflowObserver.observe(cardEl);
    overflowObserver.observe(tableEl);
  }

  closeBtn.addEventListener("click", () => closeLinemateCard(anchorRecord.player));
  foldBtn.addEventListener("click", () => toggleCardFold(cardEl, entry));
  dragHandle.addEventListener("pointerdown", (e) => beginScoutDrag(e, cardEl));
  dragHandle.addEventListener("pointermove", onScoutDragMove);
  dragHandle.addEventListener("pointerup", endScoutDrag);
  dragHandle.addEventListener("pointercancel", endScoutDrag);
  cardEl.addEventListener("pointerdown", () => bringScoutCardToFront(cardEl));
  attachCardSave(
    cardEl,
    // abbr_name shortens the first name to an initial, keeping the last name
    // intact (e.g. "D. Hall") — same convention already shown on the card's
    // own title, just applied to the downloaded filename too.
    () =>
      `LinesShines_${sanitizeForFilename(anchorRecord.abbr_name || anchorRecord.player)}_Linemates_${appliedFilters.season}`,
    // The export is always the Read layout, whichever mode is on screen: the Sort layout is too
    // wide to share. Re-renders the off-screen CLONE only (the card on screen is never touched),
    // carries the card's current sort order along, and returns true so the export re-fits the clone
    // to its new size (see exportCardPng()).
    (clone) => {
      const cloneTableEl = clone.querySelector(".linemate-table");
      clone.classList.add("is-read");
      clone.classList.remove("is-sort");
      if (cloneTableEl) {
        renderLinemateRoster(
          { mode: TABLE_MODE_READ, rosterSort: entry.rosterSort },
          linemateDisplayRoster(entry),
          cloneTableEl
        );
        // The "Card" buttons do nothing in a picture, so their row is left out of the export.
        cloneTableEl.querySelectorAll(".linemate-read-card-row").forEach((row) => row.remove());
      }
      return true;
    },
    () => (els.metricNotesToggle.checked ? categoryAppendixNotes(appliedCategoryMeta(), metadata.tps_note) : [])
  );

  linemateCards.set(anchorRecord.player, entry);
  updateScoutEmptyHint();
}
