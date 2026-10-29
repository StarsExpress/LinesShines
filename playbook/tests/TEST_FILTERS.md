# test_filters.py

> **Add tests here when:** changing which players the chart plots or highlights from the Teams and Players selections, or the threshold gate (`render()` in `render.js`).

- **Kind:** browser (Playwright). The union rule lives inside `render()`, so the tests call the real `render()` on synthetic rows and read the trace it hands to `Plotly.react` (wrapped for the call, then restored). A label counts as dimmed when its text colour carries `DIM_OPACITY.label` from `config.js`.
- **Needs:** Chromium; the tests skip without it. The page must have finished loading so the real metadata exists, which the fixture waits for. Its own `page` fixture.
- **Covers:** Teams alone; Players alone; Teams and Players as a union (an intersection would highlight nobody); nothing selected dims everyone; a selection never changes who is plotted; the threshold stays a hard gate even for a selected team or player. A Season switch resets the threshold to the new season's default in both directions between an ongoing and a finalized season (`seasonSwitchChangesThresholdDefault()`), and not between two finalized seasons; the Season `"change"` handler calls that rule (checked from source).
- **Not here:** Pinned Players invalidation → `TEST_PINNED_IMPACT.md`. The Players search pool and fuzzy matching have no test file yet.
- **Known gaps:** the tests depend on how `render()` builds its trace, because the rule is not a separate function. If it is ever extracted, test it directly. Dimming is read from the text colour only, not from marker or logo opacity. The Players search pool staying live (INVARIANTS 4) is not covered. The Season switch is tested as a rule plus a source check; no test drives the real dropdown and reads the threshold box afterwards.
