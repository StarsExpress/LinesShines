/* Entry point: event wiring (attachEvents) and module composition
 * (loadMetadata, the boot call at the bottom). Extracted from app.js per
 * MODULARIZATION.md v1.3.0 §2/§3 step 9 — the last module, depending on
 * everything above it. Loaded from index.html as <script type="module">.
 */
import { els } from "./dom.js";
import {
  currentRecords,
  currentSliceCategory,
  appliedFilters,
  setMetadata,
  setPlayerPool,
  setAppliedFilters,
  preloadLogos,
  isOngoingSeason,
} from "./data.js";
import {
  selectedPlayers,
  resetThresholdOnNextRange,
  setResetThresholdOnNextRange,
  currentFilterState,
  populateCategoryDependentControls,
  resetThresholdToCategoryDefault,
  populateTeamsChecklist,
  updateTeamsSummary,
  openTeamsDropdown,
  closeTeamsDropdown,
  renderPlayerChips,
  openPlayersPanel,
  closePlayersPanel,
  hidePlayersDropdown,
  runPlayersSearch,
  closeBelowThresholdPopup,
  prunePlayerSelections,
  updatePendingState,
  updatePlayerPool,
  loadCurrentSlice,
  closeFiltersDrawer,
  applyFilters,
} from "./filters.js";
import { render, setLogoRelayoutGuard } from "./render.js";
import { exportChartPngWithFooter, sanitizeForFilename } from "./chart-export.js";
import { createInfoPopover } from "./info-popover.js";
import { isDesktopScoutLayout, clearScoutCardDragPositions } from "./cards-base.js";
import {
  openCreateMergePopup,
  closeCreateMergePopup,
  submitCreateMergePopup,
  runCreateSearch,
  hideCreateDropdown,
  runMergeEditSearch,
  hideMergeEditDropdown,
  closeMergeEditPopup,
  workspaceSingles,
  mergeCards,
} from "./merge-card.js";
import {
  renderPlayerCardsSpace,
  togglePlayerCardsSpacePanel,
  runPcsAddSearch,
  hidePcsAddDropdown,
} from "./workspace.js";

// Tracks whatever Season value was last settled (either by the user picking
// one, or a category switch's own season-select rebuild) so the season
// "change" handler below can tell an ongoing→historical transition apart
// from every other one — a plain els.season.value read inside that handler
// only ever sees the *new* value, never what it was a moment ago. Synced
// in three places: right after the initial load, at the end of a category
// switch (which can silently rebuild/reset the season <select>), and at the
// end of every season "change" event itself.
let previousSeasonValue = null;

async function loadMetadata() {
  const res = await fetch("/api/metadata");
  if (!res.ok) throw new Error(`GET /api/metadata → ${res.status}`);
  // setMetadata()/setPlayerPool()/setAppliedFilters() replace the original's
  // direct assignments below — data.js owns that state now, see its header
  // comment for why. Same assignments, same order, same timing.
  setMetadata(await res.json());

  populateCategoryDependentControls();
  previousSeasonValue = els.season.value;
  populateTeamsChecklist();
  attachEvents();
  await loadCurrentSlice();
  setPlayerPool(currentRecords, currentSliceCategory);
  setAppliedFilters(currentFilterState());

  els.logoPreload.hidden = false;
  await preloadLogos();
  els.logoPreload.hidden = true;

  render();
  renderPlayerCardsSpace();
  updatePendingState();
}

