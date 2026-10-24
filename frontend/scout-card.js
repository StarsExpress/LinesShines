/* Player (Scout) Cards — one per pinned player, keyed by record.player.
 * Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3 step 6.
 */
import { els } from "./dom.js";
import {
  appliedCategoryMeta,
  appliedFilters,
  positionPool,
  rankAndPercentile,
  teamColor,
  teamName,
  logoSrc,
  thresholdFieldLabel,
  metadata,
} from "./data.js";
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
import { toggleLinemateCard, setPlayerCardOpener } from "./linemate-card.js";
import { attachCardSave, sanitizeForFilename } from "./card-export.js";
import { categoryAppendixNotes } from "./metric-notes.js";
import { DISPLAY_DECIMALS } from "./config.js";

// Live floating Player Cards, one per currently-open card, keyed by the same
// full "player" string selectedPlayers/prunePlayerSelections use elsewhere —
// player.player uniquely identifies a row within a slice. Each entry is
// { record, el } where el is the cloned .scout-card DOM node currently
// sitting in #scout-cards. Any number can be open/dragged/overlapping at
// once; see openScoutCard()/closeScoutCard() below. Purely an "is this
// floating card open" registry now — it does NOT imply Workspace membership,
// see workspaceSingles above.
export const scoutCards = new Map();

// Rounds to DISPLAY_DECIMALS for display only — the underlying record (and
// everything plotted from it) keeps its full DB precision untouched.
export function formatValue(value, meta) {
  if (value == null) return "—";
  const unit = meta && meta.unit ? meta.unit : "";
  const rounded = typeof value === "number" ? value.toFixed(DISPLAY_DECIMALS) : value;
  return `${rounded}${unit}`;
}

// Player Card-only percentile color coding (six bins) for the rank/percentile
// chip in .scout-stat-rank — scoped here rather than in a shared module since
// Linemate/Merge Card rank cells (and the Line Summary table) don't get this
// treatment. Bin edges are half-open on the low end, closed on the high end
// at 100, matching how rankAndPercentile()'s ordinal percentile is computed.
function percentileChipClass(percentile) {
  if (percentile < 35) return "scout-pct-red";
  if (percentile < 50) return "scout-pct-orange";
  if (percentile < 65) return "scout-pct-yellow";
  if (percentile < 75) return "scout-pct-lightblue";
  if (percentile < 90) return "scout-pct-darkblue";
  return "scout-pct-violet";
}

