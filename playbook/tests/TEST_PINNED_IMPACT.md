# test_pinned_impact.py

> **Add tests here when:** changing what happens to Pinned Players or Comparisons when filters change: `evaluatePinnedImpact()`, its outcomes (reset, partial, unaffected) and the confirm-dialog rules.

- **Kind:** browser (Playwright). The `page` fixture loads the app in Chromium and the tests call the pure function.
- **Needs:** Chromium; the tests skip without it.
- **Covers:** the outcome for each kind of filter change, partial removal, and Comparison shrink and dissolve rules.
- **Not here:** popup placement → `TEST_POPUP_POSITION.md`.
- **Known gaps:** the pure function only. Axis controls and display toggles must never reset cards (INVARIANTS 16), but that handler wiring has no test.
