# UI layout, card positioning, fuzzy search, PNG export, table sizing

> **Load when:** touching control-bar CSS, breakpoints, card drag/resize/fold, fuzzy matching, or PNG export.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Control-bar sizing** (`frontend/style.css`): the 7 filters in row 1 (Season, Teams, Players, Category,
Position, X axis, Y axis) always share ONE row at desktop widths (>= 861px) and scale as a group.
Each control declares its default width exactly once, as a unitless custom property `--w` (72 for
Season, 150 for the rest, set on `.control` / `.control-season`). That one number feeds two things:
the fixed default width of its `<select>` / the shared `.teams-select-btn` (reused verbatim for the
Teams and Players buttons) / `.control-players`, via `calc(var(--w) * 1px)`; and, inside the
consolidated `@media (min-width: 861px)` block late in the file, the flex weight `flex: var(--w) 1
0px`. A **zero flex-basis** is deliberate: flex-wrap picks line breaks from each item's hypothetical
size and never shrinks items to dodge a wrap, so a basis of `--w` would strand Y axis on its own
line the instant the bar dropped under 1080px (72 + 6*150 + 6*18px gaps). With basis 0 the row's whole
free width is split purely by flex-grow, so every control is the same multiple of its default
(exactly 1.0x at a 1080px bar, ~0.68x at 861px, ~1.5x at the 1680px layout cap) and Season:others
stays 72:150 throughout. Three floors keep content legible, all declared in that same block: every
control has `min-width: 60%` of its default (a safety net, never reached >= 861px); Season's floor is
its full default, since a clipped year ("2...") is unreadable, so it holds 72px while the other six
absorb the shrink (and still grows proportionally on the way up); Players' floor is `min-content`
so its PLAYERS button + Clear link never poke past the control edge (a few px wider than
proportional, only near 861px). Selects/buttons still elide long text with `text-overflow:
ellipsis`, so narrow windows show e.g. "All Te..." rather than growing any one control. Below 861px
the bar becomes the mobile drawer (single column, Players hidden), untouched by any of this —
including `flex: ... 0px`, which is why it lives inside the min-width media query: in the drawer's
column layout that basis would read as a height (same hazard as `.control-slider`). Phones rendering
the disguised 1024px layout (see `frontend/index.html`) land in this same regime (~0.85x). This
replaced an earlier design that split the bar into two stretched rows below 1150px via a
`.row-break-narrow` spacer (removed); that design also had a latent gap between ~1151-1171px where
Y axis was stranded alone. Keep any future tweak to these controls' widths in the one consolidated
block — an earlier version split an override like this across two locations and a same-specificity
base rule declared later silently cancelled it (caught by a QA pass, not by inspection). To add or
resize a filter: set its `--w`, add it to the block's selector lists; nothing else needs touching.
If a future control wraps a plain `<input>`/`<textarea>` in this row, give it an explicit width
rather than trusting flex-basis — a bare input carries a UA-default intrinsic width (~160px+).

**Three card types share one positioning system** (`cards-base.js` + `scout-card.js`/
`merge-card.js`/`linemate-card.js`, gated by `isDesktopScoutLayout()`, i.e.
`document.documentElement.clientWidth >= 860`). That used to mean "desktop/tablet only, never
phones" — no longer strictly true: phones now get a viewport-meta override (see
`frontend/index.html`'s inline `<script>` right after `<meta name="viewport">`) that renders the whole page at a fixed desktop-width layout, auto-scaled down to fit the real
screen, which pushes the layout viewport past 860 there too. Tablets in portrait (768px, below the
breakpoint) are the one case still on the mobile stacked-card path, same as before.

