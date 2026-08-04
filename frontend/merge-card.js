/* Merge Cards — Create/Edit popups, floating card body, and the Pinned
 * Players Workspace's Single Cards state (workspaceSingles) + the quota
 * helper that reads it (distinctWorkspacePlayers()). Extracted from app.js
 * per MODULARIZATION.md v1.3.0 §2/§3 step 6.
 *
 * Two deliberate deviations from the brief's literal file listing, both
 * forced by the ORIGINAL code's own call graph (not introduced by this
 * split):
 *
 * 1. workspaceSingles (the Map) and distinctWorkspacePlayers() live here
 *    rather than in workspace.js as the brief's bullet list suggests.
 *    submitCreateMergePopup() and addMergeMember() — both firmly
 *    merge-card.js's own logic — call distinctWorkspacePlayers() directly,
 *    and it needs to read workspaceSingles. Since workspace.js depends on
 *    merge-card.js (not the reverse, per the brief's own dependency
 *    graph), the Map and its quota helper have to live on the
 *    lower/merge-card.js side of that edge for workspace.js to import them
 *    without a cycle. workspace.js imports both from here.
 *
 * 2. openMergeCard(), closeMergeCard(), closeMergeEditPopup(),
 *    addMergeMember(), and removeMergeMember() all call
 *    renderPlayerCardsSpace() directly, in the original app.js as much as
 *    here — every Merge Card mutation needs the Pinned Players column to
 *    re-render. That makes merge-card.js <-> workspace.js a genuine
 *    two-way relationship already present in app.js, so this import is a
 *    deliberate, safe circular import (function-body-only, same
 *    reasoning as cards-base.js's — see the comment there), not one this
 *    split introduces.
 */
import { els } from "./dom.js";
import {
  appliedCategoryMeta,
  positionPool,
  rankAndPercentile,
  logoSrc,
  teamSwatch,
  findRecordByPlayer,
} from "./data.js";
import { searchPlayersExcluding, pcsSearchPool } from "./search.js";
import { MERGE_CARD_MAX_MEMBERS, MERGE_QUOTA } from "./config.js";
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
  withTrailingPeriod,
} from "./cards-base.js";
import { toggleLinemateCard, closeLinemateCard, attachAppTooltip } from "./linemate-card.js";
import { renderPlayerCardsSpace } from "./workspace.js";

// Pinned Players Workspace (BLUEPRINT_PinnedPlayers.md §1/§3) — the
// persistent Single Cards list, keyed by the same full "player" string as
// everything else (record.player → record). Populated ONLY by the Single
// Cards fuzzy-search box (addPlayerToSingleCards(), v1.2.0 §4) — a plot click
// never touches this, see viewFloatingCard(). Deliberately independent of
// scoutCards below: a player can be listed here with his floating card
// closed, or vice versa — see removeSingleCard()/closeScoutCard(). Together
// with mergeCards' memberKeys (declared further down), this is what
// distinctWorkspacePlayers() counts against the 8-player quota.
export const workspaceSingles = new Map();

// Pending membership for the Create-merge popup (BLUEPRINT_PinnedPlayers.md
// v1.2.0 §5) — record.player → record, in pick order. Staged locally and
// discarded on Cancel; only becomes a real Merge Card on Submit
// (submitCreateMergePopup()). Unlike the Edit popup's live-commit model, so a
// half-built card never briefly exists as a real, addressable Merge Card.
export const createSelection = new Map();

// Open Merge Cards, keyed by their own generated id (never by player — a
// Merge Card has several members). Entry: { id, origin:'merge',
// memberKeys:[player,...], el, folded }.
export const mergeCards = new Map();

// The 8-player quota's universe (BLUEPRINT_PinnedPlayers.md §6): every
// distinct player in Single Cards OR any Merged Card, counted once
// regardless of how many places he appears — a player merged into three
// cards, or merged AND still a Single Cards row, still costs exactly 1 slot.
export function distinctWorkspacePlayers() {
  const keys = new Set(workspaceSingles.keys());
  mergeCards.forEach((c) => c.memberKeys.forEach((k) => keys.add(k)));
  return keys;
}

