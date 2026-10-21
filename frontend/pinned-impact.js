/* Pure decision + copy functions: what would applying a final filter
 * combination do to the Pinned Players Workspace? Dependency-free leaf (no
 * DOM, no state), unit-testable by importing the served module inside
 * Chromium — see tests/test_pinned_impact.py. Judges the FINAL combination
 * about to be applied (applied vs. pending, as two snapshots), never step by
 * step.
 *
 * evaluatePinnedImpact() returns
 *   { outcome, kept, removed, comparisons: { shrunk, dissolved } }
 * where outcome is
 *   "unaffected" — every pinned player stays, same season: apply silently
 *   "refresh"    — every pinned player carries over to the new season
 *   "partial"    — some pinned players don't fit: confirm, then remove only those
 *   "reset"      — Category/Position changed, or nobody fits: confirm, clear all
 *
 * applied / pending: { category, season, position, threshold } — `pending.threshold`
 *   must be the FINAL threshold (already clamped / defaulted for the new season).
 * pinnedPlayers: iterable of player strings (Single Cards ∪ Merge Card members).
 * playerPoolRecords: records of the pending category + season (every position).
 * thresholdField: the category's threshold column ("PR Opp" / "Non Spike PB Snaps").
 * comparisons: [{ id, memberKeys }] — the open Comparison (Merge) Cards.
 *
 * Comparisons (partial only): members minus removed players; >= 2 left →
 * `shrunk` ({ id, members, kept, removed }), otherwise `dissolved`
 * ({ id, members, survivors }). A shrunk card whose remaining membership
 * equals another card's (cards must stay unique) is dissolved too, with
 * `duplicate: true`; unchanged cards keep priority over shrunk ones.
 *
 * partitionByEligibility() is the one eligibility rule, shared with the
 * Players filter (filters.js's prunePlayerSelections()): who stays and who
 * goes when the pool, position or threshold changes. removedPlayersNotice()
 * is the toast text for the Players filter's removals. resolveCarriedRecord()
 * decides which row a floating Player/Linemate Card follows after the
 * threshold or season moves.
 */
export const COMPARISON_MIN_MEMBERS = 2;

const NO_COMPARISONS = { shrunk: [], dissolved: [] };

// Who stays and who goes: a player is eligible when they exist in `records`
// at exactly `position` and their `thresholdField` value is at least
// `threshold` (inclusive). A player missing from the pool, or with no value,
// is not eligible. `threshold` must already be the FINAL one (clamped or
// defaulted for the pool being judged). Shared by evaluatePinnedImpact() and
// the Players filter so the two can never disagree about eligibility.
// Returns { kept, removed }, each in the order of `names`.
export function partitionByEligibility(names, records, position, threshold, thresholdField) {
  const byPlayer = new Map();
  (records || []).forEach((r) => {
    if (r.position === position) byPlayer.set(r.player, r);
  });
  const kept = [];
  const removed = [];
  Array.from(names).forEach((name) => {
    const record = byPlayer.get(name);
    const value = record ? record[thresholdField] : null;
    if (value == null || value < threshold) removed.push(name);
    else kept.push(name);
  });
  return { kept, removed };
}

// Which row a floating Player Card or Linemate anchor follows after the applied
// slice or threshold moved. Unlike a pinned player (judged at the applied
// position only), a card opened from a Linemate Card's "Card" button can belong
// to a teammate at another position on the same line, so any position in
// `linePositions` counts. The player must have a row there whose `thresholdField`
// value is at least `threshold` (inclusive). When several rows qualify, the one
// at `preferredPosition` (the card's current position) wins. Returns the record,
// or null when the card should close.
export function resolveCarriedRecord(records, name, preferredPosition, linePositions, threshold, thresholdField) {
  const matches = (records || []).filter(
    (r) =>
      r.player === name &&
      linePositions.includes(r.position) &&
      r[thresholdField] != null &&
      r[thresholdField] >= threshold
  );
  return matches.find((r) => r.position === preferredPosition) || matches[0] || null;
}

export const REMOVED_PLAYERS_NOTICE_MAX_NAMES = 3;

// Toast text when the Players filter drops selected players. Lists up to
// REMOVED_PLAYERS_NOTICE_MAX_NAMES names, then "and N more". `displayNames`
// are the labels to show (e.g. abbr_name); returns "" when nobody was removed.
export function removedPlayersNotice(displayNames) {
  const names = Array.from(displayNames);
  if (!names.length) return "";
  const shown = names.slice(0, REMOVED_PLAYERS_NOTICE_MAX_NAMES);
  const extra = names.length - shown.length;
  const list = extra > 0 ? `${shown.join(", ")} and ${extra} more` : shown.join(", ");
  return `Removed from Players: ${list} — no longer eligible.`;
}

