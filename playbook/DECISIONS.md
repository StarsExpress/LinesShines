# Decisions

Single source of truth for what was decided, what looks wrong but is intentional, and what was rejected.
**Before "fixing" anything odd, search this file.** This is a short list, not a log. A decision with a reason goes
into the matching section below; implementation detail goes into `architecture/` (see `architecture/INDEX.md`). Add a
date only when a decision replaces an earlier one. Do not record decisions in `CLAUDE.md`.

## 1. Looks like a bug or dead code, but is intentional

| Item | Why | Detail |
|---|---|---|
| `origin` field on cards looks unused | Reserved for the IE recommender (deferred). Do not remove as dead code. | `architecture/UI-LAYOUT-AND-EXPORT.md` |
| Fuzzy matcher is hand-rolled | Must stay debuggable and dependency-free. Levenshtein and fuzzy libraries were considered and rejected. Do not swap in a library "for simplicity". | `architecture/UI-LAYOUT-AND-EXPORT.md` |
| RSWA uses each linemate's raw, uncapped snap count; the Linemate Card has no roster cap and no "See more" | A cap understated the summary. The snap threshold is the only gate, so every qualifying linemate is on the card. Linemate Cards stay outside the Pinned Players quota. Do not reintroduce a cap. | `architecture/CARDS.md` |
| `computeLinemateRoster()` never sees the anchor; "include anchor" is a separate toggle, default off | Keeps the roster-size note and caps teammates-only. | `architecture/CARDS.md` |
| Teams and Players combine by union (OR), never intersection (AND) | Selecting a player while Teams is at the full 32 auto-resets Teams to none (all-32 case only; any partial team selection plus players is valid). | `architecture/FILTERS-AND-SEARCH.md` |
| Teams only highlights (dims the rest); it never shrinks the percentile pool | The pool is defined by season, position and threshold only. | `architecture/FILTERS-AND-SEARCH.md` |
| The Players search pool has its own live, non-Apply-gated data track | The chart stays Apply-gated; the pool stays live. Never read `currentRecords` from search code. | `architecture/FILTERS-AND-SEARCH.md` |
| Below-threshold matches are a second search pass, never auto-popped; the query text is left untouched | Must never alter what the normal dropdown shows. | `architecture/FILTERS-AND-SEARCH.md` |
| Axis direction is per metric (`higher_is_better`), not per category | PBE / TPS PBE are higher-is-better despite being pass-block. | `architecture/METRICS-AND-NOTES.md` |
| Default axis pairs cross "raw rate" and "PFF composite, TPS" metrics | Surfaces PRP/PBE. | `architecture/METRICS-AND-NOTES.md` |
| `DYNAMIC_THRESHOLDS` is keyed by a literal season year and edited by hand each week | A computed key would freeze at import time and could never be "missing". Thresholds are eyeballed, not formula-derived. | `architecture/THRESHOLDS.md` |
| The threshold is a display filter only | Preprocessing never reads it; every row is ingested. | `architecture/THRESHOLDS.md` |
| Threshold input `.max` moves only when the value needs it | Prevents clamp flicker and stale clamps. | `architecture/THRESHOLDS.md` |
| Breakpoints and popup placement read `clientWidth`, never `innerWidth` | Real bug fixed earlier. | `architecture/UI-LAYOUT-AND-EXPORT.md` |
| Chart Save Plot never passes `appendixNotes` to `compositeFooterCanvas()` | Chart notes are live Plotly annotations; passing them would draw them twice. Card exports do pass them. | `architecture/METRICS-AND-NOTES.md` |
| Linemate Cards are not checked individually during pool-change invalidation | Their roster derives from the anchor plus applied filters. | `architecture/PINNED-INVALIDATION.md` |
| Team codes use PFF spellings (`ARZ`, `BLT`, `CLV`, `HST`) | Defined once in `teams/nfl.py`; the frontend never hardcodes team data. | `architecture/BACKEND-AND-DEPLOY.md` |
| No Alembic; schema changes need a manual `ALTER TABLE` on Railway | Adding a column reaches local sqlite for free, not production. | `architecture/BACKEND-AND-DEPLOY.md` |
| Rank ties share one rank and percentile (competition ranking) | A tiebreak would misrepresent equal performance. | `architecture/PERCENTILES.md` |
| The chart panel uses `touch-action: manipulation`, not `auto` or `none` | Native pinch-zoom and pan are wanted, but `auto` would also turn on double-tap-zoom with its ~300 ms delay and break tap-to-open-a-card. Plotly's own zoom and pan stay off (`scrollZoom: false`, `dragmode: false`, `doubleClick: false`). | `architecture/UI-LAYOUT-AND-EXPORT.md` |
| Pass Cov Percent and TPS Pass Cov Percent are left out of the Linemate Card's Line Summary (`line_summary: false`) | A line mixes ED and DI, whose coverage shares differ too much for one Min/Median/Max/RSWA. The roster table still shows each player's own percentile. | `architecture/METRICS-AND-NOTES.md` |
| The preprocessing command requires `--league` and `--seasons`, with no default | The wrong league is never processed by accident. | `architecture/BACKEND-AND-DEPLOY.md` |
| Career accepts known limits | Alumni means recently active on the 2022 to 2026 NFL table, not all-time. A transfer from an out-of-scope school keeps only his in-scope seasons. LB is not exposed. Joined NFL is matched within the category. Newly drafted players stay Prospects until an NFL ingestion is followed by an NCAAF one. A college `player_id` is shared with the NFL files (836 ids), so joins use the id, never the name. | `architecture/BACKEND-AND-DEPLOY.md` |

