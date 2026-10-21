# Metrics, axis defaults, popovers, metric notes

> **Load when:** adding or renaming a metric, editing info popovers, metric notes, or the export appendix.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Metric semantics** (defined once, referenced from both `main.py` and `config.py` — keep in sync
if adding a metric): Havoc Rate = (Sacks + QB Hits) / Pass Rush Opportunities; Allowed Havoc Rate is
the pass-block equivalent over Non Spike PB Snaps. PRP (Pass Rush Productivity, pass-rush category)
and PBE (Pass Block Efficiency, pass-block category) are PFF's own composite 0-100 scores, passed
through unmodified from the raw PFF export (unlike Havoc/Pressure Rate, which this codebase derives
itself) — no `unit` suffix in `main.py`'s metric metadata, since PFF doesn't present them as strict
percentages. "TPS" prefix = the same metric restricted to true pass sets, for every metric including
PRP/PBE. `higher_is_better` is an explicit per-metric flag in `main.py`'s `PASS_RUSH_METRICS`/
`PASS_BLOCK_METRICS` dicts, not inferred from category or name — it drives frontend sort/color
direction and, in `render.js`, each axis's own inversion independently (`xMeta`/`yMeta`, not a
category-wide check). Direction by metric: every pass-rush metric is higher-is-better for the
defender; pass-block "Allowed" metrics are lower-is-better, but PBE/TPS PBE are the deliberate
exception — higher-is-better despite being in the pass-block category, same as PRP/TPS PRP on the
pass-rush side. Any future per-category direction shortcut (frontend or backend) must special-case
these two rather than assume category implies direction.