// BLUEPRINT_PinnedPlayers.md v1.2.0 §5/CHANGE 5 — order-independent
// membership hash for duplicate-card detection, keyed by player `id` (the DB
// row id, not the display name, per the spec) rather than record.player:
// two cards with the same player SET, picked in any order, must hash
// identically.
export function memberIdsKey(memberKeys) {
  const ids = memberKeys
    .map((key) => findRecordByPlayer(key))
    .filter(Boolean)
    .map((record) => record.id)
    .sort((a, b) => a - b);
  return ids.join(",");
}

// Finds an existing Merge Card whose membership hash matches `memberKeys`,
// other than `excludeId` (a card being edited must not compare against its
// own unchanged membership) — used by both the Create and Edit popups to
// block a membership that would produce two identical cards.
export function findDuplicateMergeCard(memberKeys, excludeId) {
  const key = memberIdsKey(memberKeys);
  if (!key) return null;
  for (const [id, entry] of mergeCards) {
    if (id === excludeId) continue;
    if (memberIdsKey(entry.memberKeys) === key) return entry;
  }
  return null;
}

// --- Player Merge Cards ------------------------------------------------------
// (BLUEPRINT.md §1, BLUEPRINT_PinnedPlayers.md §5/§6)

// --- Create Merged Card popup (v1.2.0 §5) -----------------------------------
// Replaces the old per-row Merge-button + header-Merge-button flow entirely:
// the Merged Cards column's "Create" button is now the only way to start a
// new merged card. Membership is staged in createSelection (module state,
// declared above) until Submit — Cancel discards it untouched, so a
// half-built card never briefly exists as a real, addressable Merge Card.

export function setCreateMessage(text) {
  els.mergeCreateMessage.textContent = text || "";
}

export function hideCreateDropdown() {
  els.mergeCreateDropdown.hidden = true;
  els.mergeCreateDropdown.innerHTML = "";
}

export function openCreateMergePopup() {
  createSelection.clear();
  renderCreateMembers();
  els.mergeCreateInput.value = "";
  hideCreateDropdown();
  setCreateMessage("");
  els.mergeCreateOverlay.hidden = false;
  els.mergeCreateInput.focus();
}

// Cancel — discards the staged selection outright, no card created.
export function closeCreateMergePopup() {
  createSelection.clear();
  els.mergeCreateOverlay.hidden = true;
  hideCreateDropdown();
}

export function renderCreateMembers() {
  els.mergeCreateMembers.innerHTML = "";
  createSelection.forEach((record, key) => {
    const label = record.abbr_name || record.player;

    const row = document.createElement("div");
    row.className = "merge-edit-member";

    const name = document.createElement("span");
    name.className = "merge-edit-member-name";
    name.textContent = label;
    row.appendChild(name);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "merge-edit-member-remove";
    removeBtn.setAttribute("aria-label", `Remove ${label}`);
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => removeCreateMember(key));
    row.appendChild(removeBtn);

    els.mergeCreateMembers.appendChild(row);
  });
}

// Mirrors renderMergeEditDropdown()'s markup/classes exactly (.player-option
// etc.) — same fuzzy-match input style as the Players filter (v1.2.0 §5).
export function renderCreateDropdown(matches) {
  els.mergeCreateDropdown.innerHTML = "";
  if (!matches.length) {
    hideCreateDropdown();
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
    opt.addEventListener("click", () => addCreateMember(record));

    els.mergeCreateDropdown.appendChild(opt);
  });

  els.mergeCreateDropdown.hidden = false;
}

export function runCreateSearch() {
  const query = els.mergeCreateInput.value.trim();
  if (!query) {
    hideCreateDropdown();
    return;
  }
  // No exclusion set — an already-picked player is caught (and explained) in
  // addCreateMember() instead, same "blocked, with a prompt" convention the
  // Edit popup already uses. Pool is position-scoped only (v1.2.0 §4).
  renderCreateDropdown(searchPlayersExcluding(query, pcsSearchPool(), new Set()));
}