## 2. Rejected approaches (do not reopen without a new reason)

- Hover interactions on the chart.
- CSS-transform zoom. Mobile uses native pinch-zoom of the rendered chart instead.
- URL sharing of chart state. PNG export is the share mechanism; a page refresh clears the Workspace.
- Sample-data infrastructure.
- Cloud auto-ingest of the weekly data (Google Drive plus GitHub Actions): no human review step, and pointless re-ingestion churn.
- scikit-learn for the IE clustering (it cannot express contrast or transitional merging).
- Automating the weekly data update. It stays a manual, reviewed step.
- Making the phone chart wider with a per-element hack. Two attempts were tried and reverted in one session: a permanently 1100px-wide chart
  panned by horizontal scroll, and the same canvas shrunk by a JS-computed `transform: scale()`. The results were a 1:1 desktop slice, or
  everything at about 35% and illegible. The phone viewport-meta override (`architecture/UI-LAYOUT-AND-EXPORT.md`) replaced both.
  Do not bring either back without a concrete reason.
- Lazy-fetching other positions when a Linemate Card is first opened. The existing records endpoint returns every position of the selected
  season and category in one response and the client filters to the selected position. Reasons: no new endpoint or round trip, and no second
  cache to invalidate (a stale-percentile bug in a lazy cache would be silent). Volume is small (roughly 79 ED + 95 DI at typical thresholds).
- Refreshing a Merge Card in place on a general pool change. It can hold up to 5 players, possibly across positions, which is far more
  surface than the confirm-and-rebuild flow costs. The Below Threshold quick-set is the one scoped exception (`architecture/FILTERS-AND-SEARCH.md`).
- Removing pinned work without a confirmation. A merge is deliberate analytical work and is not cheap to rebuild, unlike Players-filter chips,
  which are dropped silently. A confirmation precedes removals; none is shown when nothing is pinned or when the outcome is unaffected or refresh.
- Building a Merge Card by multi-selecting already-open Player Cards and pressing a Merge button, or by dragging cards onto each other.
  The Create popup with its own staged selection is used instead (Cancel discards, Submit builds); membership changes only through the
  card's Edit popup.
- `?v=` on module URLs or an import map for cache busting (URLs stay clean), an "update available" notice (the app should always run the latest version), and reproducing the bug before the preventive fix (`architecture/PWA.md`).
- Making player names clickable in the Linemate roster. A "Card" button column is used instead: it keeps names plain and carries over to the Read layout.

## 3. Process conventions

- The working rules (git, order of work, definition of done, PFF data, frontend limits, versioning) live in `INVARIANTS.md`, section "Working rules".
- Work tracking: each topic still being discussed is its own file in `playbook/discussions/`; each decided piece of work, with enough detail to start,
  is its own file in `playbook/next_steps/`. Deciding a topic means moving its file from `discussions/` to `next_steps/` (rename nothing); finishing
  means deleting it from `next_steps/`. Nothing is numbered or ordered, because relative priority changes at any time. Claude Code acts only on the
  `next_steps/` file the owner names.
- 2026-10-24: `next_steps/` files are kept current: a decision that replaces earlier text rewrites it in place instead of layering revision notes, and with more than one Claude session running, each reads `next_steps/` and re-reads a file before editing it (`INVARIANTS.md`, "Working rules").
- Release notes: the title is `🏈LinesShines vX.Y.Z — 2026 Week N`, and the version in the title must match the tag before publishing. Use the exact terms
  `Pinned Players` and `Linemates`, and singular verbs for the product name. Write what the user gets, not the mechanism.
- Cap the time spent on tooling and process work. It supports the product and is not the product.
- Ingestion is deliberately not pre-approved in `.claude/settings.local.json`, because it writes to whatever `DATABASE_URL` points at.
- Every Markdown file name under `playbook/` is upper case (extension stays `.md`); `ROSTER.md` does not state this.
- CI has `test` (push and pull request) and `browser` (pull request only, `REQUIRE_CHROMIUM=1`). `main` accepts only pull-request commits, so a push to `main` runs only `test`, which keeps Railway's "Wait for CI" fast. `browser` is a required check next to `test` and `lint`; required checks match the job name, so the fast job keeps the name `test`. No xdist for now. Never wait on async work with `page.wait_for_function` (it does not await a Promise); use `wait_until`. The smoke tests cover INVARIANTS 4, 9, 10, 11, 16 and 17.

## 4. Direction

- v2.0.0 is led by NCAAF (college) data; the Insight Explorer (IE) recommender is deferred to a later release.
- `/` stays the NFL page (external links and the PWA `start_url` depend on it). College data lives under `/ncaaf`.
- College and pro charts stay separate.
- Analysis is per player, not per team aggregate. The snap threshold sets the comparison-pool size and screens out garbage-time snaps; it is not a quality filter.
- Keep domain configuration separate from the engine where that is cheap, but do not abstract in advance for sites that do not exist yet.
- College data covers 2018 to 2026. 2014 to 2017 are deliberately not loaded until the owner decides how many players the Career chart should show; loading them is a run, not a code change.
