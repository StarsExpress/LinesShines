/* Player (Scout) Cards — one per pinned player, keyed by record.player.
 * Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3 step 6.
 */
import { els } from "./dom.js";
import {
  appliedCategoryMeta,
  appliedFilters,
  currentFiltered,
  rankAndPercentile,
  teamColor,
  teamName,
  logoSrc,
  thresholdFieldLabel,
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
import { toggleLinemateCard } from "./linemate-card.js";
import { attachCardSave, sanitizeForFilename } from "./card-export.js";
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

  const poolEl = cardEl.querySelector(".scout-card-pool");
  poolEl.textContent = `Percentiles calculated among ${currentFiltered.length} ${record.position}.`;

  const thresholdEl = cardEl.querySelector(".scout-card-threshold");
  thresholdEl.textContent = `Threshold: ≥ ${appliedFilters.threshold} ${thresholdFieldLabel(cat)}.`;

  // Three grid children per row (dt, value dd, rank dd) so the grid's
  // row-major auto-placement stays aligned — a row that only emitted two
  // children when it has no rank would shift every following row's columns.
  // Games / the threshold field get an empty rank cell for exactly this
  // reason, not because rank text was omitted by accident. `percentile`
  // is only passed for metric rows (Games/threshold field have none) — when
  // present, the whole "#rank/N · Nth pct" string renders inside a colored
  // chip span rather than as plain text.
  const addRow = (label, value, rankText, percentile) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.className = "scout-stat-value";
    dd.textContent = value;
    const rankDd = document.createElement("dd");
    rankDd.className = "scout-stat-rank";
    if (rankText && percentile != null) {
      const chip = document.createElement("span");
      chip.className = `scout-pct-chip ${percentileChipClass(percentile)}`;
      chip.textContent = rankText;
      rankDd.appendChild(chip);
    } else {
      rankDd.textContent = rankText || "—";
    }
    statsEl.appendChild(dt);
    statsEl.appendChild(dd);
    statsEl.appendChild(rankDd);
  };

  // Games and the threshold field (PR Opp / Non Spike PB Snaps) are volume
  // stats, not rate metrics — rank/percentile against them wouldn't mean
  // "how well this player performed," so only the metrics loop below gets a rank.
  addRow("Games", record.games);
  addRow(cat.threshold_field, record[cat.threshold_field]);
  Object.entries(cat.metrics).forEach(([key, meta]) => {
    const rank = rankAndPercentile(currentFiltered, key, meta.higher_is_better, record[key]);
    const rankText = rank ? `#${rank.rank}/${rank.n} · ${ordinal(rank.percentile)} pct` : "";
    addRow(key, formatValue(record[key], meta), rankText, rank ? rank.percentile : null);
  });
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

export function openScoutCard(record) {
  const cardEl = els.scoutCardTemplate.content.firstElementChild.cloneNode(true);

  const closeBtn = cardEl.querySelector(".scout-close");
  const foldBtn = cardEl.querySelector(".scout-fold");
  const dragHandle = cardEl.querySelector(".scout-drag-handle");
  const logoImg = cardEl.querySelector(".scout-logo");
  const badge = cardEl.querySelector(".scout-badge");
  const nameEl = cardEl.querySelector(".scout-name");
  const metaEl = cardEl.querySelector(".scout-meta");
  const linemateBtn = cardEl.querySelector(".card-linemate-toggle");

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

  nameEl.textContent = record.player;
  metaEl.textContent = `${teamName(record.team)} · ${record.position} · ${appliedFilters.season}`;

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
  linemateBtn.addEventListener("click", () => toggleLinemateCard(record));
  // abbr_name shortens the first name to an initial, keeping the last name
  // intact (e.g. "D. Hall") — same convention already shown on every card
  // title/table cell, just applied to the downloaded filename too.
  attachCardSave(cardEl, () => `LinesShines_${sanitizeForFilename(record.abbr_name || record.player)}_${appliedFilters.season}`);

  scoutCards.set(record.player, entry);
  updateScoutEmptyHint();
}

// The floating card's own × — per BLUEPRINT_PinnedPlayers.md §3, this
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
