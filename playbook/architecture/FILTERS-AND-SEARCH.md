# Filters and Players search

> **Load when:** touching Teams/Players filters, the Players search pool, below-threshold matches, or Quick Set.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Teams and Players filters combine via union (OR), never intersection (AND)** — a player is
highlighted if his team is selected, if he himself is selected, or both; this is the whole point of
the filter (e.g. pinning one trade-target player against an entire other team's roster at the same
position). Selecting a specific player while Teams is at the full 32-team selection auto-resets
Teams to "No Teams," since under union logic a full-32 selection would highlight everyone regardless
— but this reset is scoped to the all-32 case only; any partial team selection plus a player
selection is a legitimate combination and must not be auto-cleared. The Players filter header's
own info popover (`main.js`'s `attachEvents()`, a small ⓘ trigger via `createInfoPopover()` exactly
like Teams/X/Y — the header is a plain `<label id="players-label">`, then the ⓘ, then the Clear link)
is where this union rule is spelled out for users, so keep its text in sync with any change here.
The Teams header's ⓘ carries the complementary half: Teams only *highlights* (dims everyone else via
`render.js`'s `isDimmed`), never shrinks the percentile pool — which is determined by position and
snap threshold alone. If Teams ever starts filtering the pool, that popover's text is wrong.

**Career: the Status Filter only dims.** On `/ncaaf-career` the Status Filter (Joined NFL, Potential Draftees; only Potential
Draftees is lit by default, Joined NFL stays in the pool as the dimmed yardstick) behaves like Teams: it is Apply-gated and joins the same union in `render()`'s `isDimmed`: a player is lit when his
status is lit, or his team is chosen, or his name is selected (a status that is off lights nobody by itself). Because a full
Teams selection already lights everyone, the Career page starts with **No Teams** (`main.js`'s `setUpCareerControls()`), so
the lit status shows at first. The Status Filter never changes the percentile pool. The two bars do not follow the Status Filter:
both are always usable, and a bar of a status that is off still counts. The pool is the union of the Joined
NFL players above the first bar and the Potential Draftees above the second, so toggling a status never moves a percentile.
The ⓘ of the Status Filter says so; keep its text in sync.

**The Players search pool has its own live, non-Apply-gated data track, deliberately separate from
the chart's Apply-gated one** (`data.js`'s `playerPoolRecords`/`playerPoolCategory`, kept current by
`updatePlayerPool()`): every other piece of chart state (`currentRecords`/`currentSliceCategory`/
`appliedFilters`) only updates when Apply commits a batch of pending control changes — that's the
whole point of the Apply button, see "Pool-change invalidation" below. But a Season/Position swap
should let the Players filter suggest the *new* slice's names immediately, not wait for Apply, since
searching for a player is how a user often decides what to switch to in the first place. Rather than
bending the Apply-gated `currentRecords` to serve two different timing needs, `playerPoolRecords` is
a second, parallel copy of "whatever `fetchSlice()` returns for the pending category/season," updated
on every pending control change and read only by `qualifyingPlayerPool()`/`fullPlayerPool()` (the
Players-filter search pool) — the chart, Merge/Linemate cards, and everything else below still read
exclusively from the Apply-gated `currentRecords`. Don't let a future feature read `currentRecords`
expecting it to track pending control changes, or `playerPoolRecords` expecting it to track the chart.

**Below Threshold Matches** (`fullPlayerPool()`/`runPlayersSearch()`/`openBelowThresholdPopup()`/
`setThresholdTo()`, all `filters.js`/`search.js`): `qualifyingPlayerPool()` filters by threshold
*before* fuzzy-matching runs, so a real player name below the current threshold is otherwise
indistinguishable from a name that doesn't exist. `runPlayersSearch()` runs a second, fully
independent fuzzy-match pass against `fullPlayerPool()` (same position scope as
`qualifyingPlayerPool()`, no threshold cut) and keeps only the results that fall under the
threshold (`belowThresholdMatches`, capped at 20 — enough headroom over the normal dropdown's
top-8 for a scrollable popup without a single-letter query dumping the whole pool into it). This is
deliberately a *second* pass rather than the normal `searchPlayers(query, qualifyingPlayerPool())`
call filtered after the fact — fuzzy-matching once against the full pool and splitting afterward
could let a higher-scoring below-threshold name bump a genuinely-qualifying one out of the top-8
normal dropdown, changing existing search-ranking behavior; keeping the two passes independent
means this feature can never alter what the normal dropdown shows. When `belowThresholdMatches` is
non-empty, `renderPlayersDropdown()` prepends a "Below Threshold Matches (N)" toggle above the
first candidate — never auto-popped — opening `#below-threshold-overlay`: one row per match (name,
team, their raw metric value, a "Set Threshold" button), sorted by the same fuzzy-match score as
everywhere else in the app, **not** by snap count. A row's "Set Threshold" button calls
`setThresholdTo(value)` — the filter is an inclusive `>=`, so a candidate's own metric value is
already the minimum threshold that surfaces them, no off-by-one needed — which reuses the exact
clamp/sync/`resetThresholdOnNextRange`/`prunePlayerSelections`/`updatePendingState` sequence the
manual slider/number-input handlers already use (`main.js`'s `attachEvents()`) rather than a
parallel implementation, then closes the popup (leaving it open would show a stale list, since the
clicked player — and possibly others — no longer belong in "below threshold") and re-runs
`runPlayersSearch()`. That re-run is what surfaces the just-qualified player back in the normal
dropdown; the query text in `els.playersInput` is deliberately left untouched through this whole
flow (nothing writes to it) so the re-run picks up exactly where the user was, same convention as
picking a normal candidate (see `renderPlayersDropdown()`'s own comment on why it doesn't
clear/close on pick). Setting a lower threshold this way can surface *other* players whose values
also now clear the new bar, not just the one clicked — this is the same global threshold filter
every other control shares, and is intentional, not a bug to special-case around. The popup itself
follows the app's existing single-static-overlay convention verbatim (`#merge-edit-overlay`'s
pattern: repopulated per open, closes only via its own Close button, no outside-click dismissal,
wired once in `attachEvents()`) rather than inventing a new modal pattern.

