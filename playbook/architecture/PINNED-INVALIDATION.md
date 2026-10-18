# Pool-change invalidation (Pinned Players, confirm dialog)

> **Load when:** changing filters that can remove Pinned Players, the confirm dialog, or Comparison shrink/dissolve rules.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Pool-change invalidation is judged on the FINAL filter combination, and removes only who doesn't fit**
(`pinned-impact.js`'s pure `evaluatePinnedImpact(applied, pending, pinnedPlayers, playerPoolRecords,
thresholdField, comparisons)`, called from `applyFilters()` and the Players-filter Quick Set;
unit-tested in `tests/test_pinned_impact.py` by importing the served module in Chromium). It compares
the applied snapshot to the combination about to be applied (pending Season/Category/Position + the
*final, already clamped/defaulted* threshold) and returns `{ outcome, kept, removed, comparisons:
{ shrunk, dissolved } }`. Rules: Category or Position differs → `"reset"` (no data needed; **Position
stays a full reset** because every pinned player, Comparison and Linemate anchor was built from the
old position's pool — ED→DI isn't "same player, new pool", and Comparisons never cross positions).
Otherwise each pinned player is checked against the pending season's pool at the same position:
must exist, be at that exact position, and meet the clamped threshold (inclusive `>=`). Same season
with a looser/equal bar skips the check (`"unaffected"`). Everyone passes → `"refresh"` (Season
changed) or `"unaffected"`; **some fail → `"partial"`**; **all fail → `"reset"`**. "Pinned" =
`distinctWorkspacePlayers()` (Single Cards ∪ Merge Card members), identified by the `player` string.
It reads the already-fetched `playerPoolRecords`; `applyFilters()` first awaits `updatePlayerPool()`
when category/position are unchanged so that pool is the pending season's slice (a `sliceCache` hit)
and `els.thresholdNumber` holds the clamped value.

- **`"unaffected"`**: apply silently. **`"refresh"`**: no confirm; a neutral toast ("Pinned players
  updated to {season} season data.") and every surviving card is re-pointed at the player's row in
  the new slice (`reconcileCarriedCards()`), then `refreshOpen*Cards()` recompute the numbers.
  **`"reset"`**: confirm, then `clearWorkspace()` (everything, including Comparisons).
  **`"partial"`**: confirm (copy lists the removed players and affected Comparisons), then
  `workspace.js`'s `removePinnedPlayers()` removes ONLY the `removed` players — Single Cards rows,
  Player Cards, Linemate Cards anchored on them — and the survivors go through the same
  re-point/refresh as `"refresh"` (toast only if the Season changed). The 8-player quota frees
  itself: `distinctWorkspacePlayers()` is derived from `workspaceSingles` + `mergeCards`.

- **Comparison rules (partial only)**: a Comparison has no title of its own (its row/label is its
  members joined, its card says "Player Comparison · {season}") and keeps no creation-time member
  snapshot — only `memberKeys`, resolved by name on every render. Members minus removed players:
  `>= 2` left (`COMPARISON_MIN_MEMBERS`) → `shrunk`, kept with the reduced `memberKeys` and rebuilt by
  `refreshOpenMergeCards()`; `< 2` → `dissolved` (floating card closed, row removed; a lone surviving
  member returns to Single Cards, same as the Edit popup's auto-dissolve — they're pinned and
  passed the check). A shrunk card whose remaining membership equals another card's is dissolved too
  (`duplicate: true`) to keep the "no two Comparisons share membership" invariant; untouched cards
  keep priority. A player in several Comparisons is removed from all of them.

- **Confirm dialog** (`#merge-confirm-overlay`): one title and one confirm button for both `partial`
  and `reset` — "New Filters Cause Removals" / "REMOVE & APPLY" (cancel stays "CANCEL"). The content is
  built from the pure `impactConfirmMessage(result, displayName)` (`pinned-impact.js`), which returns a
  structured object `{ title, removedLabel, removedNames, comparisonsLabel, comparisonRows, note,
  confirmLabel }` (not a string); `workspace.js`'s `renderConfirmContent()` renders it with
  `textContent` only, each name in a `white-space: nowrap` span (long lists wrap between names).

  - **No truncation** (the earlier "and N more" is gone): everything is listed and the **content area
    scrolls**. Only `#merge-confirm-body` (the REMOVED / AFFECTED COMPARISONS sections) scrolls —
    `max-height: min(60vh, 100vh − 240px)`, `overscroll-behavior: contain`, `tabindex="0"` + `role="region"`
    + `aria-label` for keyboard scrolling; title, note and buttons stay fixed. A bottom fade
    (`.merge-confirm-scroll.has-more::after`) shows only while content is hidden below, toggled by
    `updateConfirmScrollHint()` on open and on scroll.

  - Section tags read `REMOVED · N` and `AFFECTED COMPARISONS · N` (N = real totals; the Comparisons
    block is omitted entirely when none are affected). `reset` lists every pinned player and no rows.

  - Both lists are real bullet lists, **one bullet per player / per Comparison**. A Comparison bullet is
    the original members joined by " + ", then — inside the same bullet, indented, secondary colour — the
    outcome line: shrunk → `→ {remaining members}`, dissolved (< 2 left) → `→ dissolved`, dissolved
    because it became identical to another → `→ merged into an identical comparison` (the `duplicate`
    flag). Spacing is deliberately uneven (2px inside a bullet, 12px between Comparisons) so grouping
    reads at a glance. Shrunk rows come before dissolved ones.

  - **"This can’t be undone."** sits in the fixed area above the buttons (`#merge-confirm-note`), in
    `--alert-coral` (`#ff8a75`, `style.css` `:root`): 5.22:1 against the box's lightest gradient stop
    `--turf-700` (6.19:1 on `--turf-800`); the bar is ≥ 4.5:1 — adjust the variable, not the button's
    `--rush-clay` (2.2:1 as text). The sentence states the consequence itself; color only reinforces.

  - Narrow screens (`max-width: 480px`): tighter padding, and the button row may wrap so neither button is
    pushed off-screen. That media block must stay *after* the base `.merge-confirm-actions` rules
    (same specificity, source order decides).

