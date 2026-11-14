# test_external_requests.py

> **Add tests here when:** changing `_keep_requests_local()` in `tests/conftest.py`, or adding another external host to `index.html` that a test must not wait for.

- **Kind:** browser (Playwright).
- **Needs:** Chromium (skips without it), `live_server_url`.
- **Covers:** the fonts (`fonts.googleapis.com`) and icons (`cdnjs.cloudflare.com`) requests of the page fail at once with an abort, for a page made by `chromium_browser.new_page()` and for one in a context made by hand (`new_context()`), so `page.goto()` never waits for a CDN. Without it a silent CDN failed tests in their setup with a 30 s `goto` timeout.
- **Not here:** that the page still works without its fonts and icons -> every other browser test runs that way.
- **Known gaps:** the real cause on the CI runner (which CDN stalled) was not seen; a stalled request blocking `load` was reproduced by hand, the runner's network was not.