**This breakpoint (and `data.js`'s `targetLogoPx()`/`render.js`'s `isMobile`, the same 860 cutoff)
deliberately reads `document.documentElement.clientWidth`, not `window.innerWidth`** — a real bug,
fixed post-ship: iOS Safari updates `innerWidth`/`innerHeight` to the zoomed *visual* viewport on
pinch-zoom (Chrome stopped doing this in v48), so pinching in on the chart — exactly the gesture the
phone viewport-meta override above expects users to make — could transiently drop `innerWidth` below
860, fire the `window` `resize` listener (`main.js`), and flip `isDesktopScoutLayout()` false with no
real layout change, hiding the entire Pinned Players panel until an actual resize/rotation. `clientWidth`
tracks the layout viewport on every engine and ignores pinch-zoom, so it's the correct read for any
desktop/mobile breakpoint check. Popup placement is a separate concern from breakpoints: every floating popup (`info-popover.js`'s click popovers, including the header Install menu, and `linemate-card.js`'s hover tooltip) is placed by `popup-position.js`'s `placePopup()`, which clamps against `window.visualViewport` (offset/size/scale) so a pinch-zoomed page can't strand a popup off-screen, falling back to `innerWidth` when the API is missing. Its clamp is the pure `computePopupPlacement()` (unit-tested); an open info popover closes on any visual-viewport resize/scroll rather than re-placing. New popups must go through `placePopup()`, not their own math. Add any future desktop/mobile breakpoint check against
`clientWidth`, never `innerWidth`.

