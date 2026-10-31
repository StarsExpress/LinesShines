# Frontend module structure

> **Load when:** touching ES-module layout, imports, shared state, or the client-side data model.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

The frontend (vanilla JS, no build step, no bundler) is split into ES modules under
`frontend/` — `<script type="module" src="main.js">` is the sole entry point index.html loads.
Layer boundaries follow the dependency graph, not feature buckets: `dom.js` (the `els` DOM-ref
lookup, ~230 call sites) and `config.js` (pure constants) are dependency-free; `data.js` (fetch,
`sliceCache`, `positionPool()`, percentile math, a preloaded `logoCache` of decoded team-logo
`Image` objects so a filter/render change never blocks on image decode) and `search.js` (the
hand-rolled fuzzy matcher) sit above those — `allTeamCodes()` lives in `data.js` rather than
alongside its sibling Teams-checklist helpers in `filters.js` (a historical placement: `render.js`
once needed it too, and importing from `filters.js` there would have created a circular import); `table-sort.js` (Excel-style click-to-sort: `toggleSortState()`/`sortRows()`/
`makeSortableHeader()`), `player-table-model.js` (pure, no DOM: the player table model shared by the Comparison and Linemate cards, with its Sort and Read layouts; the caller passes the identity columns), `info-popover.js` (`createInfoPopover()`, a click-toggled popup
distinct from `linemate-card.js`'s hover-only `attachAppTooltip()` — click survives on touch
devices with no cursor to dwell) plus `popup-position.js` (the one shared placement/clamp for
every floating popup — see "Popup placement" in the breakpoint note below), and `metric-notes.js` (`collectMetricNotes()`/
`categoryAppendixNotes()`, see "Metric-definition popovers" and "Include metric notes" below) are
all dependency-free leaves too, so any card module (or `render.js`/`chart-export.js`/
`card-export.js`/`main.js`, for `metric-notes.js`) can import any of them without adding a new
cross-module dependency; `cards-base.js` is the shared card
positioning system (drag/resize/fold/cascade/z-index) all three card types sit on;
`linemate-card.js` → `scout-card.js` → `merge-card.js` → `workspace.js` layer in that order
(Pinned Players' orchestration on top); `filters.js` and `render.js` sit beside each other on
`data.js` — except `render.js` also imports `scout-card.js`'s `viewFloatingCard()` directly (its
`plotly_click` handler opens/flashes a clicked player's floating card), a real dependency the
original modularization brief's table never listed, carried over unchanged from the pre-split
code and safe to keep since `scout-card.js` has no dependency back onto `render.js`; `chart-export.js` (PNG rasterization + the shared credit-footer compositing, see
below) was split out of `render.js` to keep that file under the project's ~600-line guideline —
it imports `render.js`'s label-emphasis constants (`POINT_LABEL_FONT_SIZE`,
`LABEL_EMPHASIS_WEIGHT`, etc.) but nothing about trace-building, so the dependency runs only
that one direction; `card-export.js` (the shared per-card Save-PNG button, see below) sits on
`chart-export.js`, not `render.js` directly, and is imported one-directionally by all three card
modules; `main.js` (event wiring, `attachEvents()`,
`loadMetadata()`, the boot call) depends on everything. A handful of narrow, deliberate circular imports exist where the original
single-file call graph genuinely goes both ways (documented in each file's header comment —
`cards-base.js` ↔ the three card modules for `openCardsCount()`/`updateScoutEmptyHint()`;
`merge-card.js` ↔ `workspace.js` for `renderPlayerCardsSpace()`) — safe because every use is
inside a function body, never at module-evaluation time. Cross-module mutable state (e.g.
`metadata`, `currentRecords`, `appliedFilters` in `data.js`) is owned by one module and
exposed to writers elsewhere via a thin exported setter (`setMetadata()`, etc.) since ES
modules don't let an importer reassign an imported `let`. This module split was carried out
against a since-removed implementation brief (`MODULARIZATION.md`, v1.3.0); it's stable enough
now that the brief no longer earns its keep, but each extracted file's header comment still
records which step of that brief it came from, for provenance.
The app calls the three API endpoints without a `position`, caches each fetched category+season
slice in memory (`sliceCache`, keyed `${category}:${season}`), and does all filtering (position,
min-snap threshold), axis selection, and label/logo toggling client-side against that cache —
re-fetching only on season/category change. Holding every position client-side (not just the
selected one) is what Merge/Linemate Cards below build on. Plots use the vendored
`frontend/vendor/plotly.min.js` (fetched via `npm run vendor:plotly`, committed to the repo
since Railway doesn't run `npm install` for the frontend).

## One frontend, two leagues (`LEAGUE`)

The NFL and NCAAF season pages are the same `index.html` and the same modules. `main.py`'s `render_page()` fills
`window.LEAGUE` into the page and `data.js` exports it as `LEAGUE` (falling back to the NFL values if the page was
served raw): `key`, `name` (used in the chart title), `apiPrefix` (`/api/nfl` or `/api/ncaaf`, used by `fetchSlice()`
and `loadMetadata()`), `logoDir` (`logos/{logoDir}/{team}.png`), `teamGroups` and `teamLabel`. Positions, metrics and
default thresholds already come from `/api/{league}/metadata`, so the config holds nothing else.

- **The Career page (`/ncaaf-career`).** A third entry in `main.py`'s `PAGES` with `mode: "career"` and its own
  `apiPrefix` (`/api/ncaaf/career`); `data.js` exports `IS_CAREER`. It reuses every module. Its payload is shaped like a
  Season one in `setMetadata()` (one "season", the word `Career`, one flat conference map), so the controls, titles and
  cards stay shared (a card reads "Alabama · Career"). What differs: `main.js` hides Season and shows the Status
  Filter (a dropdown of two checkboxes built like Teams, `#status-toggle-btn`, `#status-joined` / `#status-potential`) and a second bar (`#threshold-potential-*`);
  `fetchSlice()` has no season in the URL; the applied state carries `potentialThreshold` and `statuses` (left out on a
  Season page); `filters.js`'s `thresholdBars()` is the one list the range, default and reset code loops over (one bar on
  Season, two on Career, each bar's slider ceiling taken from its own status). A threshold is read through
  `appliedThreshold()` / `pendingThreshold()` and judged by `pinned-impact.js`'s `meetsThreshold()`, which accepts a number
  or `{ joined, potential }`, so no call site compares a record with a bare number any more.
- **Team key vs label.** `record.team` is the NFL code but the NCAAF franchise id (a number). Keys, logo file names and
  `metadata.teams` lookups use it as is; anything the user reads goes through `teamLabel(team)` (the code for the NFL,
  the school name for the college). Comparisons with the Teams checklist go through `String(...)`.
- **NCAAF logo variants.** The college logos in `frontend/images/team_logos/ncaaf/{franchise_id}.png` are ESPN's `dark`
  variant (readable on the dark chart), except 11 schools whose `dark` variant came out too bright and use the original
  (`default`) one: Alabama 103, Kentucky 202, Tennessee 307, Vanderbilt 333, Indiana 190, Clemson 140, Duke 154,
  North Carolina 245, Texas 311, Utah 328, Buffalo 126 (franchise ids). When re-downloading with
  `tools/download_ncaaf_logos.py`, skip these ids (or run them with `--variant default`), or the originals are
  overwritten.
- **Teams checklist.** `populateTeamsChecklist(season)` builds it from `teamGroups(season)`: `static` is the NFL's
  fixed AFC/NFC divisions in `config.js`; `by_season` is the college's conferences taken from the metadata's
  `team_conferences[season]` in `conference_order`, schools by name, with each conference header a button that selects or
  clears the whole conference. The college checklist is rebuilt when the Season or Category changes (a school's
  conference depends on the season); the teams the user unchecked are remembered across rebuilds (`uncheckedTeams`).
- **Page switch.** The `.league-nav` links (one URL per page, current one marked) are filled by `main.py`; below 860px
  they hide behind a hamburger button (`#league-nav-toggle`) that closes on Escape and on an outside click, with the
  same `isTrusted` guard as the other dropdowns. It sits in the hero's top row, which is not part of any PNG export.
  In the installed desktop app it is pushed right by 110px (unverified: the window buttons' exact width).
