/* Pinned Players — persistent Workspace orchestration layer. Sits above
 * scout-card.js and merge-card.js, calling into both. Extracted from app.js
 * per MODULARIZATION.md v1.3.0 §2/§3 step 7.
 *
 * clearMergeCards() lives here rather than in merge-card.js (which owns the
 * mergeCards map it operates on) because its only caller, clearWorkspace(),
 * is workspace.js's own, and it ends by calling renderPlayerCardsSpace() —
 * same call-graph reasoning as the circular import documented in
 * merge-card.js's header. Keeping it here avoids yet another edge back
 * into workspace.js for a function nothing outside this file calls.
 */
import { els } from "./dom.js";
import { logoSrc, teamSwatch, findRecordByPlayer } from "./data.js";
import { searchPlayersExcluding, pcsSearchPool } from "./search.js";
import { MERGE_QUOTA } from "./config.js";
import { withTrailingPeriod, isDesktopScoutLayout, updateScoutEmptyHint } from "./cards-base.js";
import {
  scoutCards,
  closeScoutCard,
  closeAllScoutCards,
  openScoutCard,
  flashFloatingCard,
} from "./scout-card.js";
import {
  workspaceSingles,
  mergeCards,
  distinctWorkspacePlayers,
  reopenOrFocusMergeCard,
  openMergeEditPopup,
  closeMergeCard,
} from "./merge-card.js";

// --- Pinned Players: Workspace admission/removal ------------------------
// (BLUEPRINT_PinnedPlayers.md §3/§4)

// Pops up a reminder for a quota/cap refusal (Workspace full, Merge Card
// 5-member cap, Merge 8-player limit) — reused everywhere one of those
// decisions needs to explain itself. Was an easy-to-miss inline message in
// Pinned Players' compact bar; a popup can't go unnoticed regardless of which
// control triggered it, and there's no "clear the message" case to track
// anymore since it dismisses itself via its own OK button.
export function showWorkspaceNotice(text) {
  els.workspaceNoticeBody.textContent = text;
  els.workspaceNoticeOverlay.hidden = false;
  const onOk = () => {
    els.workspaceNoticeOverlay.hidden = true;
    els.workspaceNoticeOk.removeEventListener("click", onOk);
  };
  els.workspaceNoticeOk.addEventListener("click", onOk);
}

// Single Cards' only entry point now (v1.2.0 §4) — the fuzzy-search box at
// the top of the column, NOT the plot (see viewFloatingCard()) and NOT a
// per-row Merge action (removed, v1.2.0 §5's Create popup replaces it).
// Deliberately does not open the floating card — that stays the job of
// clicking the player's name in the list once he's added, an existing,
// unchanged behavior (see the row click handler in renderSinglesList()).
export function addPlayerToSingleCards(record) {
  const key = record.player;
  if (workspaceSingles.has(key)) return;

  const distinct = distinctWorkspacePlayers();
  if (!distinct.has(key) && distinct.size >= MERGE_QUOTA) {
    showWorkspaceNotice(
      `Workspace full (${MERGE_QUOTA}/${MERGE_QUOTA}) — remove a player to add ${withTrailingPeriod(record.abbr_name || key)}`
    );
    return;
  }

  workspaceSingles.set(key, record);
  renderPlayerCardsSpace();
}

// Single Cards "Remove" (§4) — exits the Workspace entirely: drops the row
// and closes the floating card if it's open (decision 3). Does NOT touch any
// Merge Card the player still belongs to (§4/§6) — his stats there keep
// coming from findRecordByPlayer().
export function removeSingleCard(key) {
  if (!workspaceSingles.has(key)) return;
  workspaceSingles.delete(key);
  closeScoutCard(key);
  renderPlayerCardsSpace();
}

// --- Single Cards add-search (v1.2.0 §4) ------------------------------------
// Pinned Players' only entry point now. Same fuzzy-match style/behavior as the
// Players filter (mirrors runPlayersSearch()/renderPlayersDropdown()), just
// against pcsSearchPool() and excluding players already on the Workspace.