// 5-per-card cap enforced at pick time (v1.2.0 §5) — deliberately does NOT
// check the 8-player Workspace quota here; that's a Submit-time-only check
// against the DISTINCT total (submitCreateMergePopup()), not the raw number
// picked in the popup, per the spec.
export function addCreateMember(record) {
  const key = record.player;
  if (createSelection.has(key)) {
    setCreateMessage(`${record.abbr_name || key} is already selected — pick someone else.`);
    return;
  }
  if (createSelection.size >= MERGE_CARD_MAX_MEMBERS) {
    setCreateMessage(`Merge Cards hold at most ${MERGE_CARD_MAX_MEMBERS} players — remove one first.`);
    return;
  }
  createSelection.set(key, record);
  renderCreateMembers();
  setCreateMessage("");
  els.mergeCreateInput.value = "";
  runCreateSearch();
}

export function removeCreateMember(key) {
  createSelection.delete(key);
  renderCreateMembers();
}

// Submit: the one point membership is checked against the duplicate-card
// hash and the DISTINCT-player quota (v1.2.0 §5/CHANGE 5) — a player already
// in the Workspace elsewhere costs nothing toward the 8. Mirrors
// addMergeMember()'s "surface new members as Single Cards rows too" habit,
// and — like the old performMerge() — does not open the members' floating
// cards; their Single Cards rows are enough.
export function submitCreateMergePopup() {
  if (createSelection.size < 2) {
    setCreateMessage("Select at least 2 players for a merged card.");
    return;
  }

  const memberKeys = Array.from(createSelection.keys());
  if (findDuplicateMergeCard(memberKeys, null)) {
    setCreateMessage("This merged card already exists.");
    return;
  }

  const distinct = distinctWorkspacePlayers();
  memberKeys.forEach((key) => distinct.add(key));
  if (distinct.size > MERGE_QUOTA) {
    setCreateMessage(
      `Workspace full (${MERGE_QUOTA}/${MERGE_QUOTA}) — this card would add too many new players. Remove someone first.`
    );
    return;
  }

  const memberRecords = Array.from(createSelection.values());
  memberRecords.forEach((record) => {
    if (!workspaceSingles.has(record.player)) workspaceSingles.set(record.player, record);
  });

  createSelection.clear();
  els.mergeCreateOverlay.hidden = true;
  hideCreateDropdown();
  openMergeCard(memberRecords);
}

// Metadata columns (Player, Team, Linemates) stay frozen in place while
// Games/PR Opp and the metric columns scroll horizontally, Excel
// frozen-pane style — see applyStickyMetaColumns() below.
const META_COLUMN_COUNT = 3;

// A single <td> holding this row's team logo+code — mirrors the
// .player-option-team markup used by the Create/Edit popups' search
// dropdowns (logoSrc()/teamSwatch() fallback), just inside a table cell.
export function makeTeamCell(record) {
  const td = document.createElement("td");
  td.className = "merge-table-team";

  const wrap = document.createElement("span");
  wrap.className = "merge-table-team-inner";

  const logo = document.createElement("img");
  logo.className = "merge-table-team-logo";
  logo.src = logoSrc(record.team);
  logo.alt = "";
  logo.loading = "lazy";
  logo.onerror = () => logo.replaceWith(teamSwatch(record.team));

  const code = document.createElement("span");
  code.textContent = record.team;

  wrap.append(logo, code);
  td.appendChild(wrap);
  return td;
}

// A single <td> holding this row's linemate-toggle — shared by every row in
// a Merge Card's table (BLUEPRINT.md §2.1: one linemate toggle per merged
// member, no team-level dedupe even when two members share a team).
export function makeLinemateCell(record) {
  const td = document.createElement("td");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "merge-row-linemate-toggle";
  btn.innerHTML = '<i class="fa-solid fa-people-group"></i>';
  btn.setAttribute("aria-label", `Linemates for ${record.player}`);
  btn.addEventListener("click", () => toggleLinemateCard(record));
  td.appendChild(btn);
  return td;
}