// Builds/rebuilds a Player Card's stat rows (value + rank/percentile) — used
// both at open time and to refresh an already-open card after Apply, since
// currentFiltered/appliedFilters.xMetric/yMetric can all change without the
// card ever closing (a threshold-only change doesn't call closeAllScoutCards
// — see applyFilters()). Rebuilding from scratch each call is simplest and
// cheap at the card counts this app ever has open.
export function renderScoutCardStats(cardEl, record) {
  const cat = appliedCategoryMeta();
  const statsEl = cardEl.querySelector(".scout-stats");
  statsEl.innerHTML = "";

  // The player's own position pool, not the plot's: a card opened from a Linemate
  // Card's "Card" button can belong to another position on the line (a DI while
  // the plot shows ED), and its percentiles must be among his own position.
  // For a player at the applied position this is the same set as currentFiltered.
  const pool = positionPool(record.position);
  const poolEl = cardEl.querySelector(".scout-card-pool");
  poolEl.textContent = `Percentiles calculated among ${pool.length} ${record.position}.`;

  const thresholdEl = cardEl.querySelector(".scout-card-threshold");
  thresholdEl.textContent = `Threshold: ≥ ${appliedFilters.threshold} ${thresholdFieldLabel(cat)}.`;

  // A metric's own one-line explanation (metadata `card_note`, e.g. Pass Cov
  // Percent) goes right after the threshold line; the line hides when the
  // category has none (pass block).
  const metricNoteEl = cardEl.querySelector(".scout-card-metric-note");
  const metricNotes = Object.entries(cat.metrics)
    .filter(([, meta]) => meta.card_note)
    .map(([key, meta]) => `${key}: ${meta.card_note}`);
  metricNoteEl.textContent = metricNotes.join(" ");
  metricNoteEl.hidden = metricNotes.length === 0;

  // Three grid children per row (dt, value dd, rank dd) so the grid's
  // row-major auto-placement stays aligned — a row that only emitted two
  // children when it has no rank would shift every following row's columns.
  // Games / the threshold field get an empty rank cell for exactly this
  // reason, not because rank text was omitted by accident. `percentile`
  // is only passed for metric rows (Games/threshold field have none) — when
  // present, the whole "#rank/N · Nth pct" string renders inside a colored
  // chip span rather than as plain text.
  const addRow = (gridEl, label, value, rankText, percentile, neutral = false) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.className = "scout-stat-value";
    dd.textContent = value;
    const rankDd = document.createElement("dd");
    rankDd.className = "scout-stat-rank";
    if (rankText && percentile != null) {
      const chip = document.createElement("span");
      chip.className = `scout-pct-chip ${neutral ? "scout-pct-neutral" : percentileChipClass(percentile)}`;
      chip.textContent = rankText;
      rankDd.appendChild(chip);
    } else {
      rankDd.textContent = rankText || "—";
    }
    gridEl.appendChild(dt);
    gridEl.appendChild(dd);
    gridEl.appendChild(rankDd);
  };

  // One titled <dl> grid per section, in the order Metadata, Required
  // Metrics, Bonus Metrics. Each grid keeps the three-children-per-row layout
  // above, so its columns align inside the section.
  const addSection = (title) => {
    const heading = document.createElement("h4");
    heading.className = "scout-section-title";
    heading.textContent = title;
    const grid = document.createElement("dl");
    grid.className = "scout-stat-grid";
    statsEl.appendChild(heading);
    statsEl.appendChild(grid);
    return grid;
  };

  // Games and the threshold field (PR Opp / Non Spike PB Snaps) are volume
  // stats, not rate metrics — rank/percentile against them wouldn't mean
  // "how well this player performed," so only the metrics loop below gets a rank.
  const metadataGrid = addSection("Metadata");
  addRow(metadataGrid, "Games", record.games);
  addRow(metadataGrid, cat.threshold_field, record[cat.threshold_field]);

  // `bonus` metrics (Pass Cov Percent, DL only) get their own section after
  // the required ones; a category without any (pass block) gets no Bonus heading.
  const metricEntries = Object.entries(cat.metrics);
  const addMetricRows = (gridEl, entries) =>
    entries.forEach(([key, meta]) => {
      const rank = rankAndPercentile(pool, key, meta.higher_is_better, record[key]);
      const rankText = rank ? `#${rank.rank}/${rank.n} · ${ordinal(rank.percentile)} pct` : "";
      addRow(
        gridEl,
        key,
        formatValue(record[key], meta),
        rankText,
        rank ? rank.percentile : null,
        meta.neutral === true
      );
    });
  addMetricRows(
    addSection("Required Metrics"),
    metricEntries.filter(([, meta]) => !meta.bonus)
  );
  const bonusEntries = metricEntries.filter(([, meta]) => meta.bonus);
  if (bonusEntries.length) addMetricRows(addSection("Bonus Metrics"), bonusEntries);
}

// Re-renders every open Player Card's stats against the current
// currentFiltered/appliedFilters — called after every render() in
// applyFilters() so a threshold change (which doesn't close Player Cards,
// only a season/category/position change does) can't leave a card showing
// ranks computed against a pool that no longer exists. Safe to call
// unconditionally: if a slice change closed every card first, this is just
// an empty loop.
export function refreshOpenScoutCards() {
  scoutCards.forEach((entry) => renderScoutCardStats(entry.el, entry.record));
}

// Logo/badge + team · position · season line — the parts of a card header that
// depend on the record's team and the applied season (a player can change
// team between seasons). Shared by open and retargetScoutCard().
function setScoutCardIdentity(cardEl, record) {
  const logoImg = cardEl.querySelector(".scout-logo");
  const badge = cardEl.querySelector(".scout-badge");
  const color = teamColor(record.team);
  logoImg.src = logoSrc(record.team);
  logoImg.alt = `${record.team} logo`;
  logoImg.hidden = false;
  badge.hidden = true;
  logoImg.onerror = () => {
    logoImg.hidden = true;
    badge.hidden = false;
    badge.textContent = record.team;
    badge.style.background = color;
  };
  cardEl.querySelector(".scout-meta").textContent =
    `${teamName(record.team)} · ${record.position} · ${appliedFilters.season}`;
}

// Re-points an open Player Card at another season's row for the same player
// (a "refresh" Apply, see pinned-impact.js). Stats are re-rendered by the
// refreshOpenScoutCards() that follows.
export function retargetScoutCard(entry, record) {
  entry.record = record;
  setScoutCardIdentity(entry.el, record);
}

