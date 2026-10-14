/* Pure decision function: what would applying a final filter combination do
 * to the Pinned Players Workspace? Dependency-free leaf (no DOM, no state), so
 * it is unit-testable by importing the served module inside Chromium — see
 * tests/test_pinned_impact.py. Judges the FINAL combination about to be
 * applied (applied vs. pending, as two snapshots), never step by step.
 *
 *   "unaffected" — apply silently, nothing in the Workspace changes identity
 *   "refresh"    — every pinned player carries over to the new season; apply
 *                  with a neutral notice and re-point every card at new data
 *   "reset"      — at least one pinned player would be lost; confirm, then
 *                  clear the whole Workspace (all-or-nothing)
 *
 * applied / pending: { category, season, position, threshold } — `pending.threshold`
 *   must be the FINAL threshold (already clamped / defaulted for the new season).
 * pinnedPlayers: iterable of player strings (Single Cards ∪ Merge Card members).
 * playerPoolRecords: records of the pending category + season (every position).
 * thresholdField: the category's threshold column ("PR Opp" / "Non Spike PB Snaps").
 */
export function evaluatePinnedImpact(applied, pending, pinnedPlayers, playerPoolRecords, thresholdField) {
  // 1. Category / Position differ: nobody carries over. No data needed.
  if (applied.category !== pending.category || applied.position !== pending.position) return "reset";

  const seasonChanged = Number(applied.season) !== Number(pending.season);
  const appliedThreshold = Number(applied.threshold);
  const pendingThreshold = Number(pending.threshold);

  // 2-3. Same season: nothing, or a looser bar, can't remove anyone.
  if (!seasonChanged && pendingThreshold <= appliedThreshold) return "unaffected";

  // 4-5. Same position + category from here on; every pinned player must exist
  // in the pool at that exact position and clear the (clamped) new threshold.
  const byPlayer = new Map();
  (playerPoolRecords || []).forEach((r) => {
    if (r.position === pending.position) byPlayer.set(r.player, r);
  });
  for (const name of pinnedPlayers) {
    const record = byPlayer.get(name);
    const value = record ? record[thresholdField] : null;
    if (value == null || value < pendingThreshold) return "reset";
  }
  return seasonChanged ? "refresh" : "unaffected";
}