// One row per player, one column per metric, percentile-only cells
// (BLUEPRINT.md §1.2) — never the raw value, never #rank/N.
// Builds/rebuilds a Merge Card's title, subtitle, and percentile table from
// memberRecords — used both at creation (openMergeCard) and by the Edit
// popup (rebuildMergeCardFromMembers, BLUEPRINT_PinnedPlayers.md §5) to
// update an existing card in place after its membership changes, instead of
// destroying/recreating the floating card. One row per player, one column
// per metric, percentile-only cells (BLUEPRINT.md §1.2) — never the raw
// value, never #rank/N.
export function renderMergeCardBody(cardEl, memberRecords) {
  const cat = appliedCategoryMeta();
  const titleEl = cardEl.querySelector(".merge-card-title");
  const subtitleEl = cardEl.querySelector(".merge-card-subtitle");
  const poolEl = cardEl.querySelector(".merge-card-pool");
  const table = cardEl.querySelector(".merge-table");

  titleEl.textContent = `Merge Card · ${memberRecords.length} Players`;
  subtitleEl.textContent = memberRecords.map((r) => r.abbr_name || r.player).join(" + ");

  const pools = memberRecords.map((record) => ({ record, pool: positionPool(record.position) }));
  const sharedPosition = pools.every((p) => p.record.position === pools[0].record.position)
    ? pools[0].record.position
    : null;
  poolEl.textContent = sharedPosition
    ? `Percentiles calculated among ${pools[0].pool.length} ${sharedPosition}.`
    : `Percentiles calculated among ${pools
        .map((p) => `${p.pool.length} ${p.record.position} (${p.record.abbr_name || p.record.player})`)
        .join(", ")}.`;

  const metricKeys = Object.keys(cat.metrics);
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Player", "Team", "Linemates", "Games", cat.threshold_field, ...metricKeys].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  pools.forEach(({ record, pool }) => {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.className = "merge-table-name";
    nameTd.textContent = record.abbr_name || record.player;
    tr.appendChild(nameTd);

    tr.appendChild(makeTeamCell(record));
    tr.appendChild(makeLinemateCell(record));

    const gamesTd = document.createElement("td");
    gamesTd.textContent = record.games ?? "—";
    tr.appendChild(gamesTd);

    const snapsTd = document.createElement("td");
    snapsTd.textContent = record[cat.threshold_field] ?? "—";
    tr.appendChild(snapsTd);

    metricKeys.forEach((key) => {
      const meta = cat.metrics[key];
      const rank = rankAndPercentile(pool, key, meta.higher_is_better, record[key]);
      const td = document.createElement("td");
      td.className = "merge-metric-cell";
      td.textContent = rank ? ordinal(rank.percentile) : "—";
      // Displayed text stays percentile-only (BLUEPRINT.md §1.2); the exact
      // #rank/N is tooltip-only, same attachAppTooltip pattern as Linemate
      // Cards' percentile cells.
      attachAppTooltip(td, rank ? `${key}:\n#${rank.rank}/${rank.n} ${cat.positions[record.position] || record.position}` : key);
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });

  table.innerHTML = "";
  table.appendChild(thead);
  table.appendChild(tbody);

  // Deferred a frame: on first build, table is still off-DOM here (the
  // caller appends cardEl to els.scoutCards after this returns), so column
  // widths aren't measurable yet. rAF fires after that append lands.
  requestAnimationFrame(() => applyStickyMetaColumns(table));
}

// Freezes the Player/Team/Linemates columns (BLUEPRINT.md §1.2 extended) in
// place while Games/PR Opp and the metric columns scroll underneath them,
// Excel frozen-pane style. Measures each metadata column's actual rendered width
// off the header row (uniform per column across every row in a <table>) so
// it holds regardless of player-name length or which metrics are showing —
// no hardcoded pixel widths to keep in sync with content.
export function applyStickyMetaColumns(table) {
  const headerCells = table.querySelectorAll("thead th");
  if (!headerCells.length) return;

  const offsets = [];
  let left = 0;
  for (let i = 0; i < META_COLUMN_COUNT && i < headerCells.length; i++) {
    offsets.push(left);
    left += headerCells[i].getBoundingClientRect().width;
  }

  table.querySelectorAll("tr").forEach((tr) => {
    offsets.forEach((offsetLeft, i) => {
      const cell = tr.children[i];
      if (!cell) return;
      cell.classList.add("merge-table-frozen");
      cell.classList.toggle("merge-table-frozen-edge", i === offsets.length - 1);
      cell.style.left = `${offsetLeft}px`;
    });
  });
}

