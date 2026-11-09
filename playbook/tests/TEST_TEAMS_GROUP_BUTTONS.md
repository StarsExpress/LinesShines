# test_teams_group_buttons.py

> **Add tests here when:** changing the NFL Teams checklist's conference or division header buttons (`createGroupToggle()` / `bindGroupToggle()` in `frontend/filters.js`).

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it), and `live_server_url` with `seeded_db` from `conftest.py`.
- **Covers:** a conference header (AFC) selecting that whole conference (16 teams) and none of the other; a second click clearing it; a division header (AFC East) selecting just its four teams; a division toggle inside a ticked conference clearing only those four; a partly ticked group being completed, not cleared; the Teams summary following a group click; a group's box being empty, half-ticked (`aria-checked="mixed"`) or ticked as its teams change, including through the All button; the group boxes not being counted among the 32 team checkboxes.
- **Not here:** the NCAAF conference header → `TEST_NCAAF_TEAMS_CHECKLIST.md`; how Teams combines with Players in the chart → `TEST_FILTERS.md`.
- **Known gaps:** the boxes' drawn look (gold fill, check or dash) is not tested; only the `aria-checked` state is.
