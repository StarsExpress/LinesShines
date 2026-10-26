# Season-threshold routing and the threshold input clamp

> **Load when:** touching config.py thresholds, resolve_default_threshold, or the threshold number box in filters.js.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Season-threshold routing** (`config.py::resolve_default_threshold`, consumed by `main.py`'s
`/api/metadata` and, on the frontend, `filters.js`'s `updateThresholdRange()` /
`resetThresholdToCategoryDefault()` / `updatePendingThresholdMax()`): a season is either "finalized" (`season_year < current
calendar year` → the static `DEFAULT_THRESHOLDS`, 230 PR Opp / 300 Non Spike PB Snaps) or "in
progress" (`season_year == current calendar year` → `DYNAMIC_THRESHOLDS[season]`, hand-edited
weekly during the local `python -m database.db_ingestion` run — eyeballed against how far the
season has actually progressed, deliberately **not** a fraction-of-season-elapsed formula, since
season pacing is bumpy (byes, blowouts, injuries)). This is a Calendar Year comparison, not a
season-schedule-aware one — the regular season is ~90% complete before New Year's Day, so it's an
accepted near-100%-accurate approximation. If the current season has no `DYNAMIC_THRESHOLDS` entry
yet (e.g. the first ingest of a new season, before that week's manual edit), it silently falls back
to the static default rather than raising — `db_ingestion.py`'s `main()` prints a reminder in that
case rather than failing the run. `/api/metadata` exposes this as `default_thresholds` (a dict
keyed by season, not a single scalar) per category, one call to `resolve_default_threshold()` per
season in that category's season list. **This is a display-filter concept only** — neither
`preprocessing/front_7.py` nor `preprocessing/offensive_line.py` reads a threshold or drops rows by
one; every row for every season is ingested into the DB regardless of snap count, and the threshold
only decides what the chart/tables show. **`DYNAMIC_THRESHOLDS`'s top-level key is a literal season
year (e.g. `2026`), not `date.today().year`** — this was deliberate, not an oversight: the dict is
built once at module import (once per deploy, not per request), so a computed key would freeze at
whatever year the process happened to start in and drift out of sync with
`resolve_default_threshold()`'s own fresh-per-call `date.today().year`; worse, a computed key could
never be "missing" for the current season, silently carrying forward last season's stale eyeballed
number instead of falling back to the static default and printing the `db_ingestion.py` reminder.
Add a new `YYYY: {...}` entry by hand each time a new season starts — no code change needed for the
transition.

**Threshold number box's clamp ceiling only moves when the value actually needs it to** (`filters.js`'s
`updatePendingThresholdMax()`, called from `updatePlayerPool()`, and its Apply-time twin
`updateThresholdRange()`): a native `<input type="range">`'s handle renders at a position purely
derived from `value`/`max`, so reassigning `.max` visibly moves the handle even when `.value` is left
untouched — the driving rule behind every case below is "never reassign `.max` unless `.value` is
also genuinely changing." `updatePendingThresholdMax()` checks two triggers, in priority order:

1. **`resetThresholdOnNextRange` is still `true`** — a Category switch or an ongoing→historical Season
   switch is pending. A Category switch (`main.js`'s category `"change"` handler) still calls
   `resetThresholdToCategoryDefault()` synchronously first, for instant feedback — leaving the
   outgoing category's number on screen, even briefly, is actively misleading since the two
   categories' threshold fields are entirely different units (PR Opp vs Non Spike PB Snaps). That
   function can only grow `.max` just far enough to fit the new default off whatever pending data
   happens to already be on hand (the *outgoing* slice's, not the incoming one's real numbers) — a
   rough placeholder, corrected here once real data lands. A Season switch crossing ongoing→historical
   has no such units mismatch, so it *skips* that synchronous call entirely (only sets the flag) and
   leaves both `.value` and `.max` untouched until this function runs with real fetched data. Either
   way, this branch applies the real default + real max together, atomically, in one write, the moment
   `playerPoolRecords` actually has this slice's data. Writing both together (not value-now/max-later)
   is what avoids ever rendering a wrong intermediate frame — an earlier version of this fix set the
   value synchronously in `resetThresholdToCategoryDefault()` for the Season case too, deferring only
   `.max`'s correction to here; whenever the rough placeholder max happened to land exactly on the new
   default, the slider handle would visibly pin at the far-right edge for however long the fetch took,
   then snap back once corrected — a jarring flash this atomic version doesn't produce.

2. **No reset pending, but the current value no longer fits the newly computed max** — a real, if
   smaller, correction (e.g. Position swapped into a narrower pool). Falls back to that season's
   `default_thresholds` entry, not the new slice's raw `max` — using raw `max` here previously left a
   different bug: hopping from a finalized historical season straight to the ongoing one clamped the
   number box to whatever snap count the in-progress season happened to have racked up by that week (a
   moving, arbitrary target), instead of the number actually configured as sensible for it via
   `DYNAMIC_THRESHOLDS`/`DEFAULT_THRESHOLDS`.

Neither trigger fires for a no-op swap (e.g. one historical season to another, sharing
`DEFAULT_THRESHOLDS`' one static value) — the very first version of this function recomputed `.max`
unconditionally on *every* pending swap, which visibly slid the bar for that case even though the
number box read identically before and after (each historical season's real observed max differs
slightly). `updateThresholdRange()` mirrors the same two-trigger structure at Apply time, off
`currentRecords` instead of `playerPoolRecords`. **Gotcha, still relevant**: don't read
`els.threshold.value` to decide whether to clamp *after* already assigning a lower `els.threshold.max`
— a native range auto-clamps its own `.value` to a newly-lowered `max` the instant it's assigned, so
that read silently compares an already-corrected number against itself and skips clamping
`thresholdNumber` (which has no such auto-clamp). Capture `els.thresholdNumber.value` *before* touching either `.max`.