// Builds/mounts a Merge Card's floating DOM node onto an existing entry —
// shared by openMergeCard() (fresh entry) and reopenMergeCard() (an entry
// whose row survived a previous floating-card close, see
// closeMergeCardFloating() below). Mirrors openScoutCard()'s own DOM-build
// step; a reopen always starts from a clean node, same as a Player Card's
// own close-then-reopen, so prior resize/position/fold state doesn't carry
// over.
export function mountMergeCardElement(entry, memberRecords) {
  const cardEl = els.mergeCardTemplate.content.firstElementChild.cloneNode(true);

  const closeBtn = cardEl.querySelector(".scout-close");
  const foldBtn = cardEl.querySelector(".scout-fold");
  const dragHandle = cardEl.querySelector(".scout-drag-handle");

  renderMergeCardBody(cardEl, memberRecords);

  els.scoutCards.appendChild(cardEl);
  cascadeScoutCardPosition(cardEl); // reads openCardsCount(), so must run before entry.el is set below
  cardEl.classList.add("is-active");
  bringScoutCardToFront(cardEl);

  entry.el = cardEl;
  entry.folded = false;
  attachScoutResize(cardEl, entry);

  closeBtn.addEventListener("click", () => closeMergeCardFloating(entry.id));
  // onUnfold recomputes sticky-column offsets: if membership changed via the
  // Edit popup while this card sat folded (merge-table-wrap display:none),
  // applyStickyMetaColumns() would have measured zero-width columns — this
  // catches it back up the moment the body becomes visible again.
  foldBtn.addEventListener("click", () =>
    toggleCardFold(cardEl, entry, () => applyStickyMetaColumns(cardEl.querySelector(".merge-table")))
  );
  dragHandle.addEventListener("pointerdown", (e) => beginScoutDrag(e, cardEl));
  dragHandle.addEventListener("pointermove", onScoutDragMove);
  dragHandle.addEventListener("pointerup", endScoutDrag);
  dragHandle.addEventListener("pointercancel", endScoutDrag);
  cardEl.addEventListener("pointerdown", () => bringScoutCardToFront(cardEl));

  updateScoutEmptyHint();
}

export function openMergeCard(memberRecords) {
  const id = nextCardId();
  const memberKeys = memberRecords.map((r) => r.player);
  const entry = { id, origin: "merge", memberKeys, el: null, folded: false };
  mergeCards.set(id, entry);
  mountMergeCardElement(entry, memberRecords);
  renderPlayerCardsSpace();
}

// The floating card's own × — mirrors closeScoutCard()'s "view only" close
// (BLUEPRINT_PinnedPlayers.md §3/§4 extended to Merge Cards): the entry
// stays in mergeCards, so the Merged Cards row survives and reopenOrFocusMergeCard()
// can bring the card back. Linemate Cards spawned from this card's rows are
// left alone too, same as closeScoutCard() leaves a Player Card's.
export function closeMergeCardFloating(id) {
  const entry = mergeCards.get(id);
  if (!entry || !entry.el) return;
  entry.el.remove();
  entry.el = null;
  updateScoutEmptyHint();
}

// Reopens a previously-closed Merge Card's floating view from its surviving
// entry — the Merged Cards row's click target, see renderMergedList().
export function reopenMergeCard(id) {
  const entry = mergeCards.get(id);
  if (!entry || entry.el) return;
  const memberRecords = entry.memberKeys.map(findRecordByPlayer).filter(Boolean);
  mountMergeCardElement(entry, memberRecords);
}

export function flashMergeCard(id) {
  const entry = mergeCards.get(id);
  if (!entry || !entry.el) return;
  bringScoutCardToFront(entry.el);
  entry.el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  entry.el.classList.remove("is-flash");
  void entry.el.offsetWidth;
  entry.el.classList.add("is-flash");
  entry.el.addEventListener("animationend", () => entry.el.classList.remove("is-flash"), { once: true });
}

