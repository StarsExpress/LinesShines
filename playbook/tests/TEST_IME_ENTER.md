# test_ime_enter.py

> **Add tests here when:** changing `isImeComposing()` in `frontend/search.js`, or the `keydown` handler of a name-search input in `frontend/main.js` (Players filter, Single Cards add, Create comparison, Edit comparison), or adding another name-search input.

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it); the `page` fixture and helpers of `test_browser_smoke.py` (synthetic players, imported, not copied).
- **Covers:** in each of the four name-search inputs, an Enter with `isComposing` true, and one with `keyCode` 229 (Safari, after `compositionend`), picks nobody and is not cancelled, while the same Enter outside a composition still picks the top suggestion; an Escape during a composition leaves the Players panel and its suggestions open. The key events are dispatched by hand: a headless browser has no input method.
- **Not here:** what the picks do to the filters and cards -> `TEST_BROWSER_SMOKE.md`.
- **Known gaps:** a real input method (macOS Pinyin, iOS keyboard) can only be checked by hand; the tests prove the page's reaction to the events, not that a given browser sends them as assumed.
