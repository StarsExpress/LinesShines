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
`makeSortableHeader()`), `info-popover.js` (`createInfoPopover()`, a click-toggled popup
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
