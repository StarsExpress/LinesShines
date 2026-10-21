# test_install_links.py

> **Add tests here when:** changing the header Install button or its popup (the four links into `PWA.md`, the hints, hiding in standalone display mode).

- **Kind:** browser (Playwright).
- **Needs:** Chromium; the tests skip without it. Its own `page` fixture; one test launches its own browser.
- **Covers:** the button exists beside the GitHub link; popup links and hints; open and close state; the popup stays inside the viewport; hidden in standalone mode; hints stay on one line; option icons and labels.
- **Not here:** popup placement math → `TEST_POPUP_POSITION.md`.
- **Known gaps:** none recorded.
