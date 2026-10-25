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
- 2026-10-24: `next_steps/` files are kept current: a decision that replaces earlier text rewrites it in place instead of layering revision notes, and with more than one Claude session running, each reads `next_steps/` and re-reads a file before editing it (`INVARIANTS.md`, "Working rules").
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
- 2026-10-18: the Players filter keeps selected players who are still eligible, using the same eligibility function as Pinned Players (`partitionByEligibility()`). It re-checks them only on commit, and a toast names up to three removed players.
- 2026-10-18: notices about removals use a yellow warning variant of the toast (`--flag-gold-bright` with dark text and a warning sign); the pinned-players refresh notice stays dark green.
- 2026-10-18: the Comparison Card gets a Read | Sort switch (default Read; sorting only in Sort; Read follows the current sort order; PNG export always uses the Read layout). Moved from `discussions/` to `next_steps/`.
- 2026-10-18: Comparison Card Read | Sort modes implemented: one pure model, two layouts, Read follows the current sort, PNG export always Read. In Read the left freeze was dropped because the table always fits the card, and only the head block is pinned.
- 2026-10-18: after a first look at the Read layout: the Read | Sort (i) uses the same glyph-only trigger style as the Teams, Players and axis popovers; Read columns made compact (104px labels, 88px per player) and the desktop card shrinks to fit its table instead of staying 640px.
- 2026-10-18: the Read | Sort popup is a two-point bulleted list (new `bullets` form of the shared info popover); Read player columns widened 1.3x to 114px (88 x 1.3), so a five-player Read card is about 714px and its desktop cap is 720px.
- 2026-10-18: CI now fails when a test script has no document in `playbook/tests/`, when a document has no script, or when a document's third line lacks "Add tests here when:" (`tests/test_playbook_docs.py`). The documents therefore must be committed together with the scripts. `INDEX.md` listing is not enforced.
- 2026-10-18: `tests/test_playbook_docs.py` also fails when `playbook/tests/INDEX.md` does not link a document, so a new document must be added to the routing table too.
- 2026-10-18: `tests/test_playbook_docs.py` also fails when `playbook/tests/INDEX.md` links to a file that does not exist.
- 2026-10-21: static files are answered with `Cache-Control: no-cache` (root mount, `/` and `/sw.js`; not `/logos`; `NoCacheStaticFiles` in `main.py`), and the Service Worker serves the app shell network-first with a 3 second timeout (`NETWORK_TIMEOUT_MS`), falling back to the cache when slow or offline. `/api/` and `/health` still bypass the cache. Rejected: `?v=` on module URLs or an import map (URLs stay clean), an "update available" notice (the app should always run the latest version), and reproducing the bug first (preventive fix). Implemented as a PATCH; local CI and manual checks passed. Moved from `discussions/` to `next_steps/`, then deleted when done.
- 2026-10-21: the three card corner buttons became solid discs of different colours: Save black with a 2px `#f0ede4` outline and a light icon (like Save Plot and Create), Fold sky blue `#5ec8f2`, Close bright coral `#ff6b5e`, both with a dark icon. Size 24 px (22 px x 1.1, rounded), kept small so long player names are not crowded; positions unchanged, no larger touch area for now. Same change for the scouting, Comparison and Linemates cards. Contrast is checked from `style.css` by `tests/test_card_buttons.py`. Raised after feedback from a fellow student that the buttons were hard to press and not prominent. Implemented; local CI and a visual check passed. Moved from `discussions/` to `next_steps/`, then deleted when done.
- 2026-10-21: the Linemate Card's roster gets a "Card" button column between Player and Position; each button opens that teammate's own Player Card, or brings it forward if already open (same as a Pinned Players entry), for every position on the line and for the anchor's own row. Chosen over making names clickable because it keeps names plain and carries over to the Read layout planned for PR #13. The Comparison Card's Linemates button and the new buttons share one solid gold (`#d4af5a`, 28 px) as "opens a card". The new column is left out of the Linemate Card PNG export; the Comparison Card's Linemates button stays in its export. Implemented; local CI and a visual check passed. Moved from `discussions/` to `next_steps/`, then deleted when done.
- 2026-10-21: a Player Card opened from a Linemate Card's Card button for a teammate at another position on the line now survives a threshold or season change while he still qualifies (`resolveCarriedRecord()`; the old check required the plot's position, which was fine while every card sat at the plot's position). A Player Card also ranks its player among his own position (`positionPool`) instead of the plot's pool. This is a change made for the new entry point, not a fix of shipped behaviour: every percentile shown before (Player Cards at the plot's position, and the Linemate Card table, which always used each teammate's own position pool) was correct.
- 2026-10-22: the Pinned Players panel starts open for a first-time visitor so the feature is seen (it used to start folded, showing only a counter); the last open or folded choice is then remembered in the browser, and unavailable storage means open. The button reads Hide while open and Manage while folded. Still desktop and tablet only. Local CI and a visual check passed. Moved from `discussions/` to `next_steps/`, then deleted when done.
- 2026-10-24: in the Player, Linemate and Comparison Card PNG exports the white frame is now the image's outermost edge and encloses the card, the metric notes and the credit line (it used to be the card panel's own border, with notes and credit below it, outside). The frame is square (no rounded corners) and the same 2px `#f0ede4`. A narrow card stays centred with extra dark space on both sides inside the frame; the credit line is not shrunk or split. The Scatter Plot (Save Plot) export is unchanged and has no frame. Implemented via a `frame` option of `compositeFooterCanvas()`. Local CI and a visual check passed. Moved from `discussions/` to `next_steps/`, then deleted when done.
- 2026-10-24: in the Player, Linemate and Comparison Card PNG exports the credit line sits on a full-width gold band (`#d3a73d`, the `--flag-gold` of the card tab) in dark text (`#0f2119`), inside the white frame. Dark text because white on that gold is only about 2:1 contrast. The metric notes keep their colour and position, and no dashed separator lines were added. The Scatter Plot export is unchanged (grey credit text, no band, no frame). Via a `creditBand` option of `compositeFooterCanvas()`. Local CI and a visual check passed; the gold was kept after weighing it against the yellow percentile tags (different tone, shape and place). Written straight into `next_steps/` as `CARD-NOTES-CREDITS-STYLES.md`, then deleted when done.
- 2026-10-24: when "Include metric notes" is on, the Player, Linemate and Comparison Card PNG exports draw a faint dashed line (1px, 4px dashes and gaps, chalk at 0.45 opacity, inset 16px from both sides) between the card's metrics and the Notes. No line between the Notes and the gold credit band (the band's colour already separates them), and none on the Scatter Plot export. Via a `notesDivider` option of `compositeFooterCanvas()`, added to `CARD-NOTES-CREDITS-STYLES.md`. Local CI and a visual check passed.
- 2026-10-24: the Scatter Plot (Save Plot) PNG export's credit line also sits on the gold band with dark text, like the cards. It still has no white frame and no notes divider. Reverses the earlier "Scatter Plot unchanged" part of the card-export entries above.
- 2026-10-24: in the Comparison Card's Read mode the rows are grouped under gold heading rows, like the Player Card: Metadata (Games, the threshold field), Required Metrics, and Bonus Metrics (metrics flagged `bonus`, DL only; no heading when a category has none). Sort mode has no headings. The PNG export (always Read) shows them too. Detail: `architecture/CARDS.md`.
- 2026-10-24: the Player Card's stats are grouped under gold small headings: Metadata (Games, the threshold field), Required Metrics, and Bonus Metrics (metrics flagged `bonus: true`: Pass Cov Percent and TPS Pass Cov Percent, DL only; the OL card has no Bonus heading). The Linemates button and the note bullets stay above them. `PASS_RUSH_METRICS` lists the bonus metrics last, so the axis pickers and the Comparison and Linemate cards show required-then-bonus too. Detail: `architecture/CARDS.md`.
- 2026-10-24: Pass Cov Percent and TPS Pass Cov Percent (100 minus the source Pass Rush Percent, computed at ingestion) are left out of the Linemate Card's Line Summary (`line_summary: false`), because a line mixes ED and DI whose coverage shares differ too much for one Min/Median/Max/RSWA. The roster table still shows each player's own percentile among his position.
- 2026-10-24: the Linemate Card's roster table sits under a gold "Individual" heading and the Line Summary under its own, separated by one divider each, matching the Player Card.
- 2026-10-24: the Linemate Card's Individual table has the Comparison Card's Read | Sort switch, right-aligned on its heading row, default Read; only that table switches (the Line Summary does not). Read puts players in columns (76px each, label column 104px) under a pinned name/position/Card head, with the rows grouped Metadata / Required Metrics / Bonus Metrics; "See more" is hidden in Read, the card fits its table (420 to 760px), and the PNG export is always Read without the Card row. The Comparison and Linemate cards share one table model, `player-table-model.js`, which takes the identity columns from the caller. Detail: `architecture/CARDS.md`.