// Merged Cards row click (§4-style "admit or focus", extended to Merge
// Cards): reopens the floating card if it's closed, or brings it to front
// (flashed, scrolled into view) if it's already open somewhere off-screen.
export function reopenOrFocusMergeCard(id) {
  const entry = mergeCards.get(id);
  if (!entry) return;
  if (entry.el) {
    flashMergeCard(id);
  } else {
    reopenMergeCard(id);
  }
}

// Dissolve: releases the merged players' quota slots and removes the card
// entirely, row and all. Pinned Players' "Dismiss" button, and the Edit popup
// auto-dissolving down to <= 1 remaining member (removeMergeMember()/
// closeMergeEditPopup()), both call this — unlike the floating card's own ×
// above, which only hides the view.
export function closeMergeCard(id) {
  const entry = mergeCards.get(id);
  if (!entry) return;
  if (entry.el) entry.el.remove();
  mergeCards.delete(id);
  entry.memberKeys.forEach((key) => closeLinemateCard(key));
  updateScoutEmptyHint();
  renderPlayerCardsSpace();
}

// --- Merge Card membership editor (BLUEPRINT_PinnedPlayers.md §5) --------
// Its add pool is pcsSearchPool() (v1.2.0 §4) — the current position pool
// only, same as the Create popup and the Single Cards add-search; merge
// cards no longer cross positions.

// The one merged card currently open in the popup, or null — single static
// overlay instance (like #merge-confirm-overlay), repopulated per open.
let mergeEditCardId = null;

export function setMergeEditMessage(text) {
  els.mergeEditMessage.textContent = text || "";
}

export function hideMergeEditDropdown() {
  els.mergeEditDropdown.hidden = true;
  els.mergeEditDropdown.innerHTML = "";
}

export function openMergeEditPopup(id) {
  const entry = mergeCards.get(id);
  if (!entry) return;
  mergeEditCardId = id;
  renderMergeEditMembers(entry);
  els.mergeEditInput.value = "";
  hideMergeEditDropdown();
  setMergeEditMessage("");
  els.mergeEditOverlay.hidden = false;
  els.mergeEditInput.focus();
}

// Closing the popup (Done, or Escape backing all the way out — both route
// here) is the one point membership edits are checked against the <= 1
// auto-dissolve rule, not each individual removeMergeMember() click — so the
// user can freely remove members and see the card update live without it
// disappearing out from under them until they're actually done editing.
export function closeMergeEditPopup() {
  const id = mergeEditCardId;
  mergeEditCardId = null;
  els.mergeEditOverlay.hidden = true;
  hideMergeEditDropdown();

  if (id == null) return;
  const entry = mergeCards.get(id);
  if (!entry || entry.memberKeys.length > 1) return;

  const survivorKey = entry.memberKeys[0];
  closeMergeCard(id);
  if (survivorKey && !workspaceSingles.has(survivorKey)) {
    const survivorRecord = findRecordByPlayer(survivorKey);
    if (survivorRecord) workspaceSingles.set(survivorKey, survivorRecord);
  }
  renderPlayerCardsSpace();
}

export function renderMergeEditMembers(entry) {
  els.mergeEditMembers.innerHTML = "";
  entry.memberKeys.forEach((key) => {
    const record = findRecordByPlayer(key);
    const label = (record && (record.abbr_name || record.player)) || key;

    const row = document.createElement("div");
    row.className = "merge-edit-member";

    const name = document.createElement("span");
    name.className = "merge-edit-member-name";
    name.textContent = label;
    row.appendChild(name);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "merge-edit-member-remove";
    removeBtn.setAttribute("aria-label", `Remove ${label}`);
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => removeMergeMember(entry.id, key));
    row.appendChild(removeBtn);

    els.mergeEditMembers.appendChild(row);
  });
}