export function openScoutCard(record) {
  const cardEl = els.scoutCardTemplate.content.firstElementChild.cloneNode(true);

  const closeBtn = cardEl.querySelector(".scout-close");
  const foldBtn = cardEl.querySelector(".scout-fold");
  const dragHandle = cardEl.querySelector(".scout-drag-handle");
  const nameEl = cardEl.querySelector(".scout-name");
  const linemateBtn = cardEl.querySelector(".card-linemate-toggle");

  nameEl.textContent = record.player;
  setScoutCardIdentity(cardEl, record);

  renderScoutCardStats(cardEl, record);

  els.scoutCards.appendChild(cardEl);
  cascadeScoutCardPosition(cardEl); // reads openCardsCount(), so must run before scoutCards.set() below
  cardEl.classList.add("is-active");
  bringScoutCardToFront(cardEl);

  const entry = { record, el: cardEl, id: nextCardId(), origin: "seed", folded: false };
  attachScoutResize(cardEl, entry);

  closeBtn.addEventListener("click", () => closeScoutCard(record.player));
  foldBtn.addEventListener("click", () => toggleCardFold(cardEl, entry));
  dragHandle.addEventListener("pointerdown", (e) => beginScoutDrag(e, cardEl));
  dragHandle.addEventListener("pointermove", onScoutDragMove);
  dragHandle.addEventListener("pointerup", endScoutDrag);
  dragHandle.addEventListener("pointercancel", endScoutDrag);
  // Raises a card even on a plain click, not just a drag, so tapping an
  // overlapped card's stats brings it to front too.
  cardEl.addEventListener("pointerdown", () => bringScoutCardToFront(cardEl));
  // entry.record, not the closed-over `record`: retargetScoutCard() swaps it
  // when a season change carries this card to another season's row.
  linemateBtn.addEventListener("click", () => toggleLinemateCard(entry.record));
  // abbr_name shortens the first name to an initial, keeping the last name
  // intact (e.g. "D. Hall") — same convention already shown on every card
  // title/table cell, just applied to the downloaded filename too.
  attachCardSave(
    cardEl,
    () => `LinesShines_${sanitizeForFilename(entry.record.abbr_name || entry.record.player)}_${appliedFilters.season}`,
    undefined,
    () => (els.metricNotesToggle.checked ? categoryAppendixNotes(appliedCategoryMeta(), metadata.tps_note) : [])
  );

  scoutCards.set(record.player, entry);
  updateScoutEmptyHint();
}

// The floating card's own × — this
// ONLY closes the floating card. It does NOT touch workspaceSingles or the
// Pinned Players in any way — a player's Single Cards row survives
// regardless, exactly mirroring how his own Linemate Card, if open, is also
// left alone: its roster/summary were computed once at open time and never
// read back from scoutCards, so it has nothing left to depend on and can
// keep floating on screen after its anchor Player Card is gone.
export function closeScoutCard(key) {
  const entry = scoutCards.get(key);
  if (!entry) return;
  entry.el.remove();
  scoutCards.delete(key);
  updateScoutEmptyHint();
}

// Bulk-closes every floating Player Card — used by clearWorkspace() (a real
// Workspace-clearing operation, unlike the individual × above).
export function closeAllScoutCards() {
  scoutCards.forEach((entry) => entry.el.remove());
  scoutCards.clear();
  updateScoutEmptyHint();
}

// Wired to the chart's plotly_click handler (v1.2.0 §4 — plot-click and
// Space-membership are now fully decoupled: this ONLY opens or flashes the
// floating card for viewing, it never touches workspaceSingles). A click on
// a player whose card is already open just flashes/refocuses it; repeat
// clicks must be safe and never toggle-close anything.
export function viewFloatingCard(record) {
  const key = record.player;
  if (scoutCards.has(key)) {
    flashFloatingCard(key);
  } else {
    openScoutCard(record);
  }
}

// Lets a Linemate Card row's "Card" button open or refocus that player's card
// (see setPlayerCardOpener() in linemate-card.js for why it is injected).
setPlayerCardOpener(viewFloatingCard);

export function flashFloatingCard(key) {
  const entry = scoutCards.get(key);
  if (!entry) return;
  bringScoutCardToFront(entry.el);
  entry.el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  entry.el.classList.remove("is-flash");
  void entry.el.offsetWidth;
  entry.el.classList.add("is-flash");
  entry.el.addEventListener("animationend", () => entry.el.classList.remove("is-flash"), { once: true });
}