- Linemate Cards are deliberately not checked individually: their roster derives from the anchor +
  applied filters, so a season change keeps them (anchor re-pointed, roster/summary recomputed by
  `refreshOpenLinemateCards()`); they are dissolved only by a "reset" that changes the slice.
  Floating cards left over from a plot click (not pinned) survive only if their player still exists
  at the applied position and meets the threshold, otherwise they close.

- Previously any Season/Category/Position/Threshold change cleared the Workspace; Axes, Teams,
  Players, Fold/Unfold, labels etc. still never participate (they don't touch `positionPool()`'s inputs).

- **Players-filter Quick Set** (`quickSetPlayersThreshold()` in `filters.js`) uses the same
  Pinned fast lane as `applyThresholdImmediately()` (commit a threshold-only merge into
  `appliedFilters`, `render()`, refresh cards in place, skip the confirm) but only when the pending
  Season/Category/Position equal the applied ones — pending Teams/Players/axes edits are irrelevant
  (Teams only highlights) and are left untouched. It first passes `evaluatePinnedImpact()`; on
  `"partial"` or `"reset"` (`mayApplyWithoutConfirm()`), or when the pool fields differ, it just stages
  the value as pending (the old behavior), so Apply shows its confirm. Pinned's own Quick Set only ever lowers the bar, which is
  always "unaffected".
- 

**Things that must NOT invalidate, clear or reset any card** (carried over from the retired `BLUEPRINT.md` §4, 2026-10-17)

- **X / Y axis selection**: plot controls, not filters. The pool has not changed, and the user may well be switching axes
  precisely to re-view a set already merged.
- **Player Names / Team Logos / Include metric notes toggles**: display options only (see `METRICS-AND-NOTES.md`, "Include metric notes").
- **Fold/Unfold and See more/See less state.**
- **Card dragging.**

The axis controls sit in the same row as the filters in the layout. Take care not to wire them into a shared
"filter changed → reset" handler.