**Default axis pair per category** (`filters.js`'s `populateCategoryDependentControls()`): each
category seeds its X/Y metric selects to a distinct, curated pair rather than the first two entries
in `PASS_RUSH_METRICS`/`PASS_BLOCK_METRICS` — pass-rush defaults to Win Rate (X) vs. TPS PRP (Y),
pass-block to Allowed Pressure % (X) vs. TPS PBE (Y). Both pairs deliberately cross the "raw rate
metric" vs. "PFF's own composite score, true-pass-set variant" line rather than pairing a metric
against its own TPS counterpart (an earlier version defaulted to Win Rate vs. TPS Win Rate /
Allowed Pressure % vs. TPS Allowed Pressure %) — this surfaces PRP/PBE, the two metrics most likely
to get overlooked since they're not derived by this codebase and read less self-explanatory than a
named rate. Each `if`/`else if` branch checks both metric names exist in `metricKeys` before setting
them, falling through to the generic non-TPS/TPS heuristic (`else` branch) if a category's metadata
is ever missing one — so this never throws if `main.py`'s metric dicts change shape. Keep this pair
in sync with any future metric additions/renames in `main.py`.

**Metric-definition popovers on the X/Y axis controls** (`info-popover.js`, `main.js`'s
`axisFormulaContent()`, `utils/render_metric_formulas.py`): a small (i) trigger sits next to each
axis `<label>` (`frontend/index.html`'s `#x-axis-info-slot`/`#y-axis-info-slot`), opening a popup for
whichever metric that `<select>` currently holds — its *live* pending value (`els.xMetric.value`),
not `appliedFilters`, since axis changes are themselves pending-until-Apply but "what does this
metric mean" should answer for whatever's on screen in the dropdown right now. `main.py`'s metric
dicts carry two note-shaped fields, both optional: `note` (the Havoc/Allowed Havoc family) and
`formula_note` (the PRP/PBE family — added as a separate field rather than reusing `note`, back when
`note` alone still drove the now-removed top-right chart annotation below, so that adding PRP/PBE
notes wouldn't silently turn that annotation on for them too; both fields still feed the same
`collectMetricNotes()` today — see "Include metric notes" below), each paired with a `formula_svg`
path (e.g. `/images/metric_formulas/prp.svg`) when a rendered formula exists; metrics with neither
(Win Rate, Pressure Rate, Allowed Pressure %, ...) fall back to their short `pff_note` so the trigger
is never a dead end. Every "TPS "-prefixed metric's
popup additionally appends `metadata.tps_note` (config.py's `TPS_NOTE`, exposed once at
`/api/metadata`'s top level, never duplicated per metric) as a second, visually distinct paragraph —
`key.startsWith("TPS ")` is the only check, so this never needs updating per new metric.
`info-popover.js`'s `createInfoPopover()`/`openInfoPopover()` were extended to support this: `content`
may now be a function (called fresh at *open* time, not creation time, so it tracks the select's
live value) returning `{ imgSrc, imgAlt, extraText }` instead of a plain string; a `formula: true`
option switches the popup to a wider `max-content` box (`.info-popover-content--formula`) instead of
the standard fixed-240px text box. `content` can also be `{ text }`, `{ links }` (the header Install popup) or
`{ bullets: [...] }` (a bulleted list, one `<li>` per string with a gap between points, used by the Merge Card's
Read | Sort popup); `bullets` can sit beside a `text` paragraph. The `<img>`'s `load` listener re-runs `placePopup()` —
an SVG has no measurable size until its request resolves, so the first (synchronous)
positioning call sees a near-zero box and mis-clamps the popup's left edge; without the reposition-on-
load, the box visibly overflows the viewport's right edge once the image actually renders. The SVGs
themselves are pre-rendered, not drawn client-side — `utils/render_metric_formulas.py` is a dev-only,
build-time script (never imported by `main.py`/Railway) using matplotlib's built-in mathtext (no
system LaTeX/dvipng install needed — that's only required for `usetex=True`, which this doesn't use)
to typeset each formula and save it as a transparent-background SVG with text converted to vector
paths (`svg.fonttype='path'`, matplotlib's default), so the browser needs no font of its own to
render it. One SVG per metric *family* (`havoc_rate`/`allowed_havoc_rate`/`prp`/`pbe`.svg under
`frontend/images/metric_formulas/`, served for free since `frontend/` is already mounted wholesale as
static) — re-run `python -m utils.render_metric_formulas` by hand and commit the output whenever a
formula changes, same manual-regen convention as `npm run vendor:plotly`/`vendor:html2canvas`.
`matplotlib` is a `requirements-dev.txt`-only dependency, commented as build-time-only.

**Info-popover triggers and the header Install button** (`info-popover.js`, `main.js`'s
`attachEvents()`, `config.js`'s `PLATFORM_ICONS`, `style.css`): the shared `.info-popover-trigger`
is deliberately small (10px type, 1.5px border, 3px×8px padding) so it doesn't dwarf the control
labels; the four ⓘ-only triggers (Teams, Players, X axis, Y axis — each in its own
`#<name>-info-slot` inside an `.axis-label-row`, label then ⓘ) get an even tighter 1px border and
2px×5px padding via an id-scoped rule, while text-label triggers (the RSWA header) keep the base
size. Add a new filter ⓘ by copying that pattern, not by restyling the trigger.

**Install button** (top-right of `.hero`, immediately left of the untouched `.hero-github`) is
the same component in a hero-sized skin: `.hero-install` is absolutely positioned 64px from the
right (20px inset + GitHub's 36px box + 8px gap; 58px in the <860px block), and its trigger is
pinned to GitHub's exact box height (36px, 34px on mobile — computed from icon + padding + border,
and asserted equal by a test) with a black (`#000`) fill, matching GitHub's, kept on hover/open.
Its popup is `createInfoPopover()` with two extensions: `content` may carry `links:
[{href, label, hint, icon}]` (rendered as a list; picking one closes the popup, since on a phone it
would otherwise still cover the page on return from the new tab) and the option `alignRight: true`
(popup's right edge lines up with the trigger's so it opens down-and-left; popups holding `links`
also get `.info-popover-content--links` → `width: max-content` so the longest hint, iOS's, stays on
one line). The four options deep-link to `PWA.md` on GitHub — `#ios`, `#android`, `#macos`,
`#windows`. Those are GitHub's slugs for `## 📱iOS` etc.: the headings have **no space after the
emoji**, so there's no leading hyphen (a heading written `## 📱 iOS` would slug to `#-ios`); verify
against the rendered page's `user-content-*` ids if PWA.md's headings ever change. A
`@media (display-mode: standalone)` rule hides `.hero-install` entirely once the app is installed.
Platform logos are inline SVG — Simple Icons' 24×24 paths embedded verbatim (shapes never edited),
`aria-hidden="true"`, 17px, the text label carrying the accessible name. `PLATFORM_ICONS` maps each
platform to a list of `{d, fill}` shapes whose `fill` is a CSS variable from `style.css`'s `:root`
(`--logo-ios/-macos/-android/-windows-red/-green/-blue/-yellow`) — recolor there only. iOS and macOS
share the Apple path but have separate variables so they read apart; Windows' single Simple Icons
path is four subpaths, split into four `<path>`s (same coordinates; the last one's relative `m`
rewritten as the absolute point) purely so each square can take its own color. Label and hint
colors are not variable-driven.

**"Include metric notes" — export appendix and live chart notes** (`metric-notes.js`,
`chart-export.js`'s `compositeFooterCanvas()`, `render.js`'s `metricNoteAnnotations`): a checkbox in
`.control-toggles` (default OFF, unlike Player Names/Team Logos above it), driving two different
mechanisms depending on export type. `metric-notes.js`'s `collectMetricNotes(cat, metricKeys,
tpsNote)` is the shared logic both use — it reads each key's `note`/`formula_note` (falling back to
neither, never a placeholder line), **dedupes by note *text*, not by metric key** (so a metric and
its "TPS " counterpart collapse to one line for free, the same sharing `HAVOC_RATE_NOTE`/`PRP_NOTE`/
`PBE_NOTE` already do), and appends `tpsNote` once, last, if *any* key is "TPS "-prefixed — never
duplicated per TPS metric. `categoryAppendixNotes(cat, tpsNote)` is a convenience wrapper for card
exports: Player/Merge/Linemate Cards always render *every* metric in their category
(`Object.keys(cat.metrics)`, unconditionally, no subsetting by position or membership — confirmed
directly), so "which metrics appear in this card" is just "every metric in its category", not
something that needs figuring out per export instance. For the **chart**, "which metrics appear" is
exactly `[appliedFilters.xMetric, appliedFilters.yMetric]` (2 keys, varies per export) — but unlike
the three card types, the chart's notes are **not** export-only: `render()` reads
`els.metricNotesToggle.checked` live (wired to `render()` on `"change"`, same as Player Names/Team
Logos — see the "must NOT invalidate" list in `PINNED-INVALIDATION.md`) and draws each note as a real Plotly
annotation, left-aligned, at the bottom of the plot (`xanchor:"left"`, stepped down by
`NOTE_LINE_HEIGHT` per line), growing `margin.b` to fit. This replaced an earlier, retired mechanism
(`activeNotes`/`noteAnnotations`) that only ever covered the Havoc family, sat top-right, and was
always-on regardless of any checkbox — removed outright, not merely superseded, since this covers
every metric with a note and is opt-in. Each note line's `yshift` is anchored **strictly after** the
plot's own already-correct base bottom margin (`BASE_MARGIN_B = 56`, unchanged from before this
feature existed) rather than computed from a guessed tick-label + axis-title height — an earlier
version tried a flat `-34px` offset and it overlapped the axis title directly, since the real
combined height of ticks + title is taller than that; anchoring after the whole known-good region
instead makes an overlap impossible regardless of actual font metrics. Because this lives in
`els.chart.layout` itself (a real annotation, not a canvas overlay), `exportChartPngWithFooter()`'s
export clone — which deep-clones `chartDiv.layout` — picks it up automatically, so **the chart's own
Save Plot call deliberately never passes `appendixNotes` to `compositeFooterCanvas()`**, unlike all
three card types' Save buttons, which do (their notes have no live on-screen equivalent, so the
canvas-composited strip is the only place they ever render, sized by pre-wrapping each note against
the final canvas width before the canvas itself is created — same "measure first" ordering
`compositeFooterCanvas()` already used for the footer's own minimum width). Passing `appendixNotes`
to the chart's export too would draw the same text twice. **Every note is a bullet in every export:** the
chart's annotations are prefixed "• " (replacing the old "ⓘ "), and the card appendix canvas strip draws a
"•" in a bullet column (`APPENDIX_BULLET`/`APPENDIX_BULLET_INDENT`) with only a note's first line carrying
it — wrapped continuation lines hang under the text, so one bullet = one note.
