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
import { searchPlayersExcluding, qualifyingPlayerPool } from "./search.js";
import { CONFERENCES } from "./config.js";
import { render } from "./render.js";
import { refreshOpenScoutCards } from "./scout-card.js";
import { refreshOpenLinemateCards, clearLinemateCards } from "./linemate-card.js";
import { workspaceSingles, mergeCards } from "./merge-card.js";
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
// the 150px button (see the control-players sizing comment above .control-players).
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
  if (!matches.length) {
    hidePlayersDropdown();
    return;
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
    hidePlayersDropdown();
    return;
  }
  renderPlayersDropdown(searchPlayers(query, qualifyingPlayerPool()));
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

  // Seasons (already sorted desc by the API)
  els.season.innerHTML = "";
  cat.seasons.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    els.season.appendChild(opt);
  });

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
  // Distinct defaults, mirroring the pipeline's canonical query pairs
  // (e.g. plain Win Rate vs. TPS Win Rate). Pass rush gets an explicit
  // Win Rate / Havoc Rate pairing; pass block falls back to the generic
  // non-TPS-vs-TPS heuristic.
  if (els.category.value === "pass_rush" && metricKeys.includes("Win Rate") && metricKeys.includes("Havoc Rate")) {
    els.xMetric.value = "Win Rate";
    els.yMetric.value = "Havoc Rate";
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
// without waiting for Apply.
export async function updatePlayerPool() {
  const category = els.category.value;
  const season = Number(els.season.value);
  // setPlayerPool() — see the comment in loadCurrentSlice() above.
  setPlayerPool(await fetchSlice(category, season), category);
  prunePlayerSelections();
  runPlayersSearch();
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
  els.threshold.max = max;
  els.threshold.step = 5;

  if (resetThresholdOnNextRange) {
    const defaultValue = cat.default_threshold ?? 0;
    els.threshold.value = Math.min(Math.max(defaultValue, 0), max);
    resetThresholdOnNextRange = false;
  } else if (Number(els.threshold.value) > max) {
    // Season/position change within the same category — keep the user's
    // value, only clamping if the new slice's max no longer covers it.
    els.threshold.value = max;
  }

  els.thresholdNumber.min = 0;
  els.thresholdNumber.max = max;
  els.thresholdNumber.value = els.threshold.value;
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
  // filters just applied — covers both the threshold-only case above and an
  // axes-only Apply (a card's X/Y-highlighted stat row was similarly never
  // rebuilt after open before this). No-ops cleanly if sliceChanged already
  // closed everything.
  refreshOpenScoutCards();
  refreshOpenLinemateCards();
  updatePendingState();
}
