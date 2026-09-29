/* Filter panel UI wiring: Category/Season/Position/Metric selects, the
 * Teams checklist, the Players fuzzy-search chips, and applyFilters() — the
 * pool-change vs. axes-only vs. threshold-only dispatch logic described in
 * CLAUDE.md's "Pool-change invalidation" section. Extracted from app.js per
 * MODULARIZATION.md v1.3.0 §2/§3 step 8.
 *
 * searchPlayers() lives here rather than in search.js — see search.js's own
 * header comment for why (it needs this module's selectedPlayers state).
 *
 * allTeamCodes() lives in data.js, not here, even though every other Teams-
 * checklist helper is local to this file — render.js's highlightSubtitle()
 * needs it too, and importing it from here would make render.js depend on
 * filters.js while filters.js already depends on render.js (for render()
 * itself), a circular import with no function-body-only escape hatch this
 * time. data.js is a dependency both modules already have.
 */
import { els } from "./dom.js";
import {
  metadata,
  playerPoolCategory,
  playerPoolRecords,
  appliedFilters,
  currentRecords,
  fetchSlice,
  setCurrentSlice,
  setPlayerPool,
  setAppliedFilters,
  currentCategoryMeta,
  thresholdFieldLabel,
  logoSrc,
  teamSwatch,
  teamName,
  allTeamCodes,
} from "./data.js";
import { searchPlayersExcluding, qualifyingPlayerPool, fullPlayerPool } from "./search.js";
import { CONFERENCES } from "./config.js";
import { render } from "./render.js";
import { refreshOpenScoutCards } from "./scout-card.js";
import { refreshOpenLinemateCards, clearLinemateCards } from "./linemate-card.js";
import { workspaceSingles, mergeCards, refreshOpenMergeCards } from "./merge-card.js";
import { clearWorkspace, showMergeInvalidationConfirm } from "./workspace.js";

// True right after page load and right after a category switch — both cases
// where the threshold should snap to that category's configured default
// rather than carrying over a value from a different threshold_field scale
// (PR Opp vs Non Spike PB Snaps aren't comparable). Season/position changes
// within the same category leave this false, so the user's value persists.
// If the user manually edits the threshold slider/number while a category
// switch is still pending (not yet Applied), that's an explicit override —
// it clears this flag so applyFilters() doesn't clobber it with the new
// category's default.
export let resetThresholdOnNextRange = true;

// main.js's attachEvents() sets this directly on a category change and on a
// manual threshold edit — same reason every other cross-module write in
// this split goes through a setter, see data.js's header comment.
export function setResetThresholdOnNextRange(v) {
  resetThresholdOnNextRange = v;
}

// Players filter: full player name ("player", not the abbreviated display
// name) → record, in selection order. Live/pending like the Teams
// checklist — edited freely via chips, only takes effect on the chart once
// Apply snapshots it into appliedFilters.players (see currentFilterState()).
export const selectedPlayers = new Map();

// Below-threshold-matches popup (surfaces a name match that exists but
// doesn't clear the current threshold, rather than leaving that
// indistinguishable from "no such player" — see runPlayersSearch()). A
// generous cap since this is a scrollable popup, not the 8-item autocomplete
// dropdown — just enough to keep a single-letter query from dumping the
// whole pool into it. Exported since every Pinned Players search box
// (workspace.js/merge-card.js) reuses the same cap for its own below-
// threshold pass, see those files' run*Search() functions.
export const BELOW_THRESHOLD_TOP_K = 20;
let belowThresholdMatches = [];

export function currentFilterState() {
  return {
    category: els.category.value,
    season: els.season.value,
    position: els.position.value,
    xMetric: els.xMetric.value,
    yMetric: els.yMetric.value,
    threshold: els.thresholdNumber.value,
    // Joined into a comparable string (not a bare array) so the `!==`
    // check in filtersArePending() works the same way it does for every
    // other primitive-valued control — two different array references
    // would never compare equal even with identical contents.
    teams: selectedTeamCodes().sort().join(","),
    players: Array.from(selectedPlayers.keys()).sort().join(","),
  };
}

export function selectedTeamCodes() {
  return Array.from(els.teamsChecklist.querySelectorAll("input[type=checkbox]:checked")).map((cb) => cb.value);
}

