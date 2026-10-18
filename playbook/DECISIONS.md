# Decisions

Single source of truth for what was decided, what looks wrong but is intentional, and what was rejected.
**Before "fixing" anything odd, search this file.** Add new significant decisions at the bottom of the
relevant section with a date. Do not log decisions in `CLAUDE.md`.

Detail for each item lives in `architecture/` (see `architecture/INDEX.md`); this file is the short list.

## 1. Looks like a bug or dead code, but is intentional

| Item | Why | Detail |
|---|---|---|
| `origin` field on cards looks unused | Reserved for the IE recommender (deferred). Do not remove as dead code. | `architecture/UI-LAYOUT-AND-EXPORT.md` |
| Fuzzy matcher is hand-rolled | Must stay debuggable and dependency-free. Levenshtein and fuzzy libraries were considered and rejected. Do not swap in a library "for simplicity". | `architecture/UI-LAYOUT-AND-EXPORT.md` |
| RSWA uses each linemate's raw, uncapped snap count | A cap understated the summary. Do not reintroduce a cap. | `architecture/CARDS.md` |
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
| Team codes use PFF spellings (`ARZ`, `BLT`, `CLV`, `HST`) | Defined once in `teams_reference.py`; the frontend never hardcodes team data. | `architecture/BACKEND-AND-DEPLOY.md` |
| No Alembic; schema changes need a manual `ALTER TABLE` on Railway | Adding a column reaches local sqlite for free, not production. | `architecture/BACKEND-AND-DEPLOY.md` |
| Rank ties share one rank and percentile (competition ranking) | A tiebreak would misrepresent equal performance. | `architecture/PERCENTILES.md` |
| The chart panel uses `touch-action: manipulation`, not `auto` or `none` | Native pinch-zoom and pan are wanted, but `auto` would also turn on double-tap-zoom with its ~300 ms delay and break tap-to-open-a-card. Plotly's own zoom and pan stay off (`scrollZoom: false`, `dragmode: false`, `doubleClick: false`). | `architecture/UI-LAYOUT-AND-EXPORT.md` |

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
- Removing pinned work without a confirm. A merge is deliberate analytical work and is not cheap to rebuild, unlike Players-filter chips,
  which are dropped silently. A confirm precedes removals; none is shown when nothing is pinned or when the outcome is unaffected or refresh.
- Building a Merge Card by multi-selecting already-open Player Cards and pressing a Merge button, or by dragging cards onto each other.
  The Create popup with its own staged selection is used instead (Cancel discards, Submit builds); membership changes only through the
  card's Edit popup.

## 3. Process conventions

- The working rules (git, order of work, definition of done, PFF data, frontend limits, versioning) live in `INVARIANTS.md`, section "Working rules".
- Work tracking: each topic still being discussed is its own file in `playbook/discussions/`; each decided piece of work, with enough detail to start,
  is its own file in `playbook/next_steps/`. Deciding a topic means moving its file from `discussions/` to `next_steps/` (rename nothing); finishing
  means deleting it from `next_steps/`. Nothing is numbered or ordered, because relative priority changes at any time. Claude Code acts only on the
  `next_steps/` file the owner names.
- Release notes: the title is `🏈LinesShines vX.Y.Z — 2026 Week N`, and the version in the title must match the tag before publishing. Use the exact terms
  `Pinned Players` and `Linemates`, and singular verbs for the product name. Write what the user gets, not the mechanism.
- Cap the time spent on tooling and process work. It supports the product and is not the product.

## 4. Direction

- v2.0.0 is led by NCAAF (college) data; the Insight Explorer (IE) recommender is deferred to a later release.
- `/` stays the NFL page (external links and the PWA `start_url` depend on it). College data lives under `/ncaaf`.
- College and pro charts stay separate.
- Analysis is per player, not per team aggregate. The snap threshold sets the comparison-pool size and screens out garbage-time snaps; it is not a quality filter.
- Keep domain configuration separate from the engine where that is cheap, but do not abstract in advance for sites that do not exist yet.

## 5. Log

- 2026-10-17: `CLAUDE.md` split into short rules plus this `playbook/` folder. Decisions are now logged here.
- 2026-10-17: `.claude/settings.local.json` rebuilt. Git, `railway`, `psql` and reading `.env` are denied; broad allows (`python *`, `node *`, `curl *`, `lsof *`, `cd *`, installs) removed. Ingestion is deliberately not pre-approved because it writes to whatever `DATABASE_URL` points at.
- 2026-10-17: old `NEXT_STEPS.md` renamed `HANDOFF.md`; new `NEXT_STEPS.md` (decided work) and `DISCUSSIONS.md` (open topics) created.
- 2026-10-17: every Markdown file name under `playbook/` is now upper case (extension stays `.md`), and `_archive/` is now `archive/`.
- 2026-10-17: the Commands section moved from `CLAUDE.md` to `playbook/COMMANDS.md`; `CLAUDE.md` keeps a pointer.
- 2026-10-17: the "Rules that always apply" section moved from `CLAUDE.md` to `INVARIANTS.md` ("Working rules"); `CLAUDE.md` now tells Claude Code to read `INVARIANTS.md` first. The duplicate process bullets were removed from this file. The CI formatter command is `black -S .`.
- 2026-10-17: the "must NOT invalidate" list from `BLUEPRINT.md` §4 moved into `architecture/PINNED-INVALIDATION.md`, with a matching row (16) in `INVARIANTS.md`.
- 2026-10-17: design rationale and rejected approaches from `BLUEPRINT.md` §1–§4 carried into this file, `architecture/CARDS.md` and `architecture/UI-LAYOUT-AND-EXPORT.md`.
- 2026-10-17: `BLUEPRINT.md` and the `archive/` folder deleted after its unique rationale was carried into `DECISIONS.md`, `architecture/CARDS.md`, `architecture/PINNED-INVALIDATION.md` and `architecture/UI-LAYOUT-AND-EXPORT.md`.
- 2026-10-17: the single `NEXT_STEPS.md` and `DISCUSSIONS.md` files were replaced by one file per item in `next_steps/` and `discussions/`.
- 2026-10-17: `next_steps/` and `discussions/` items are both written in English, so a file moves between them with no rename and no rewrite.
- 2026-10-17: `HANDOFF.md` retired. Its open items became files in `discussions/` and `next_steps/`, its settled rules were already in `INVARIANTS.md`, `DECISIONS.md` and `architecture/`.
- 2026-10-17: added the private `MEMORANDUM.md` for the owner's standing stances. Wording across `playbook/` was checked against the current layout and corrected where it still described the old one.
- 2026-10-17: `discussions/` and `next_steps/` are visible in the public repo through a `.gitkeep` placeholder each; every other file inside them stays local-only.
- 2026-10-17: `playbook/tests/` added (public): one document per test script, plus `INDEX.md` saying which test file to extend. A new test script ships with its document in the same change.
- 2026-10-18: invariants 1, 2, 3 and 8 got tests (`test_percentiles.py`, `test_filters.py`, `test_app_startup.py`). Invariants 12 and 13 are deliberately untested, with the reasons recorded in `INVARIANTS.md` and `tests/INDEX.md`.