**Below Threshold Matches extends to every Pinned Players search box, not just the Players
filter**: `openBelowThresholdPopup(matches, cat, onSetThreshold)` (`filters.js`) was generalized to
take its matches/category/commit-callback as parameters instead of reading module-level state, so
the Single Cards add-search (`workspace.js`'s `runPcsAddSearch()`/`renderPcsAddDropdown()`), the
Merge Create popup (`merge-card.js`'s `runCreateSearch()`/`renderCreateDropdown()`), and the Merge
Edit popup (`runMergeEditSearch()`/`renderMergeEditDropdown()`) all share the one
`#below-threshold-overlay` instance instead of each getting its own. Each box computes its own
below-threshold pass against `fullPcsSearchPool()` (`search.js` — `pcsSearchPool()`'s
threshold-less counterpart, scoped to `appliedFilters.position` off `currentRecords` rather than
`playerPoolRecords`, since Pinned Players has no separate pending-pool concept) and keeps its own
module-level matches array (`pcsAddBelowThresholdMatches`, `createBelowThresholdMatches`,
`editBelowThresholdMatches`) — same two-independent-passes shape as `runPlayersSearch()`, just
three more instances of it.

The Players filter's own Set Threshold is Apply-gated by default (`setThresholdTo()` stages a
pending value), and only takes the immediate lane under the narrow conditions in
"Pool-change invalidation" above (`quickSetPlayersThreshold()`). Pinned Players never was Apply-gated to begin with
(a Single/Merge Card takes effect the moment you pick a player), so its three search boxes instead
call `applyThresholdImmediately(value)` — commits the new threshold straight into `appliedFilters`
(a threshold-only merge; every other currently-Applied field is left exactly as it was, even if the
user has an unrelated pending edit sitting unapplied in the drawer), no refetch needed
(`currentRecords` already holds every threshold value), then calls `render()` and refreshes every
open Player/Linemate/Merge Card **in place** (`refreshOpenScoutCards()`/
`refreshOpenLinemateCards()`/`refreshOpenMergeCards()` — the last one new, `merge-card.js`, reusing
`rebuildMergeCardFromMembers()`) rather than routing through `applyFilters()`'s normal
evaluate→confirm→remove/clear path. This is a deliberate, scoped exception to "a threshold
change is a pool change like any other" (see "Pool-change invalidation" below; the lowered bar can
only widen the pool, so it is always "unaffected" there): routing a one-player quick-add through
the real Apply flow could otherwise put up a removal confirm on an unrelated pending edit, forcing a "back out of the Create/Edit popup, Apply, reopen, redo the search" loop
just to pull in one player below the bar — defeating the point of a *quick* set. Both
`syncThresholdControls()` (the clamp/sync core, extracted so `setThresholdTo()`,
`quickSetPlayersThreshold()` and `applyThresholdImmediately()` share it) and `applyThresholdImmediately()` still call
`prunePlayerSelections()`/`updatePendingState()` for consistency, though pruning is a no-op in
practice here — Set Threshold only ever *lowers* the bar to a below-threshold candidate's own
value, which can only widen the qualifying pool, never shrink it. Wiring this up required two new
circular imports — `workspace.js` <-> `filters.js` and `merge-card.js` <-> `filters.js` — both
function-body-only (a dropdown's toggle click, or `applyThresholdImmediately()` itself, never at
module-evaluation time), the same safety argument as every other documented cycle in this codebase;
see the header comments in `workspace.js` and `merge-card.js`.

**Selected Players are kept while they are still eligible, and re-checked only on commit**

- `prunePlayerSelections()` keeps the selected players who are still eligible and drops the rest, using the same rule as the Pinned Players invalidation:
  `partitionByEligibility()` in `pinned-impact.js`. A player is eligible when they exist in the pending category and season pool at exactly the pending position and
  meet the current (already clamped) threshold, inclusive.
- It runs only when a value is committed: the slider's `change` (on release), the number box's `change` (Enter or leaving the field), Apply, either Set Threshold lane,
  and a category, season or position change through `updatePlayerPool()`. It does **not** run on the slider's or the number box's `input` events, so dragging or typing
  never removes anyone halfway.
- A removed selection is not restored if the value later moves back.
- The user is told through the shared toast, `showNotice()`, with text from `removedPlayersNotice()`: up to three names, then "and N more". In `applyFilters()` the Players
  message is joined with the pinned-players refresh message into a single toast, so one cannot replace the other.
- A removal notice uses the yellow warning variant (`.is-warning`: dark text on `--flag-gold-bright`, with a leading warning sign from `::before`, so colour is not the only cue).
  The pinned-players refresh message stays on the neutral dark-green toast. A joined message is yellow whenever it includes a removal.
- The shared rule treats a record with no threshold value as not eligible. The old pool check let such a record through at a threshold of 0; it only matters if a record
  ever lacks its threshold column.