// Teams and Players combine via union (CLAUDE.md's "Teams and Players
// filters combine via union" section) — a full 32-team selection highlights
// every player regardless of Players, which makes picking a specific player
// on top of it a no-op the user almost certainly didn't intend. Auto-resets
// Teams to none selected in exactly that one case. Deliberately scoped to
// the all-32 case only: a partial selection (even 5 or 31 teams) is a
// legitimate combination the user chose on purpose and must survive a
// player pick untouched — only ever called from the player-pick handler
// below, never from anywhere a partial selection should be left alone.
function resetTeamsIfAllSelected() {
  if (selectedTeamCodes().length !== allTeamCodes().length) return;
  els.teamsChecklist.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = false));
  updateTeamsSummary();
}

export function teamOptionRow(code) {
  const label = document.createElement("label");
  label.className = "team-option";

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.value = code;
  cb.checked = true;

  const logo = document.createElement("img");
  logo.className = "team-option-logo";
  logo.src = logoSrc(code);
  logo.alt = "";
  logo.loading = "lazy";
  logo.onerror = () => logo.replaceWith(teamSwatch(code));

  const text = document.createElement("span");
  text.textContent = code;

  label.append(cb, logo, text);
  return label;
}

export function populateTeamsChecklist() {
  els.teamsChecklist.innerHTML = "";

  Object.entries(CONFERENCES).forEach(([conference, divisions]) => {
    const column = document.createElement("div");
    column.className = "teams-column";

    const columnHeader = document.createElement("div");
    columnHeader.className = "teams-column-header";
    columnHeader.textContent = conference;
    column.appendChild(columnHeader);

    Object.entries(divisions).forEach(([division, codes]) => {
      const group = document.createElement("div");
      group.className = "teams-division";

      const divisionHeader = document.createElement("div");
      divisionHeader.className = "teams-division-header";
      divisionHeader.textContent = division;
      group.appendChild(divisionHeader);

      // Codes are already listed ascending within each division above.
      codes.forEach((code) => group.appendChild(teamOptionRow(code)));
      column.appendChild(group);
    });

    els.teamsChecklist.appendChild(column);
  });

  updateTeamsSummary();
}

export function updateTeamsSummary() {
  const selected = selectedTeamCodes();
  const total = allTeamCodes().length;
  if (selected.length === total) els.teamsSummary.textContent = "All Teams";
  else if (selected.length === 0) els.teamsSummary.textContent = "No Teams";
  else if (selected.length === 1) els.teamsSummary.textContent = teamName(selected[0]);
  else els.teamsSummary.textContent = `${selected.length} Teams`;
}

export function openTeamsDropdown() {
  els.teamsDropdown.hidden = false;
  els.teamsBtn.setAttribute("aria-expanded", "true");
}

export function closeTeamsDropdown() {
  els.teamsDropdown.hidden = true;
  els.teamsBtn.setAttribute("aria-expanded", "false");
}


// Players filter's own search — no point suggesting a chip that already
// exists, so it excludes whatever's already selected there.
export function searchPlayers(query, pool, topK = 8) {
  return searchPlayersExcluding(query, pool, new Set(selectedPlayers.keys()), topK);
}

export function renderPlayerChips() {
  els.playersChips.innerHTML = "";
  selectedPlayers.forEach((record, key) => {
    const label = record.abbr_name || record.player;
    const chip = document.createElement("span");
    chip.className = "player-chip";

    const text = document.createElement("span");
    text.textContent = label;

    const removeBtn = document.createElement("button");

    removeBtn.type = "button";
    removeBtn.className = "player-chip-remove";
    removeBtn.setAttribute("aria-label", `Remove ${label}`);
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => {
      selectedPlayers.delete(key);
      renderPlayerChips();
      updatePendingState();
    });

    chip.append(text, removeBtn);
    els.playersChips.appendChild(chip);
  });
  updatePlayersSummary();
}

// Mirrors updateTeamsSummary() — the collapsed button's label, shown while
// .players-panel is closed so the chip list itself never has to fit inside
// the collapsed button (see the control-players sizing comment above .control-players).
export function updatePlayersSummary() {
  const count = selectedPlayers.size;
  if (count === 0) els.playersSummary.textContent = "No Players";
  else if (count === 1) {
    const [[, record]] = selectedPlayers;
    els.playersSummary.textContent = record.abbr_name || record.player;
  } else els.playersSummary.textContent = `${count} Players`;
}

export function openPlayersPanel() {
  els.playersPanel.hidden = false;
  els.playersBtn.setAttribute("aria-expanded", "true");
  els.playersInput.focus();
}