export function hidePcsAddDropdown() {
  els.pcsAddDropdown.hidden = true;
  els.pcsAddDropdown.innerHTML = "";
}

export function renderPcsAddDropdown(matches) {
  els.pcsAddDropdown.innerHTML = "";
  if (!matches.length) {
    hidePcsAddDropdown();
    return;
  }

  matches.forEach((record) => {
    const opt = document.createElement("button");
    opt.type = "button";
    opt.className = "player-option";

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
      addPlayerToSingleCards(record);
      els.pcsAddInput.value = "";
      els.pcsAddInput.focus();
      runPcsAddSearch();
    });

    els.pcsAddDropdown.appendChild(opt);
  });

  els.pcsAddDropdown.hidden = false;
}

export function runPcsAddSearch() {
  const query = els.pcsAddInput.value.trim();
  if (!query) {
    hidePcsAddDropdown();
    return;
  }
  renderPcsAddDropdown(searchPlayersExcluding(query, pcsSearchPool(), new Set(workspaceSingles.keys())));
}

// Dissolves every Merge Card — the pool invalidation from BLUEPRINT.md §4
// (season/category/position/threshold changes). Called from applyFilters()
// once any confirm prompt it needed has already resolved. Merge Cards still
// dissolve on every pool change, threshold included: refreshing up to 5
// players' percentiles in place, possibly spanning multiple positions, is
// more surface area than the confirm-and-rebuild UX already buys the user.
// Linemate Cards don't share this — see refreshOpenLinemateCards() in
// applyFilters().
export function clearMergeCards() {
  mergeCards.forEach((entry) => entry.el && entry.el.remove());
  mergeCards.clear();
  updateScoutEmptyHint();
  renderPlayerCardsSpace();
}

// --- Pinned Players UI (BLUEPRINT_PinnedPlayers.md) ------------------

// Pinned Players (quota bar + Single Cards / Merged Cards columns) is always
// visible on desktop/tablet — unlike the old merge-toolbar it replaces, its
// visibility isn't gated on any card being open (§2: "the quota counter
// stays visible in BOTH [collapsed/expanded] states"). Called from every
// place workspaceSingles/mergeCards change, plus the resize handler for the
// breakpoint crossing. The Create button (v1.2.0 §5) is a static control —
// no selection-count/disabled state to keep in sync here anymore, since the
// Create popup runs its own checks at Submit time.
export function renderPlayerCardsSpace() {
  const visible = isDesktopScoutLayout();
  els.playerCardsSpace.hidden = !visible;
  if (!visible) return;

  const distinct = distinctWorkspacePlayers();
  els.pcsQuotaLabel.textContent = `📍PINNED: ${distinct.size} / ${MERGE_QUOTA} Distinct Players.`;

  renderSinglesList();
  renderMergedList();
}

// Single Cards column (§1/§4): one row per Workspace player, name/team +
// Remove (exits the Workspace). Entry is via the add-search box above the
// list (runPcsAddSearch()/addPlayerToSingleCards()), not a plot click and
// not a per-row Merge action (v1.2.0 §4/§5 — see the Create popup instead).
export function renderSinglesList() {
  const empty = workspaceSingles.size === 0;
  els.pcsSinglesList.hidden = empty;
  els.pcsSinglesList.innerHTML = "";
  if (empty) return;

  workspaceSingles.forEach((record, key) => {
    const row = document.createElement("div");
    row.className = "pcs-row pcs-row--single is-clickable";
    row.dataset.player = key;
    // Reopens the floating card if it's been closed, or brings it to front
    // (scrolled into view) if it's already open somewhere off-screen — this
    // existing behavior is unchanged/reused as-is (v1.2.0 §4). Remove stops
    // propagation so it keeps its own single-purpose click.
    row.addEventListener("click", () => {
      if (scoutCards.has(key)) {
        flashFloatingCard(key);
      } else {
        openScoutCard(record);
      }
    });

    const name = document.createElement("span");
    name.className = "pcs-row-name";
    name.textContent = record.abbr_name || key;
    row.appendChild(name);

    const meta = document.createElement("span");
    meta.className = "pcs-row-meta";
    meta.textContent = `${record.team} · ${record.position}`;
    row.appendChild(meta);

    const spacer = document.createElement("span");
    spacer.className = "pcs-row-spacer";
    row.appendChild(spacer);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "pcs-row-remove";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      removeSingleCard(key);
    });
    row.appendChild(removeBtn);

    els.pcsSinglesList.appendChild(row);
  });
}

