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
 */
export const COMPARISON_MIN_MEMBERS = 2;

const NO_COMPARISONS = { shrunk: [], dissolved: [] };

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
  const byPlayer = new Map();
  (playerPoolRecords || []).forEach((r) => {
    if (r.position === pending.position) byPlayer.set(r.player, r);
  });
  const kept = [];
  const removed = [];
  pinned.forEach((name) => {
    const record = byPlayer.get(name);
    const value = record ? record[thresholdField] : null;
    if (value == null || value < pendingThreshold) removed.push(name);
    else kept.push(name);
  });

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
export const CONFIRM_MAX_NAMES = 3;
export const CONFIRM_MAX_COMPARISONS = 3;
export const STATUS_DISSOLVED = "dissolved";
export const STATUS_MERGED = "merged into an identical comparison";

// Splits a list into what is shown (first `max`) and how many are cut.
export function formatNameList(items, max = CONFIRM_MAX_NAMES) {
  return { shown: items.slice(0, max), more: Math.max(0, items.length - max) };
}

// Structured copy for the confirm dialog (rendered by workspace.js with
// textContent only). `displayName` maps a player string to the label shown to
// the user (e.g. abbr_name). Title and confirm label are the same for
// "partial" and "reset"; "reset" lists every pinned player and no Comparisons.
//
//   removedNames    first <= 3 display names (array, so each can be kept on one line)
//   removedMore     how many were cut ("and N more"), 0 if none
//   comparisonRows  [{ before: [names], after: [names] | null, status: string | null }]
//                   shrunk → after = remaining members; dissolved/merged → status text.
//                   A Comparison has no title of its own, so rows are labelled by
//                   their original members (rendered joined with " + ").
//   comparisonMore  Comparisons cut beyond 3
export function impactConfirmMessage(result, displayName = (k) => k) {
  const names = formatNameList(result.removed.map(displayName));
  const label = (keys) => keys.map(displayName);
  const rows = [
    ...result.comparisons.shrunk.map((c) => ({ before: label(c.members), after: label(c.kept), status: null })),
    ...result.comparisons.dissolved.map((c) => ({
      before: label(c.members),
      after: null,
      status: c.duplicate ? STATUS_MERGED : STATUS_DISSOLVED,
    })),
  ];
  const shownRows = formatNameList(rows, CONFIRM_MAX_COMPARISONS);
  return {
    title: CONFIRM_TITLE,
    removedLabel: "REMOVED",
    removedNames: names.shown,
    removedMore: names.more,
    comparisonRows: shownRows.shown,
    comparisonMore: shownRows.more,
    note: CONFIRM_NOTE,
    confirmLabel: CONFIRM_LABEL,
  };
}