Player Cards (`openScoutCard()`, one per pinned player, keyed by `record.player` in `scoutCards`),
Merge Cards (`openMergeCard()`, keyed by a generated id in `mergeCards`), and Linemate Association
Cards (`openLinemateCard()`, keyed by the anchor's player string in `linemateCards`) are all
cloned from their own `<template>` in `index.html` but share the `.scout-card` class, so they fall
into the same drag (`beginScoutDrag`/`onScoutDragMove`/`endScoutDrag`), z-index
(`bringScoutCardToFront`), cascade-on-open (`cascadeScoutCardPosition`, gated by
`openCardsCount()` — the sum across all three maps; each successive card's offset is
`(openCardsCount() % SCOUT_CASCADE_WRAP) * SCOUT_CASCADE_STEP`, wrapping every 8 opens so a long
run of cards can't cascade their way off the panel edge), and mobile stacked-column CSS as Player Cards
always have — no parallel system to keep in sync. Every open card carries `{id, origin, folded}`
(`origin` is `'seed'` / `'merge'` / `'linemate'`) so a future recommender can read merge
provenance without depending on a card's current member set. **This field has no reader yet** — it
looks unused today but is intentionally in place for the v2.0.0 clustering recommender ("IE"); don't remove it as dead code.

**The fuzzy-match engine (Players filter, Pinned Players search, Merge Create/Edit) is hand-rolled
on purpose** — layered prefix/substring/token-prefix/Ratcliff-Obershelp scoring, no npm dependency.
Levenshtein and off-the-shelf fuzzy-match libraries were considered and rejected: this needed to
stay debuggable and dependency-free. Don't swap in a library "for simplicity" without revisiting that tradeoff.

**Fold/Unfold and free edge-resize both exist, on every card type.** All three card types have a
fold button (`toggleCardFold()`) toggling `.scout-card.is-folded`, a CSS-only two-state switch —
folded hides the metric body (stats table / merge table / linemate roster+summary) and leaves just
the header, no inline height, no min-size clamp. A Player Card's linemate-toggle button lives in
`.scout-card-actions`, a row that stays visible even while folded, so it doesn't require unfolding
first (merging happens through Pinned Players' Create popup instead, see below — never a checkbox
here). A Linemate Card's fold button passes `toggleCardFold()`
an `onUnfold` callback that resets its "See more" state back to collapsed every time the card
re-expands, rather than leaving a stale expanded roster behind — see `openLinemateCard()`.
Independently, every card type also gets 8 edge/corner resize handles
(`attachScoutResize()`/`beginScoutResize()`/`onScoutResizeMove()`/`endScoutResize()`) so a card can
be pulled to expand or pushed to shrink like a native window — width lives as an inline style on
`.scout-card` itself, height as an inline style on `.scout-card-panel` (overriding its open/close
`max-height` transition via `panelEl.style.maxHeight = "none"`). Folding a card that's been resized
taller stashes the panel's inline height in `panelEl.dataset.resizedHeight` and clears it (so the
folded header-only card isn't left with a tall dead gap), then restores it on unfold —
`toggleCardFold()` owns that stash/restore. `clearScoutCardDragPositions()` (fired on the `resize`
window listener when the layout drops below 860px) strips left/top/right/width plus the panel's
inline height/max-height/`resizedHeight` for every open card of every type, so inline overrides
from dragging or resizing can't survive a drop into the mobile stacked layout. **Fold and resize
also talk to each other directly, not just independently coexist:** `beginScoutResize()` auto-
unfolds a folded card the instant its north/south edge is grabbed (a folded card's body is
`display: none`, so dragging its height open would reveal nothing without unfolding first) —
measuring the gesture's starting rect only after that unfold, so the drag's math reflects the
now-unfolded layout, not the collapsed one. The reverse happens at `endScoutResize()`: pushing a
card's height down to the resize floor (`SCOUT_RESIZE_MIN_HEIGHT`) auto-folds it and syncs the fold
button, since a card manually shrunk to its minimum reads as "collapse this" rather than "leave it
open at its smallest size."

**PNG export exists at both the chart level and the per-card level, and both share one footer.**
The chart's own Save PNG button (`attachEvents()` in `main.js`) calls `chart-export.js`'s
`exportChartPngWithFooter()`, which renders via `Plotly.toImage` at a fixed 1200×750 logical size
with `scale: 2` (kept close to the on-screen ~1100×720 render so exported label/font proportions
match what's on screen — a larger logical size than that made text look shrunken relative to a
merely upscaled image) and temporarily swaps the chart's transparent `paper_bgcolor`/`plot_bgcolor`
for `--turf-800` (`#16301f`) so the export doesn't composite onto white, restoring transparency
after (guarded by `setLogoRelayoutGuard()` so the swap itself doesn't retrigger the logo/label
relayout handler). Every card type's Save button (`.card-save-btn`, wired once at open time via
`card-export.js`'s `attachCardSave()`) instead uses the vendored `html2canvas` (`npm run
vendor:html2canvas`, committed the same way Plotly's bundle is), since a card is real DOM, not a
Plotly figure — `exportCardPng()` clones the card off-screen (`buildExportClone()`) rather than
mutating the live one, so a user's current fold/drag/resize/scroll state is never disturbed by
exporting it. That clone gets its `is-folded`/drag/resize state cleared, its panel's
`max-height` opened up, and any `.merge-table-frozen` sticky column, and the Read layout's `.merge-read-frozen` head block, forced to `position: static`
(sticky has nothing to scroll against in a detached fixed-position clone and drifts to the row's
right edge otherwise) before any of the card's own `overflow:auto` scroll strips
(`.merge-table-wrap`, `.linemate-summary-wrap`) are unclipped and the card widened to fit — so the
export always shows the full card, never whatever happened to be scrolled/collapsed into view. An
optional `prepareClone` callback lets a card type do more before capture: Linemate Card's is the
first user, force-rendering its full roster into the clone regardless of on-screen "See more"
state, since a collapsed roster's hidden rows were never in the DOM for html2canvas to reveal. Merge Card's is the second: it re-renders the clone in the Read layout
(see `CARDS.md`, "Merge Card layouts"). A `prepareClone` that changes the layout returns `true`, and `exportCardPng()` then runs `fitCloneToContent()` again, which starts from the card's
natural width so a clone widened for the Sort layout can shrink back; returning nothing leaves the sizing as it was. The `.merge-mode-switch` and `.merge-card-scroll-hint` elements are ignored by the export.
Both export paths funnel through the same `compositeFooterCanvas()`/`drawExportFooter()` in
`chart-export.js` (`card-export.js` imports rather than duplicates them) so every PNG the app
produces — chart or card — carries the identical `EXPORT_FOOTER_TEXT` credit strip, drawn onto a
canvas widened if needed to fit that text at the export's own scale (a narrow Player Card export
can otherwise clip it). `compositeFooterCanvas()` also takes an optional `{ appendixNotes }` — see
"Include metric notes" below for how each of the four export call sites builds that list and why the
chart's own Save Plot call is the one exception that never passes it.

**Merge/Linemate table cell sizing and alignment** (`style.css`'s `.merge-table`/`.linemate-table`
blocks): row padding on `.merge-table th`/`td` is 11px vertical (bumped up from an original 6px) —
a taller row was the fix for the Comparison (Merge) Card reading as visually flat once the column
count grows, since more columns only add width, not height, to a card whose export sizing is
content-driven (see the PNG export paragraph above). `.linemate-table` was deliberately left at its
original 6px — the padding bump was scoped to the Merge Card's specific "flat" complaint, not
applied as a blanket table restyle. Every percentile chip cell (`.merge-metric-cell`,
`.linemate-metric-cell`) is centered rather than right-aligned, via `.merge-table td.merge-metric-cell`
/`.linemate-table td.linemate-metric-cell { text-align: center; }` — note the compound selector: a
bare `.merge-metric-cell { text-align: center; }` has lower specificity (one class) than the base
`.merge-table td { text-align: right; }` rule (class + element) and would silently lose regardless of
source order, the same specificity trap this file already calls out for the control-bar block above.
Any future per-cell override on these tables needs at least `.merge-table td.<class>` /
`.linemate-table td.<class>` to actually win.

**Mobile and layout gotchas** (carried over from the retired `BLUEPRINT.md` §2.6, 2026-10-17)

- **Bare `1fr` and flex items do not shrink below their content's natural width.** Opening a Player Card plus a Linemate Card on a phone once
  widened the whole page, traced to `.board` using `grid-template-columns: 1fr`, whose automatic minimum follows the widest item (the
  10-column roster table). The fix is `grid-template-columns: minmax(0, 1fr)`, plus `min-width: 0` on `.scout-cards`' mobile flex rule as
  defense in depth. A since-removed mobile-only re-declaration of a bare `1fr` had already reintroduced this once, so check the comment at the
  top of the `@media (max-width: 860px)` block in `style.css` before touching `.board` or `.scout-cards`.
- **Pinch-zoom on the chart is native and page-wide.** `.chart-panel` uses `touch-action: manipulation` (it used to be `none`). Pinching zooms
  and pans the whole page, header and controls included, not a chart-scoped transform. `manipulation` rather than `auto` keeps single-tap-to-open-a-card
  instant, because `auto` also enables double-tap-zoom and its ~300 ms delay. Plotly's own data zoom and pan stay off
  (`scrollZoom: false`, `dragmode: false`, `doubleClick: false` in `render.js`), so this is purely browser zoom over a static rendered image.

## Card corner buttons

Every card type (scouting, Comparison, Linemates) shares three round buttons in its top right, as
solid discs 24 px across at `right: 10px` (Close), `40px` (Fold) and `70px` (Save), `top: 10px`:
**Close** bright coral (`--card-btn-close`, `#ff6b5e`), **Fold** sky blue (`--card-btn-fold`,
`#5ec8f2`), both with a dark `--turf-950` icon; **Save** pure black with a 2px `#f0ede4` outline and a
`--chalk` icon, the same look as the Save Plot and Create buttons (black alone would merge into the
green card). Hover and keyboard focus show a 2px `--chalk` ring. The size is deliberately small: long
player names must not be crowded, so a bigger circle was rejected (the original 22 px grown by 1.1 and
rounded). `tests/test_card_buttons.py` checks size, distinct fills and contrast from `style.css`.
All three stay ignored by the PNG export (`shouldIgnoreForExport`, `attachCardSave()`).