// Mirrors renderPlayersDropdown()'s markup/classes exactly (.player-option
// etc.) for the "same fuzzy-match input style as the Players filter" rule.
export function renderMergeEditDropdown(matches) {
  els.mergeEditDropdown.innerHTML = "";
  if (!matches.length) {
    hideMergeEditDropdown();
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
      if (mergeEditCardId != null) addMergeMember(mergeEditCardId, record);
    });

    els.mergeEditDropdown.appendChild(opt);
  });

  els.mergeEditDropdown.hidden = false;
}

export function runMergeEditSearch() {
  const query = els.mergeEditInput.value.trim();
  if (!query) {
    hideMergeEditDropdown();
    return;
  }
  // No exclusion set — an already-on-this-card pick is caught (and
  // explained) defensively in addMergeMember() rather than hidden from the
  // list, matching the checklist's "blocked, with a prompt" wording.
  renderMergeEditDropdown(searchPlayersExcluding(query, pcsSearchPool(), new Set()));
}

// Rebuilds the floating Merge Card's title/subtitle/table from its current
// memberKeys — the only place a merged member's record has to be looked up
// fresh (findRecordByPlayer), since he may no longer be in workspaceSingles
// (§4/§6: Remove doesn't touch merged instances).
export function rebuildMergeCardFromMembers(entry) {
  if (!entry.el) return; // floating card closed (BLUEPRINT_PinnedPlayers.md §4-style) — nothing on screen to update
  const memberRecords = entry.memberKeys.map(findRecordByPlayer).filter(Boolean);
  renderMergeCardBody(entry.el, memberRecords);
}

// §5 Edit popup rules: blocks + explains a duplicate add, a 6th member, the
// same 8-player hard cap as any other new admission, or a resulting
// membership that would match another existing card's (CHANGE 5). Otherwise
// appends, surfaces the new member as a Single Cards row too if he wasn't
// already one (mirroring the invariant a normal Merge creates), and rebuilds
// the card in place.
export function addMergeMember(id, record) {
  const entry = mergeCards.get(id);
  if (!entry) return;
  const key = record.player;

  if (entry.memberKeys.includes(key)) {
    setMergeEditMessage(`${record.abbr_name || key} is already on this card — pick someone else.`);
    return;
  }
  if (entry.memberKeys.length >= MERGE_CARD_MAX_MEMBERS) {
    setMergeEditMessage(`Merge Cards hold at most ${MERGE_CARD_MAX_MEMBERS} players — remove one first.`);
    return;
  }
  const distinct = distinctWorkspacePlayers();
  if (!distinct.has(key) && distinct.size >= MERGE_QUOTA) {
    setMergeEditMessage(
      `Workspace full (${MERGE_QUOTA}/${MERGE_QUOTA}) — remove a player to add ${withTrailingPeriod(record.abbr_name || key)}`
    );
    return;
  }
  const proposedKeys = [...entry.memberKeys, key];
  if (findDuplicateMergeCard(proposedKeys, id)) {
    setMergeEditMessage("This merged card already exists.");
    return;
  }

  entry.memberKeys = proposedKeys;
  if (!workspaceSingles.has(key)) workspaceSingles.set(key, record);

  rebuildMergeCardFromMembers(entry);
  renderMergeEditMembers(entry);
  setMergeEditMessage("");
  els.mergeEditInput.value = "";
  runMergeEditSearch();
  renderPlayerCardsSpace();
}

// Removing a member down to <= 1 no longer dissolves the card immediately —
// the popup stays open showing whatever's left, and the dissolve (with the
// same "return the lone survivor to Single Cards" behavior as before) only
// actually happens once the user hits Done, see closeMergeEditPopup(). A
// removal that would leave this card's membership matching another existing
// card's is blocked too (CHANGE 5) — the invariant holds on every mutation,
// not just adds.
export function removeMergeMember(id, key) {
  const entry = mergeCards.get(id);
  if (!entry) return;
  const remaining = entry.memberKeys.filter((k) => k !== key);
  if (findDuplicateMergeCard(remaining, id)) {
    setMergeEditMessage("This merged card already exists.");
    return;
  }
  entry.memberKeys = remaining;
  rebuildMergeCardFromMembers(entry);
  renderMergeEditMembers(entry);
  renderPlayerCardsSpace();
}
