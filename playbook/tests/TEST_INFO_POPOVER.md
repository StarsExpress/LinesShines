# test_info_popover.py

> **Add tests here when:** changing the shared info popover (`info-popover.js`): the content forms it accepts (a string, `{ text }`, `{ bullets }`, `{ links }`, a formula) and how each one renders.

- **Kind:** browser (Playwright). The tests import `/info-popover.js` in the page, build a trigger the way the app does, click it, and read what the popup holds.
- **Needs:** Chromium; the tests skip without it. Its own `page` fixture, which only loads the app so the module is served.
- **Covers:** `bullets` render as one list with one item per point and no paragraph; a plain string is still one paragraph (the form every older caller uses); bullets can sit beside a text paragraph.
- **Not here:** the Teams (i) popover → `TEST_TEAMS_INFO_POPOVER.md`; the Install popup's links → `TEST_INSTALL_LINKS.md`; popup placement → `TEST_POPUP_POSITION.md`.
- **Known gaps:** the `links` and formula forms are tested only through the Install and axis popovers' own tests (or not at all for formulas). The wording of any one popup is not tested here, so the Merge Card's Read | Sort text is unchecked.