export function closePlayersPanel() {
  els.playersPanel.hidden = true;
  els.playersBtn.setAttribute("aria-expanded", "false");
  hidePlayersDropdown();
}

export function hidePlayersDropdown() {
  els.playersDropdown.hidden = true;
  els.playersDropdown.innerHTML = "";
}

export function renderPlayersDropdown(matches) {
  els.playersDropdown.innerHTML = "";
  if (!matches.length && !belowThresholdMatches.length) {
    hidePlayersDropdown();
    return;
  }

  // Sits above the first normal candidate, not among them — it opens a
  // popup rather than picking a player, so it's styled/behaves distinctly
  // from a .player-option row. Renders only when there's at least one
  // below-threshold match; N mirrors whatever runPlayersSearch() just found.
  if (belowThresholdMatches.length > 0) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "below-threshold-toggle";
    toggle.textContent = `Below Threshold Matches (${belowThresholdMatches.length})`;
    toggle.addEventListener("click", () =>
      openBelowThresholdPopup(belowThresholdMatches, metadata[playerPoolCategory], (value) => {
        // Players filter stays Apply-gated, same as every other batched
        // control here — see setThresholdTo()'s own comment for why this
        // only stages a pending value rather than committing it the way
        // applyThresholdImmediately() does for Pinned Players below.
        setThresholdTo(value);
        runPlayersSearch();
      })
    );
    els.playersDropdown.appendChild(toggle);
  }

  matches.forEach((record) => {
    const opt = document.createElement("button");
    opt.type = "button";
    opt.className = "player-option";

    // Full name here (unlike the abbreviated chip label) — the dropdown is
    // a disambiguation UI where "Anderson" alone could mean several
    // players, so the full name plus team logo carries more identifying
    // context than the compact "W. Anderson Jr." the chip uses once picked.
    const name = document.createElement("span");
    name.className = "player-option-name";
    name.textContent = record.player;

    const team = document.createElement("span");
    team.className = "player-option-team";

    const logo = document.createElement("img");
    logo.className = "player-option-logo";
    logo.src = logoSrc(record.team);
    logo.alt = "";
    logo.loading = "lazy";
    logo.onerror = () => logo.replaceWith(teamSwatch(record.team));

    const code = document.createElement("span");
    code.textContent = record.team;

    team.append(logo, code);
    opt.append(name, team);
    opt.addEventListener("click", () => {
      selectedPlayers.set(record.player, record);
      resetTeamsIfAllSelected();
      renderPlayerChips();
      updatePendingState();
      els.playersInput.focus();
      // Keep the query text and dropdown alive instead of clearing/closing —
      // searchPlayers() already excludes just-picked players, so re-running
      // it surfaces the next-best matches for the same query (e.g. picking
      // "Chris Jones" out of a "Jones" search leaves DaQuan/Travis Jones in
      // the list) without the user having to retype the query per pick.
      runPlayersSearch();
    });

    els.playersDropdown.appendChild(opt);
  });

  els.playersDropdown.hidden = false;
}

export function runPlayersSearch() {
  const query = els.playersInput.value.trim();
  if (!query) {
    belowThresholdMatches = [];
    hidePlayersDropdown();
    return;
  }

  // Two independent passes, not one filtered afterward — searchPlayers()
  // over qualifyingPlayerPool() stays exactly as it was (the normal
  // dropdown's ranking must not shift just because this feature exists, see
  // fullPlayerPool()'s header comment). This second pass runs the same
  // fuzzy matcher against the unfiltered pool and keeps only what didn't
  // already clear the bar, so it can never overlap with the normal results.
  if (playerPoolCategory) {
    const cat = metadata[playerPoolCategory];
    const minThreshold = Number(els.thresholdNumber.value);
    const fullMatches = searchPlayers(query, fullPlayerPool(), BELOW_THRESHOLD_TOP_K);
    belowThresholdMatches = fullMatches.filter((r) => r[cat.threshold_field] < minThreshold);
  } else {
    belowThresholdMatches = [];
  }

  renderPlayersDropdown(searchPlayers(query, qualifyingPlayerPool()));
}

