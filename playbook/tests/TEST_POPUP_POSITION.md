# test_popup_position.py

> **Add tests here when:** changing popup placement (`popup-position.js`): clamping inside the visual viewport, or closing on viewport change.

- **Kind:** browser (Playwright). Imports `/popup-position.js` inside the page and checks the clamp math; also drives the real popup.
- **Needs:** Chromium; the tests skip without it. Its own `page` fixture with a set viewport.
- **Covers:** placement stays inside the visual viewport; an unconstrained popup keeps its width and anchor; the fallback without the visual-viewport API; closing on viewport resize and scroll.
- **Not here:** the Install popup content → `TEST_INSTALL_LINKS.md`.
- **Known gaps:** none recorded.