function attachEvents() {
  els.playersInfoSlot.appendChild(
    createInfoPopover(
      "Teams and Players combine as a union: a player is highlighted if either his team is chosen, or his name is selected.",
      { label: "Players", labelId: "players-label" }
    )
  );

  // Category/season/position/axes are all pending-only for the chart: picking
  // a new value just updates the control itself (plus, for category, the
  // option lists that depend on it) and lights up Apply — nothing fetches or
  // re-renders the chart until applyFilters() runs, so the user can change
  // several of these together and commit them in one shot. Category/season/
  // position additionally trigger updatePlayerPool() live (unlike the chart),
  // since the Players search pool is cheap to keep in sync with whatever
  // position is currently selected rather than making it wait for Apply too.
  els.category.addEventListener("change", () => {
    setResetThresholdOnNextRange(true);
    populateCategoryDependentControls();
    // Snaps the slider + number input to the new category's default right
    // away, rather than waiting for Apply — see resetThresholdToCategoryDefault()'s
    // comment for why this can't wait like season/position changes do.
    resetThresholdToCategoryDefault();
    // populateCategoryDependentControls() can silently rebuild/reset the
    // Season <select> (a category doesn't necessarily offer the season that
    // was previously picked) — resync so the season "change" handler below
    // compares against what's actually on screen now, not a stale value
    // from before this category switch.
    previousSeasonValue = els.season.value;
    updatePendingState();
    updatePlayerPool();
  });

  els.season.addEventListener("change", () => {
    // Ongoing → historical: the ongoing season's threshold sits on a scale
    // shaped by however much of the season has actually been played, not a
    // comparable number for a finalized season — carrying it over would
    // either read as an oddly low cutoff or get silently clamped to an
    // arbitrary pool max, never the historical default anyone actually
    // configured. Historical → historical shares one static default across
    // every finalized season (DEFAULT_THRESHOLDS), so there's nothing
    // meaningful to snap to — leave the user's value alone.
    //
    // Deliberately does NOT call resetThresholdToCategoryDefault() here the
    // way the Category handler above does — only sets the flag and lets
    // updatePendingThresholdMax() (fired by updatePlayerPool() below, once
    // its fetch actually resolves with this season's real data) apply the
    // new default and its real max together in one atomic write. Calling
    // resetThresholdToCategoryDefault() synchronously here too used to grow
    // .max just far enough to fit the new default off of whatever pending
    // data happened to already be on hand (the outgoing season's, not the
    // incoming one's) — close enough to the new value that it could pin the
    // slider handle at the far-right edge for however long the fetch took,
    // then visibly snap back once the real max landed. A Category switch
    // still needs that synchronous call (see its own comment — leaving the
    // wrong category's number/units on screen is actively misleading, a
    // worse sin than a brief stale value), but a Season switch has no such
    // units mismatch, so there's nothing lost by just waiting the beat for
    // real data instead of flashing a wrong guess first.
    if (isOngoingSeason(previousSeasonValue) && !isOngoingSeason(els.season.value)) {
      setResetThresholdOnNextRange(true);
    }
    previousSeasonValue = els.season.value;
    updatePendingState();
    updatePlayerPool();
  });

  els.position.addEventListener("change", () => {
    updatePendingState();
    updatePlayerPool();
  });

  [els.xMetric, els.yMetric].forEach((el) =>
    el.addEventListener("change", updatePendingState)
  );

  // Teams: pending-only like every other filter above — picking teams just
  // updates the summary label and lights up Apply; the chart doesn't
  // refilter until applyFilters() runs.
  els.teamsBtn.addEventListener("click", () => {
    if (els.teamsDropdown.hidden) openTeamsDropdown();
    else closeTeamsDropdown();
  });

  els.teamsSelectAll.addEventListener("click", () => {
    els.teamsChecklist.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = true));
    updateTeamsSummary();
    updatePendingState();
  });

  els.teamsSelectNone.addEventListener("click", () => {
    els.teamsChecklist.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = false));
    updateTeamsSummary();
    updatePendingState();
  });

  els.teamsChecklist.addEventListener("change", () => {
    updateTeamsSummary();
    updatePendingState();
  });

  // Same e.isTrusted guard as the scouting card / filters drawer listeners
  // below — protects against exportChartPngWithFooter()'s synthetic anchor
  // click, which bubbles to document as an untrusted "click" outside every
  // container and would otherwise slam this dropdown shut mid-export.
  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (els.teamsDropdown.hidden) return;
    if (!els.teamsControl.contains(e.target)) closeTeamsDropdown();
  });

  // Players: collapsed behind a button + panel, same mechanism as Teams —
  // the chip list stays hidden until opened so it never has to fit inside
  // the collapsed button's width (see the .control-players comment in
  // style.css). Pending-only like Teams otherwise: adding/removing a chip
  // just updates the selection and lights up Apply; the chart doesn't
  // re-highlight until applyFilters() runs. The search itself, though,
  // reacts live (see qualifyingPlayerPool()/prunePlayerSelections()) since
  // it's cheap client-side filtering against already-cached data, not a
  // refetch.
  els.playersBtn.addEventListener("click", () => {
    if (els.playersPanel.hidden) openPlayersPanel();
    else closePlayersPanel();
  });

  // Mirrors Teams' None button, but scoped to Players' own chip set rather
  // than a shared checklist — clears every selected player in one click
  // regardless of whether the panel is open, then re-runs the live search
  // so any just-cleared player can immediately reappear as a suggestion.
  els.playersResetBtn.addEventListener("click", () => {
    if (!selectedPlayers.size) return;
    selectedPlayers.clear();
    renderPlayerChips();
    updatePendingState();
    runPlayersSearch();
  });

  els.playersInput.addEventListener("input", runPlayersSearch);

  els.playersInput.addEventListener("focus", () => {
    if (els.playersInput.value.trim()) runPlayersSearch();
  });

  els.playersInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      // Autocomplete convention: Escape backs out one level at a time —
      // first close just the suggestion list, and only close the whole
      // panel if the suggestions were already closed.
      if (!els.playersDropdown.hidden) hidePlayersDropdown();
      else closePlayersPanel();
    } else if (e.key === "Enter") {
      // Autocomplete convention: Enter commits the top suggestion, same as
      // a click on it.
      e.preventDefault();
      const first = els.playersDropdown.querySelector(".player-option");
      if (first) first.click();
    }
  });

  // Same e.isTrusted guard as the Teams/filters-drawer listeners — see the
  // comment above the Teams one for why. Uses composedPath() rather than
  // playersControl.contains(e.target): picking a suggestion calls
  // hidePlayersDropdown(), which clears the suggestion list's innerHTML
  // (removing the very button just clicked) before this bubbled listener
  // runs — contains() on a now-detached node always returns false, which
  // was slamming the whole panel shut on every single pick. composedPath()
  // is captured at dispatch time, before that mutation, so it still
  // includes playersControl.
  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (els.playersPanel.hidden) return;
    if (!e.composedPath().includes(els.playersControl)) closePlayersPanel();
  });

  // Dragging the slider or typing a number only updates these two controls'
  // own displayed values — the chart holds its current state until the user
  // clicks Apply (or presses Enter in the number field). Re-rendering on
  // every pixel of drag / every keystroke was the whole problem on dense
  // positions.
  els.threshold.addEventListener("input", () => {
    els.thresholdNumber.value = els.threshold.value;
    // The user just gave an explicit threshold — don't let a pending
    // category switch stomp it back to that category's default at Apply
    // time (see the resetThresholdOnNextRange comment above its declaration).
    setResetThresholdOnNextRange(false);
    // The Players pool is threshold-gated live (not just at Apply) — see
    // qualifyingPlayerPool() — so a chip that no longer clears the new
    // value should disappear the moment the slider moves, not linger until
    // Apply.
    prunePlayerSelections();
    updatePendingState();
  });

  els.thresholdNumber.addEventListener("input", () => {
    const min = Number(els.threshold.min);
    const max = Number(els.threshold.max);
    const step = Number(els.threshold.step) || 1;

    let raw = Number(els.thresholdNumber.value);
    if (Number.isNaN(raw)) raw = min;
    raw = Math.min(Math.max(raw, min), max);
    els.thresholdNumber.value = raw;

    // Slider snaps to the nearest step just to keep the handle in sync
    // visually — filtering below still uses the exact typed number.
    els.threshold.value = min + Math.round((raw - min) / step) * step;
    setResetThresholdOnNextRange(false);
    prunePlayerSelections();
    updatePendingState();
  });

  els.thresholdNumber.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    applyFilters();
  });

  els.applyBtn.addEventListener("click", applyFilters);

  // Exports exactly what's on screen — built from appliedFilters (the
  // last-committed state render() actually drew), not the live controls,
  // so a pending-but-not-applied axis/season change can't leak into the
  // downloaded filename or image.
  els.savePngBtn.addEventListener("click", () => {
    if (els.savePngBtn.disabled) return;
    const season = appliedFilters.season;
    const position = sanitizeForFilename(appliedFilters.position);
    const xMetric = sanitizeForFilename(appliedFilters.xMetric);
    const yMetric = sanitizeForFilename(appliedFilters.yMetric);
    const filename = `LinesShines_${season}_${position}_${xMetric}_vs_${yMetric}`;

    // paper/plot bgcolor are "transparent" on screen — the chart relies on
    // .chart-panel's dark CSS behind it (see style.css --turf-800). A raster
    // export has no page behind it, so a transparent export composites onto
    // whatever's behind it when opened (white, on most viewers/socials),
    // which washes out the low-opacity gridlines/labels designed for a dark
    // background. Swap in the panel's actual color just for the export, then
    // restore transparency so on-screen zoom/pan is unaffected. The guard
    // suppresses the logo/label relayout handler from reacting to the first
    // (dark-swap) bookkeeping relayout — harmless to skip reacting to, since
    // the chart's about to be captured then immediately restored anyway.
    els.savePngBtn.disabled = true;
    setLogoRelayoutGuard(true);
    Plotly.relayout(els.chart, { paper_bgcolor: "#16301f", plot_bgcolor: "#16301f" })
      .then(() =>
        // `width`/`height` set Plotly's *logical* layout size — every fixed-px
        // font (marker labels, axis titles, median/note annotations) is sized
        // relative to that, not to the final image resolution. `scale` is a
        // separate post-render pixel-density multiplier that leaves those
        // proportions alone. The on-screen chart renders at ~1100x720, so a
        // straight width:2400/height:1500/scale:1 export (a ~2.2x larger
        // logical canvas) made every label look shrunken relative to the chart
        // even though the file itself was high-res. Keeping the logical size
        // close to the real on-screen size and reaching the same 2400x1500
        // output via scale:2 instead makes exported text match what's on
        // screen while keeping the image just as crisp.
        exportChartPngWithFooter(els.chart, {
          filename,
          width: 1200,
          height: 750,
          scale: 2,
        })
      )
      .then(() => {
        // Unguarded *before* this second relayout, not after: any relayout
        // — even one that only touches bgcolor — can make Plotly regenerate
        // some <text> DOM nodes as part of its normal redraw, which silently
        // strips applyLabelEmphasis()'s manually-added inline styles (Plotly
        // has no idea they're there, since they're not part of its own trace
        // config). Leaving the guard up here left some spotlighted labels
        // stuck without their halo after every export (confirmed directly).
        // Unguarding first lets render.js's own plotly_relayout listener
        // catch this relayout and do its normal, already-correct
        // applyLogoImages()/applyLabelDeclutter() pass — which re-applies
        // emphasis — rather than duplicating that recovery logic here.
        setLogoRelayoutGuard(false);
        return Plotly.relayout(els.chart, { paper_bgcolor: "transparent", plot_bgcolor: "transparent" });
      })
      .finally(() => {
        els.savePngBtn.disabled = false;
      });
  });

  els.labelsToggle.addEventListener("change", render);
  els.logosToggle.addEventListener("change", render);

  // Per-card close/drag listeners are wired up inside openScoutCard() itself
  // — each cloned card owns its own close button and drag handle — so
  // there's no single static card to attach listeners to here anymore.

  // A drag position is only valid in the desktop overlay layout — resizing
  // past the breakpoint mid-session (or a device rotation) needs every
  // currently-open card's inline position stripped so the mobile stacked
  // layout can take back over, see clearScoutCardDragPositions().
  window.addEventListener("resize", () => {
    if (!isDesktopScoutLayout()) clearScoutCardDragPositions();
    // Merge/Linemate cards and Pinned Players are desktop/tablet-only
    // (BLUEPRINT.md §0) — a resize across the 860px breakpoint needs to
    // re-evaluate Pinned Players' own visibility either way.
    renderPlayerCardsSpace();
  });

  // Pinned Players collapse/expand (§2) — Manage does both, no separate
  // close control inside the panel anymore.
  els.pcsInspectBtn.addEventListener("click", () => togglePlayerCardsSpacePanel());

  // Single Cards add-search (v1.2.0 §4) — same fuzzy-input conventions as
  // the Players filter (input fires the live search; Enter commits the top
  // suggestion; Escape backs out of the dropdown).
  els.pcsAddInput.addEventListener("input", runPcsAddSearch);
  els.pcsAddInput.addEventListener("focus", () => {
    if (els.pcsAddInput.value.trim()) runPcsAddSearch();
  });
  els.pcsAddInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      hidePcsAddDropdown();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const first = els.pcsAddDropdown.querySelector(".player-option");
      if (first) first.click();
    }
  });

  // Create-merge popup (v1.2.0 §5) — replaces the old header Merge button.
  els.pcsCreateBtn.addEventListener("click", openCreateMergePopup);
  els.mergeCreateCancel.addEventListener("click", closeCreateMergePopup);
  els.mergeCreateSubmit.addEventListener("click", submitCreateMergePopup);
  els.mergeCreateInput.addEventListener("input", runCreateSearch);
  els.mergeCreateInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!els.mergeCreateDropdown.hidden) hideCreateDropdown();
      else closeCreateMergePopup();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const first = els.mergeCreateDropdown.querySelector(".player-option");
      if (first) first.click();
    }
  });

  // Merge Card membership editor (§5) — same fuzzy-input conventions as the
  // Players filter (input fires the live search; Enter commits the top
  // suggestion; Escape backs out one level at a time).
  els.mergeEditInput.addEventListener("input", runMergeEditSearch);
  els.mergeEditInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!els.mergeEditDropdown.hidden) hideMergeEditDropdown();
      else closeMergeEditPopup();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const first = els.mergeEditDropdown.querySelector(".player-option");
      if (first) first.click();
    }
  });
  els.mergeEditDone.addEventListener("click", closeMergeEditPopup);

  // Below Threshold Matches popup — see openBelowThresholdPopup() in
  // filters.js. Same "closes only via its own button" convention as the
  // merge-edit overlays above.
  els.belowThresholdClose.addEventListener("click", closeBelowThresholdPopup);

  // Deliberately no "click outside closes the card" handler here, unlike the
  // Teams/Players dropdowns and the filters drawer below. Those are
  // transient single-purpose overlays where dismissing on an outside click
  // is the expected pattern; scouting cards are meant to stay pinned — any
  // number open at once, see openScoutCard() — until the user explicitly
  // hits a card's own ×. Auto-closing all of them on an incidental click
  // elsewhere on the chart would undercut the whole point of letting
  // several stay open side by side.

  els.filtersToggle.addEventListener("click", () => {
    const isOpen = els.filtersDrawer.classList.toggle("open");
    els.filtersToggle.setAttribute("aria-expanded", String(isOpen));
  });

  // Same e.isTrusted guard as the Teams/Players dropdown listeners above —
  // it protects against exportChartPngWithFooter()'s download trigger: it
  // builds a throwaway <a>, appends it to <body>, and calls .click() on it
  // to trigger the browser's save dialog. That programmatic click bubbles
  // to document as a real "click" event with a target outside the drawer,
  // which — without this guard — closed the mobile filters drawer
  // immediately after Save Plot, even though Save Plot is supposed to leave
  // the drawer open for repeated exports. Synthetic (script-dispatched)
  // events always report isTrusted: false, so filtering on it distinguishes
  // the export's anchor click from an actual user tap outside the drawer.
  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (!els.filtersDrawer.classList.contains("open")) return;
    if (els.filtersDrawer.contains(e.target) || els.filtersToggle.contains(e.target)) return;
    closeFiltersDrawer();
  });

  // Refresh/close silently wipes the whole Workspace (BLUEPRINT_PinnedPlayers.md
  // §7) — warn first so that isn't a silent loss of deliberate work. Skipped
  // when the Workspace is empty (nothing to lose), same "skip unless
  // non-empty" convention as showMergeInvalidationConfirm() above.
  window.addEventListener("beforeunload", (e) => {
    if (workspaceSingles.size === 0 && mergeCards.size === 0) return;
    e.preventDefault();
    e.returnValue = "";
  });
}

loadMetadata().catch((err) => {
  console.error(err);
  els.chart.innerHTML =
    `<p style="color:#f1ecdd;padding:24px;">Could not load /api/metadata — ` +
    `is the FastAPI server running? (${err.message})</p>`;
});