// Single static overlay, repopulated per open — same convention as
// #merge-edit-overlay (see its header comment in index.html): no
// outside-click dismissal, closes only via its own Close button (wired once
// in main.js's attachEvents()). Shared by every search box with a below-
// threshold concept (the Players filter here, plus every Pinned Players
// search box in workspace.js/merge-card.js) rather than one popup per box —
// there's only ever one threshold control to quick-set regardless of which
// box's dropdown the toggle was clicked from. `matches` and `cat` are
// whatever that box's own run*Search() just computed; `onSetThreshold(value)`
// is called on the Set Threshold click, before the popup closes — it owns
// BOTH committing the value (setThresholdTo() for the Players filter's own
// pending-only behavior, applyThresholdImmediately() for every Pinned
// Players box, see that function's comment) AND re-running that box's own
// search afterward. Deliberately left entirely to the caller rather than
// hardcoded here, since the two commit strategies differ per caller and this
// popup has no business knowing which one applies.
export function openBelowThresholdPopup(matches, cat, onSetThreshold) {
  els.belowThresholdList.innerHTML = "";

  matches.forEach((record) => {
    const row = document.createElement("div");
    row.className = "below-threshold-row";

    const info = document.createElement("div");
    info.className = "below-threshold-row-info";

    const name = document.createElement("span");
    name.className = "player-option-name";
    name.textContent = record.player;

    const team = document.createElement("span");
    team.className = "player-option-team";
    const logo = document.createElement("img");
    logo.className = "player-option-logo";
    logo.src = logoSrc(record.team);
    logo.alt = "";
    logo.loading = "lazy";
    logo.onerror = () => logo.replaceWith(teamSwatch(record.team));
    const code = document.createElement("span");
    code.textContent = record.team;
    team.append(logo, code);

    info.append(name, team);

    const value = document.createElement("span");
    value.className = "below-threshold-row-value";
    value.textContent = `${record[cat.threshold_field]} ${cat.threshold_field}`;

    const setBtn = document.createElement("button");
    setBtn.type = "button";
    setBtn.className = "below-threshold-row-btn";
    setBtn.textContent = "Set Threshold";
    setBtn.addEventListener("click", () => {
      // Query text is left untouched (nothing in this flow writes to the
      // triggering box's own input) — onSetThreshold's own rerun surfaces
      // the just-qualified player the same way retyping the query would.
      onSetThreshold(record[cat.threshold_field]);
      closeBelowThresholdPopup();
    });

    row.append(info, value, setBtn);
    els.belowThresholdList.appendChild(row);
  });

  els.belowThresholdOverlay.hidden = false;
}

export function closeBelowThresholdPopup() {
  els.belowThresholdOverlay.hidden = true;
  els.belowThresholdList.innerHTML = "";
}

// Clamp-and-sync core shared by setThresholdTo() (pending-only, Players
// filter) and applyThresholdImmediately() (commits immediately, Pinned
// Players — see below) — the filter is an inclusive `>=` (see
// qualifyingPlayerPool()), so a candidate's own metric value is already the
// minimum threshold that surfaces them, no off-by-one adjustment needed.
// Mirrors the manual slider/number-input handlers in main.js's attachEvents()
// (sync both controls, clamp to range, mark the value as an explicit
// override) rather than reimplementing that logic per caller. Neither
// caller's own appliedFilters/pool-refresh handling lives here — that's each
// one's own job, since they differ (stay pending vs. commit now).
function syncThresholdControls(value) {
  const min = Number(els.threshold.min);
  const max = Number(els.threshold.max);
  const step = Number(els.threshold.step) || 1;
  const clamped = Math.min(Math.max(value, min), max);

  els.thresholdNumber.value = clamped;
  // Slider snaps to the nearest step just to keep the handle in sync
  // visually — filtering itself reads thresholdNumber.value (the exact
  // value), same split as the manual number-input handler in main.js.
  els.threshold.value = min + Math.round((clamped - min) / step) * step;
  setResetThresholdOnNextRange(false);
}

// Sets the threshold to exactly `value`, staged as a pending edit like the
// manual slider/number-input handlers — the chart/Pinned Players search
// pools don't see it until Apply. Deliberately does NOT call
// runPlayersSearch() itself — every existing caller of this same clamp/sync/
// prune sequence (the manual handlers) leaves that to whatever's calling it,
// since a threshold edit doesn't always happen with the Players dropdown
// open.
export function setThresholdTo(value) {
  syncThresholdControls(value);
  prunePlayerSelections();
  updatePendingState();
}

