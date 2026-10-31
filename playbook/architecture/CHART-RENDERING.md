# Chart rendering: dimming, labels, axis inversion

> **Load when:** touching render.js, label decluttering/emphasis, or axis direction.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Teams/Players filtering dims non-matching players on the chart; it never removes them**
(`render.js`'s `isDimmed`, `config.js`'s `DIM_OPACITY`): a player whose team isn't in the current
Teams selection (and who isn't individually added via Players) still plots, at reduced marker/
label/logo opacity, rather than disappearing — the point is to see a highlighted subset *in context*
against the rest of the pool, not to shrink the pool itself (contrast with the Snap threshold filter,
which does genuinely drop rows). `highlightSubtitle()` is therefore just a count line — a plain
"N players with at least X <field>." on a Season page, or two lines on the Career page (Potential
Draftees first, then Joined NFL, each with its own count and bar); it never names the highlighted
teams/players.

**Player labels get three independent treatments on top of each other: dim-in-place, collision
declutter, and bold/halo/glow emphasis** (`render.js`) — this grew out of repeated Reddit feedback
("extremely hard to read," then "even bolder") and the two problems (legibility vs. readable
density) are solved by genuinely separate mechanisms, not one dial:
- **Dimming** reuses the same `isDimmed` array as the marker/logo treatment above — a non-
  highlighted player's label renders at `DIM_OPACITY.label` instead of `LABEL_ALPHA`, via Plotly's
  native `textfont.color` (an alpha channel Plotly *does* support).
- **Collision declutter** (`computeKeptLabels()`) hand-rolls an adjustText-style decluttering pass
  with no library dependency, same philosophy as the fuzzy-match engine above: each player gets an
  approximate pixel bounding box (sized off `POINT_LABEL_FONT_SIZE` via a `FONT_SCALE` factor, so a
  future font-size change can't silently desync the collision math from the text it's measuring),
  processed in descending `threshold_field` order so star players claim space first, with
  highlighted (non-dimmed) players given a `HIGHLIGHT_BOOST` priority bump so a Teams/Players
  selection never loses its own labels to an unrelated bigger name. A label is kept only if its box
  doesn't overlap one already placed; everything else is blanked (`text: ""`), not hidden via CSS —
  Plotly needs the trace text itself cleared for the hover/click target to stay centered on the
  marker rather than an invisible label's box.
- **Bold + halo + glow emphasis** (`applyLabelEmphasis()`) is the "bolder" half of the Reddit
  follow-up, applied only to spotlighted (non-dimmed) labels. Plotly's `textfont` schema has no
  font-weight, stroke, or filter/drop-shadow property at all, so this is done as direct inline SVG
  style patching on the rendered `<text>` nodes *after* Plotly renders, matched via Plotly's own
  `data-unformatted` attribute (the exact current label text) rather than DOM index or structure —
  robust to Plotly recreating those nodes across re-renders. Every non-spotlighted node's styles are
  explicitly cleared, not just skipped, since a Teams/Players change can un-spotlight a player
  between renders and an un-cleared halo would otherwise go stale. The halo/glow constants
  (`LABEL_EMPHASIS_WEIGHT`/`LABEL_HALO_WIDTH`/`LABEL_HALO_COLOR`/`LABEL_GLOW_BLUR`/`LABEL_GLOW_COLOR`)
  are exported, not local, because `chart-export.js`'s PNG export redraws this same emphasis onto a
  canvas by hand (Plotly's own `toImage` regenerates its SVG from its internal model, not the live
  DOM-patched chart, so the emphasis would otherwise vanish from every exported PNG) — sharing the
  constants is what keeps that canvas redraw pixel-matched to the on-screen version instead of a
  second hand-tuned copy drifting over time. Unstyled label text resolves to Oswald weight 450 (one
  of two Oswald instances `index.html` loads, 450/600) purely through the browser's own nearest-
  weight-above-400 CSS font-matching, since `textfont` sets no explicit weight — a subtle,
  easily-broken convention worth knowing before touching `index.html`'s font `<link>` or this file's `family` string.

Separately, dashed median reference lines (one per axis, `shapes` + `medianAnnotations` in
`render()`) always draw against the currently filtered/thresholded pool, matching the `meta-band`
copy in `index.html` ("Median lines are calculated according to current filter").

**Axis inversion is per-metric, not per-category** (`render.js`'s `xReversed`/`yReversed`, derived
from `xMeta.higher_is_better`/`yMeta.higher_is_better`): this used to be a single `reversed` flag
keyed off `appliedFilters.category === "pass_block"`, which only worked because every pass_block
metric happened to be lower-is-better at the time. PBE/TPS PBE (see "Metric semantics" below) broke
that assumption — they're higher-is-better despite being in the pass_block category — so each axis
now reads its own metric's `higher_is_better` flag independently. Don't reintroduce a category-wide
shortcut here; a category is allowed to mix directions.
