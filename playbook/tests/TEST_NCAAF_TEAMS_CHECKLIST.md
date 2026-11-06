# test_ncaaf_teams_checklist.py

> **Add tests here when:** changing how the NCAAF Teams checklist is built or rebuilt (`populateTeamsChecklist()` in `frontend/filters.js`): its per-season schools, or which boxes stay checked across a season or category change.

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it), and `live_server_url` with `seeded_ncaaf_db` from `conftest.py`.
- **Covers:** each season listing only its own schools; "Clear" followed by a season that has a school never seen before leaves every box unchecked; "All Teams" stays all checked in a season with more schools; a school the user unchecked stays unchecked when its season comes back; the reported sequence (a Players pick on top of "All Teams" clears Teams, then moving through seasons ticks nothing); a first-seen school (Ball State, 2024 only) staying off after the user re-ticks one season's visible schools by hand, versus "Select all" carrying it on. The "on/off mode" for not-yet-seen schools is an explicit flag set only by Select all / Clear / the player-pick auto-clear, never inferred from how many boxes happen to be ticked.
- **Not here:** how Teams and Players combine in the chart → `TEST_FILTERS.md`; the NFL checklist, which is built once.
- **Known gaps:** the conference header button (select or clear a whole conference) has no test.
