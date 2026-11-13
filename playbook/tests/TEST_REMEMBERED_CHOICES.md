# test_remembered_choices.py

> **Add tests here when:** changing `frontend/preferences.js`, `rememberAppliedAxes()` / `applyRememberedAxes()` in `frontend/filters.js` or the position-change wiring in `frontend/main.js`.

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it), `live_server_url`, and (for the Career test) the `seeded_career_page_db` fixture of `test_ncaaf_career_page.py`. Each page is a fresh browser context, so nothing is remembered at the start.
- **Covers:** an applied X / Y pair coming back after a reload; a pair that was not applied not being remembered; each position (ED, DI) and each category keeping its own pair; the default pair not being stored, so applying it again drops the entry and a later change of the default still reaches everyone; the three switches being remembered, and drawn in their remembered state before any module loads (`main.js` is blocked, so only the inline script in `index.html` can have restored them; on the NFL and the Career key); a remembered metric that no longer exists falling back to the default; unreadable stored text (bad JSON, wrong version, wrong shape) being ignored; the page working where storage throws; the View key naming the page; the Career page keeping its own entry and leaving the NFL one alone.
- **Not here:** the default pair of each category -> `TEST_FILTERS.md`; that an axis change never touches a pinned card -> `TEST_BROWSER_SMOKE.md`.
- **Known gaps:** the NCAAF Season page's own key is not exercised (it shares the code of the NFL page); the iOS Safari vs Home Screen storage split can only be checked by hand.