// Pinned Players' own "Set Threshold" behavior (Below Threshold Matches,
// triggered from the Single Cards add-search or the Merge Create/Edit
// popups) — unlike setThresholdTo() above, this commits the new threshold
// immediately instead of staging it for the next Apply click. Pinned
// Players was never an Apply-gated area of the UI to begin with (Single/
// Merge Cards already take effect the moment you pick a player — see
// addPlayerToSingleCards()/submitCreateMergePopup()), so leaving a below-
// threshold quick-set stuck behind a full Apply — with its pool-change
// confirm and its Merge-Card-clearing side effect (see CLAUDE.md's
// "Pool-change invalidation") — forced a "back out of the Create/Edit
// popup, Apply, reopen the popup, redo the search" loop just to pull in one
// player below the bar. No refetch is needed either way — currentRecords
// already holds every threshold value (see data.js) — so this writes
// straight into appliedFilters (a threshold-only merge, every other
// currently-Applied field — category/season/position/axes/Teams/Players —
// is left exactly as it was, even if some of THOSE have their own unrelated
// pending edit sitting unapplied in the drawer right now) and refreshes
// every already-open card in place instead of invalidating the Workspace
// the way a normal Apply's threshold change does.
export function applyThresholdImmediately(value) {
  syncThresholdControls(value);
  // Read back els.thresholdNumber.value (a string) rather than restating
  // `clamped` here, so appliedFilters.threshold is byte-for-byte what
  // currentFilterState() would have produced — that's what keeps
  // filtersArePending() from lighting the Apply button for a threshold that
  // in fact just got committed.
  setAppliedFilters({ ...appliedFilters, threshold: els.thresholdNumber.value });
  prunePlayerSelections();
  render();
  refreshOpenScoutCards();
  refreshOpenLinemateCards();
  refreshOpenMergeCards();
  updatePendingState();
}

// Called whenever the qualifying pool can have shrunk — live threshold
// edits, and live category/season/position changes via updatePlayerPool()
// (e.g. switching Position from ED to DI drops any ED-only chip immediately,
// since it's no longer in the new position's pool) — so a selected player
// who no longer clears the bar (or no longer exists in the new slice)
// silently loses their chip instead of lingering as a selection that can't
// actually take effect.
export function prunePlayerSelections() {
  const poolKeys = new Set(qualifyingPlayerPool().map((r) => r.player));
  let changed = false;
  selectedPlayers.forEach((_, key) => {
    if (!poolKeys.has(key)) {
      selectedPlayers.delete(key);
      changed = true;
    }
  });
  if (changed) renderPlayerChips();
}

export function filtersArePending() {
  if (!appliedFilters) return false;
  const current = currentFilterState();
  return Object.keys(current).some((key) => current[key] !== appliedFilters[key]);
}

// Lights up the Apply button whenever any batched control (category,
// season, position, either axis, or threshold) holds a value the chart
// hasn't been rendered with yet — the only feedback the user gets now that
// none of these re-render on their own.
export function updatePendingState() {
  els.applyBtn.classList.toggle("pending", filtersArePending());
}