// Merged Cards column (§1/§5): one row per Merge Card — open or closed, see
// closeMergeCardFloating() — a short member-name summary + Edit (membership
// popup) + Dismiss (closeMergeCard, the only full dissolve). The row itself
// is clickable to reopen/focus the floating card, same "admit or focus"
// pattern as Single Cards rows.
export function renderMergedList() {
  const empty = mergeCards.size === 0;
  els.pcsMergedEmpty.hidden = !empty;
  els.pcsMergedList.hidden = empty;
  els.pcsMergedList.innerHTML = "";
  if (empty) return;

  mergeCards.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "pcs-row is-clickable";
    row.dataset.id = entry.id;
    row.addEventListener("click", () => reopenOrFocusMergeCard(entry.id));

    const names = entry.memberKeys.map((key) => {
      const record = findRecordByPlayer(key);
      return (record && (record.abbr_name || record.player)) || key;
    });

    const name = document.createElement("span");
    name.className = "pcs-row-name";
    name.textContent = names.join(" · ");
    row.appendChild(name);

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "pcs-row-edit";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openMergeEditPopup(entry.id);
    });
    row.appendChild(editBtn);

    const dismissBtn = document.createElement("button");
    dismissBtn.type = "button";
    dismissBtn.className = "pcs-row-dismiss";
    dismissBtn.textContent = "Dismiss";
    dismissBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      closeMergeCard(entry.id);
    });
    row.appendChild(dismissBtn);

    els.pcsMergedList.appendChild(row);
  });
}

// Manage (§2) — a panel that expands/collapses in place, deliberately not a
// native <select>/dropdown. Manage is the only control for this now — no
// separate close button inside the panel.
export function togglePlayerCardsSpacePanel() {
  const next = els.pcsPanel.hidden;
  els.pcsPanel.hidden = !next;
  els.pcsInspectBtn.setAttribute("aria-expanded", String(next));
  els.pcsInspectBtn.classList.toggle("is-open", next);
}

// Full Workspace wipe — Single Cards + Merged Cards together, per §9's
// "Season/Category/Position/Threshold+Apply clear all Single Cards and
// Merged Cards." Linemate Cards are handled separately in applyFilters()
// (they only fully clear on a slice change, not threshold-only).
export function clearWorkspace() {
  closeAllScoutCards();
  workspaceSingles.clear();
  clearMergeCards(); // already calls renderPlayerCardsSpace()
}

// --- Pool-change confirm modal (BLUEPRINT.md §4) -----------------------------

// Resolves true (proceed) or false (cancel). Only ever shown when the
// Workspace (Single Cards and/or Merged Cards, BLUEPRINT_PinnedPlayers.md
// §9) is non-empty — Linemate Cards refresh in place instead of being
// dissolved on a threshold-only change (see refreshOpenLinemateCards() in
// applyFilters()), so they don't warrant interrupting Apply on their own.
export function showMergeInvalidationConfirm() {
  return new Promise((resolve) => {
    els.mergeConfirmOverlay.hidden = false;
    const cleanup = (result) => {
      els.mergeConfirmOverlay.hidden = true;
      els.mergeConfirmCancel.removeEventListener("click", onCancel);
      els.mergeConfirmClear.removeEventListener("click", onClear);
      resolve(result);
    };
    const onCancel = () => cleanup(false);
    const onClear = () => cleanup(true);
    els.mergeConfirmCancel.addEventListener("click", onCancel);
    els.mergeConfirmClear.addEventListener("click", onClear);
  });
}