export function evaluatePinnedImpact(
  applied,
  pending,
  pinnedPlayers,
  playerPoolRecords,
  thresholdField,
  comparisons = []
) {
  const pinned = Array.from(pinnedPlayers);

  // Category / Position differ: nobody carries over (a pinned player came from
  // the old position's pool). No data needed.
  if (applied.category !== pending.category || applied.position !== pending.position) {
    return { outcome: "reset", kept: [], removed: pinned, comparisons: NO_COMPARISONS };
  }

  const seasonChanged = Number(applied.season) !== Number(pending.season);
  const pendingThreshold = Number(pending.threshold);

  // Same season and a looser (or equal) bar can't remove anyone.
  if (!seasonChanged && pendingThreshold <= Number(applied.threshold)) {
    return { outcome: "unaffected", kept: pinned, removed: [], comparisons: NO_COMPARISONS };
  }

  // Every pinned player must exist in the pool at that exact position and
  // clear the (clamped) new threshold (inclusive).
  const { kept, removed } = partitionByEligibility(
    pinned,
    playerPoolRecords,
    pending.position,
    pendingThreshold,
    thresholdField
  );

  if (!removed.length) {
    return { outcome: seasonChanged ? "refresh" : "unaffected", kept, removed, comparisons: NO_COMPARISONS };
  }
  if (!kept.length) return { outcome: "reset", kept, removed, comparisons: NO_COMPARISONS };
  return { outcome: "partial", kept, removed, comparisons: splitComparisons(comparisons, removed) };
}

function splitComparisons(comparisons, removed) {
  const gone = new Set(removed);
  const shrunk = [];
  const dissolved = [];
  const seen = new Set();
  const keyOf = (members) => [...members].sort().join("\u0000");
  const survivors = [];

  comparisons.forEach(({ id, memberKeys }) => {
    const left = memberKeys.filter((k) => !gone.has(k));
    if (left.length === memberKeys.length)
      seen.add(keyOf(left)); // untouched: claims its membership first
    else survivors.push({ id, members: memberKeys, left });
  });
  survivors.forEach(({ id, members, left }) => {
    const gonePart = members.filter((k) => gone.has(k));
    const duplicate = left.length >= COMPARISON_MIN_MEMBERS && seen.has(keyOf(left));
    if (left.length < COMPARISON_MIN_MEMBERS || duplicate) {
      dissolved.push({ id, members, survivors: left, ...(duplicate ? { duplicate: true } : {}) });
    } else {
      seen.add(keyOf(left));
      shrunk.push({ id, members, kept: left, removed: gonePart });
    }
  });
  return { shrunk, dissolved };
}

// Only "unaffected" / "refresh" may take an immediate (no-confirm) lane — the
// Players-filter Quick Set stages the value for Apply on "partial" / "reset".
export function mayApplyWithoutConfirm(outcome) {
  return outcome === "unaffected" || outcome === "refresh";
}

export const CONFIRM_TITLE = "New Filters Cause Removals";
export const CONFIRM_LABEL = "REMOVE & APPLY";
export const CONFIRM_NOTE = "This can’t be undone.";
export const STATUS_DISSOLVED = "dissolved";
export const STATUS_MERGED = "merged into an identical comparison";

// Structured copy for the confirm dialog (rendered by workspace.js with
// textContent only). `displayName` maps a player string to the label shown to
// the user (e.g. abbr_name). Title and confirm label are the same for
// "partial" and "reset"; "reset" lists every pinned player and no Comparisons.
// Nothing is truncated — the dialog's content area scrolls instead.
//
//   removedLabel / comparisonsLabel   section tags (the renderer appends " · N")
//   removedNames    every removed player's display name
//   comparisonRows  [{ before: [names], after: [names] | null, status: string | null }]
//                   one per affected Comparison. shrunk → after = remaining members;
//                   dissolved / merged → status text. A Comparison has no title of
//                   its own, so rows are labelled by their original members
//                   (rendered joined with " + ").
export function impactConfirmMessage(result, displayName = (k) => k) {
  const label = (keys) => keys.map(displayName);
  return {
    title: CONFIRM_TITLE,
    removedLabel: "REMOVED",
    removedNames: label(result.removed),
    comparisonsLabel: "AFFECTED COMPARISONS",
    comparisonRows: [
      ...result.comparisons.shrunk.map((c) => ({ before: label(c.members), after: label(c.kept), status: null })),
      ...result.comparisons.dissolved.map((c) => ({
        before: label(c.members),
        after: null,
        status: c.duplicate ? STATUS_MERGED : STATUS_DISSOLVED,
      })),
    ],
    note: CONFIRM_NOTE,
    confirmLabel: CONFIRM_LABEL,
  };
}