export function populateCategoryDependentControls() {
  const cat = currentCategoryMeta();

  // Positions
  els.position.innerHTML = "";
  Object.entries(cat.positions).forEach(([code, label]) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${label}`;
    els.position.appendChild(opt);
  });

  // Seasons (already sorted desc by the API) — rebuilding the <select>'s
  // options resets its value to whichever option lands first (the newest
  // season) unless we explicitly restore the previous selection, so a
  // category switch doesn't silently drag Season back to default along with
  // it. Only restored when the prior season still exists for the new
  // category; otherwise the browser's own first-option default stands.
  // cat.seasons holds numbers (straight from /api/metadata's JSON), but a
  // <select>'s own .value is always a string — String(s) here is what makes
  // the .includes() comparison below actually match.
  const previousSeason = els.season.value;
  els.season.innerHTML = "";
  cat.seasons.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    els.season.appendChild(opt);
  });
  if (cat.seasons.map(String).includes(previousSeason)) els.season.value = previousSeason;

  // Metrics
  const metricKeys = Object.keys(cat.metrics);
  [els.xMetric, els.yMetric].forEach((select) => {
    select.innerHTML = "";
    metricKeys.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      select.appendChild(opt);
    });
  });
  // Distinct defaults, mirroring the pipeline's canonical query pairs.
  // Anything else falls back to generic non-TPS-vs-TPS heuristic.
  if (
    els.category.value === "pass_rush" &&
    metricKeys.includes("Win Rate") &&
    metricKeys.includes("TPS PRP")
  ) {
    els.xMetric.value = "Win Rate";
    els.yMetric.value = "TPS PRP";
  } else if (
    els.category.value === "pass_block" &&
    metricKeys.includes("Allowed Pressure %") &&
    metricKeys.includes("TPS PBE")
  ) {
    els.xMetric.value = "Allowed Pressure %";
    els.yMetric.value = "TPS PBE";
  } else {
    els.xMetric.value = metricKeys.find((m) => !m.startsWith("TPS")) || metricKeys[0];
    els.yMetric.value = metricKeys.find((m) => m.startsWith("TPS")) || metricKeys[1] || metricKeys[0];
  }

  els.thresholdFieldLabel.textContent = thresholdFieldLabel(cat);
}

export async function loadCurrentSlice() {
  const category = els.category.value;
  const season = Number(els.season.value);
  // setCurrentSlice() replaces the original's direct `currentRecords =`/
  // `currentSliceCategory =` assignments — data.js owns that state now, and
  // ES modules don't let an importer reassign an imported `let` (see
  // data.js's header comment). Same two assignments, same order, same
  // timing.
  setCurrentSlice(await fetchSlice(category, season), category);
  updateThresholdRange();
}

// Mirrors loadCurrentSlice(), but for whatever category/season the controls
// are pending on right now, and never touches currentRecords/
// currentSliceCategory/updateThresholdRange — those stay reserved for the
// last Applied slice the chart is actually showing. Fired on every
// category/season/position change (see attachEvents()) so the Players
// dropdown always searches the position currently selected, e.g. switching
// from ED to DI immediately drops ED-only players like Derick Hall from the
// suggestions and starts surfacing DI players like Dexter Lawrence instead,
// without waiting for Apply. Also keeps the threshold number box's clamp
// ceiling live via updatePendingThresholdMax() below — see that function's
// own comment for why.
export async function updatePlayerPool() {
  const category = els.category.value;
  const season = Number(els.season.value);
  // setPlayerPool() — see the comment in loadCurrentSlice() above.
  setPlayerPool(await fetchSlice(category, season), category);
  updatePendingThresholdMax();
  prunePlayerSelections();
  runPlayersSearch();
}

// Live counterpart to updateThresholdRange()'s max calculation below, but
// sourced from playerPoolRecords (the pending category/season/position's
// already-fetched data, kept live by updatePlayerPool() above) instead of
// currentRecords (Apply-gated). Two independent reasons this function
// reassigns .max/.value, checked in priority order below:
//
// 1. resetThresholdOnNextRange is still true — a Category switch or an
//    ongoing→historical Season switch is still pending. A Category switch
//    already ran resetThresholdToCategoryDefault() synchronously (a rough
//    placeholder — it can only grow .max just far enough to fit the new
//    default off whatever pending data was already on hand, not this
//    slice's real max); a Season switch deliberately skips that synchronous
//    call entirely (see main.js's season "change" handler) and leaves
//    *everything* pending until here. Either way, this is the first point
//    where this slice's real fetched data is actually available, so it's
//    where the real default+max get applied, together, in one write. Doing
//    both atomically — rather than a value now / max later two-step — is
//    what avoids ever rendering a wrong intermediate frame: the old
//    two-step version could pin the slider handle at the far-right edge
//    for however long the fetch took (whenever the placeholder max landed
//    right on the new value) and then visibly snap back once corrected.
// 2. No reset is pending, but the current value no longer fits the newly
//    computed max — a real, if smaller, correction (e.g. Position swapped
//    into a narrower pool). Falls back to this season's configured default
//    rather than the raw pool max (see the comment inline below).
//
// Neither case touches .max for a swap that changes nothing (e.g. one
// historical season to another, sharing DEFAULT_THRESHOLDS' one static
// value) — a native range input's handle position is purely value/max, so
// touching .max unconditionally on every pending swap (the very first
// version of this function) visibly slid the bar even when the number box
// read identically before and after. Guarded on playerPoolCategory rather
// than els.category.value for the same race-safety reason
// runPlayersSearch()/openBelowThresholdPopup() above read it that way — an
// in-flight fetch for a category the user has since changed away from
// shouldn't get read as if it were current.
function updatePendingThresholdMax() {
  if (!playerPoolCategory) return;
  const cat = metadata[playerPoolCategory];
  const positionRecords = playerPoolRecords.filter((r) => r.position === els.position.value);
  const values = positionRecords.map((r) => r[cat.threshold_field]).filter((v) => v != null);
  const maxVal = values.length ? Math.max(...values) : 100;
  const max = Math.ceil(maxVal / 10) * 10;

  if (resetThresholdOnNextRange) {
    const defaultValue = cat.default_thresholds[els.season.value] ?? 0;
    els.threshold.max = max;
    els.thresholdNumber.max = max;
    els.threshold.value = Math.min(Math.max(defaultValue, 0), max);
    els.thresholdNumber.value = els.threshold.value;
    return;
  }

  // Read the number box's own current value *before* touching .max below —
  // a native <input type="range">'s value auto-clamps to a lowered max the
  // instant it's assigned, so checking els.threshold.value afterward would
  // silently compare against an already-corrected number and skip
  // clamping thresholdNumber (caught via manual testing: the slider ended
  // up right, but the number box was left stuck at the old, too-high
  // value). thresholdNumber has no such auto-clamp, so it's the only
  // reliable "what was actually set before this ran" source here.
  const currentValue = Number(els.thresholdNumber.value);
  if (currentValue > max) {
    const defaultValue = cat.default_thresholds[els.season.value] ?? 0;
    const fallback = Math.min(Math.max(defaultValue, 0), max);
    els.threshold.max = max;
    els.thresholdNumber.max = max;
    els.threshold.value = fallback;
    els.thresholdNumber.value = fallback;
  }
}

export function updateThresholdRange() {
  const cat = currentCategoryMeta();
  // currentRecords now holds every position in the category (see
  // fetchSlice) — scope to the pending position before computing the
  // slider's max, otherwise switching to a smaller-pool position (e.g. DI)
  // would inherit a max sized for a bigger one (e.g. ED).
  const positionRecords = currentRecords.filter((r) => r.position === els.position.value);
  const values = positionRecords.map((r) => r[cat.threshold_field]).filter((v) => v != null);
  const maxVal = values.length ? Math.max(...values) : 100;
  const max = Math.ceil(maxVal / 10) * 10;

  els.threshold.min = 0;
  els.threshold.step = 5;
  els.thresholdNumber.min = 0;

  // .max is only reassigned inside the two branches below, not
  // unconditionally up front — same "don't move the bar unless the value
  // actually needs to" rule as updatePendingThresholdMax()'s live
  // counterpart (see its comment for the full reasoning). A no-op Apply
  // (e.g. one historical season swapped for another, both sharing
  // DEFAULT_THRESHOLDS' one static value) now leaves the slider's fill
  // percentage exactly where it was instead of jumping to match
  // whatever slightly different real max the new slice happens to have.
  if (resetThresholdOnNextRange) {
    const defaultValue = cat.default_thresholds[els.season.value] ?? 0;
    els.threshold.max = max;
    els.thresholdNumber.max = max;
    els.threshold.value = Math.min(Math.max(defaultValue, 0), max);
    resetThresholdOnNextRange = false;
  } else if (Number(els.threshold.value) > max) {
    // Every other Season/Position change (Position always; Season only
    // when it isn't an ongoing→historical transition — main.js's season
    // "change" handler already forces resetThresholdOnNextRange for that
    // case via resetThresholdToCategoryDefault(), so this branch won't even
    // run for it) — keep the user's value if it still fits; otherwise fall
    // back to this season's configured default rather than the new slice's
    // raw max (see updatePendingThresholdMax()'s matching comment — same
    // bug, same fix, just the Apply-time copy of it).
    const defaultValue = cat.default_thresholds[els.season.value] ?? 0;
    els.threshold.max = max;
    els.thresholdNumber.max = max;
    els.threshold.value = Math.min(Math.max(defaultValue, 0), max);
  }
  // else: the current value still fits under the new max, and nothing
  // forced a default reset — leave .max/.thresholdNumber.max exactly as
  // they are so the bar doesn't move for a change that isn't there.

  els.thresholdNumber.value = els.threshold.value;
}

// Fired immediately on a Category switch only (main.js's attachEvents()) —
// unlike every other Season/Position case in updateThresholdRange() above,
// which only clamps the user's existing value. A Category switch needs an
// *instant* correction because the outgoing and incoming threshold scales
// aren't comparable at all (PR Opp vs Non Spike PB Snaps) — leaving the
// outgoing category's number on screen even for the beat it'd take a fetch
// to resolve would be actively misleading (wrong units, not just a stale
// number). A Season switch has no such units mismatch, so it doesn't call
// this — see main.js's season "change" handler and
// updatePendingThresholdMax()'s matching branch for why it waits for real
// fetched data instead of guessing a placeholder here (guessing was tried;
// it could pin the slider at the far-right edge for however long the fetch
// took, then visibly snap back once corrected). Always snaps to the new
// category's configured default for whatever season is currently selected
// (see config.py's resolve_default_threshold — a season may carry a static
// or dynamic default) and never tries to preserve whatever the user had
// set beforehand. The accurate slider max (which needs the new category's
// fetched data) still gets corrected as soon as it's available via
// updatePendingThresholdMax(), and again at Apply time via
// loadCurrentSlice()/updateThresholdRange() — this only fixes what's on
// screen immediately, as a rough placeholder. Sets both the slider and the
// number input together so they can never fall out of sync with each
// other, same as every other place both controls change at once.
export function resetThresholdToCategoryDefault() {
  const cat = currentCategoryMeta();
  const defaultValue = cat.default_thresholds[els.season.value] ?? 0;
  // The outgoing category's slider max may be smaller than the incoming
  // default (e.g. a narrow DL pool's max sitting below OL's 300 default) —
  // extend it so the browser doesn't silently clamp the value we're about
  // to set. loadCurrentSlice() overwrites this with the real max at Apply.
  if (Number(els.threshold.max) < defaultValue) {
    els.threshold.max = defaultValue;
    els.thresholdNumber.max = defaultValue;
  }
  els.threshold.value = defaultValue;
  els.thresholdNumber.value = defaultValue;
}

export function closeFiltersDrawer() {
  els.filtersDrawer.classList.remove("open");
  els.filtersToggle.setAttribute("aria-expanded", "false");
}

// The one entry point that turns pending control values into what's
// actually plotted — fires on Apply click or Enter in the threshold field,
// batching however many of category/season/position/axes/threshold the
// user changed since the last apply into a single fetch + render.
export async function applyFilters() {
  const sliceChanged =
    els.category.value !== appliedFilters.category ||
    els.season.value !== appliedFilters.season ||
    els.position.value !== appliedFilters.position;
  // Threshold isn't part of sliceChanged (no refetch needed — currentRecords
  // already holds every threshold value), but it does change which rows
  // clear the bar, so it still invalidates the Workspace (Single Cards +
  // Merged Cards) exactly like a slice change does
  // (BLUEPRINT_PinnedPlayers.md §9 — a broader rule than the base
  // BLUEPRINT.md §4's Merge-Card-only version it supersedes). Axes/Teams/
  // Players deliberately don't participate here — none of them affect
  // currentFiltered/positionPool, see the "do NOT invalidate" list in §4/§9.
  const thresholdChanged = els.thresholdNumber.value !== appliedFilters.threshold;
  const poolChanged = sliceChanged || thresholdChanged;

  const workspaceNonEmpty = workspaceSingles.size > 0 || mergeCards.size > 0;
  if (poolChanged && workspaceNonEmpty) {
    const proceed = await showMergeInvalidationConfirm();
    if (!proceed) return; // Cancel aborts entirely — pending controls stay lit, nothing is fetched or cleared.
  }
  if (poolChanged) {
    clearWorkspace();
  }

  // A season/category/position change invalidates Linemate Cards outright
  // (different roster of possible linemates entirely) — a threshold-only
  // change doesn't get the same treatment: refreshOpenLinemateCards() below
  // recomputes each open one's roster/percentiles in place instead. Player
  // Cards no longer get a separate closeAllScoutCards() call here — they're
  // already covered by clearWorkspace() above whenever poolChanged, and
  // sliceChanged is always a poolChanged too.
  if (sliceChanged) {
    clearLinemateCards();
    await loadCurrentSlice(); // may also reset/clamp the threshold controls
  }

  // A season/position/category switch (or a threshold edit that slipped in
  // without a live prune) can leave stale chips pointing at players outside
  // the new qualifying pool — drop them before snapshotting into
  // appliedFilters so the chart never highlights a player who isn't there.
  prunePlayerSelections();
  // setAppliedFilters() replaces the original's direct `appliedFilters =`
  // assignment — see the comment in loadCurrentSlice() above for why.
  setAppliedFilters(currentFilterState());
  closeFiltersDrawer();
  render();
  // Refreshes whatever Player/Linemate Cards are still open against the
  // filters just applied — covers the threshold-only case above (ranks are
  // computed against currentFiltered, which a threshold change moves).
  // No-ops cleanly if sliceChanged already closed everything, and on a pure
  // axes-only Apply too, since a Player Card's stat rows don't depend on
  // which metrics are currently plotted.
  refreshOpenScoutCards();
  refreshOpenLinemateCards();
  updatePendingState();
}
