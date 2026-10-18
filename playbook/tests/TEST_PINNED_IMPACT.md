# test_pinned_impact.py

> **Add tests here when:** changing what happens to Pinned Players or Comparisons when filters change (`evaluatePinnedImpact()`, its outcomes and the confirm-dialog rules), or the eligibility rule and removal toast text shared with the Players filter (`partitionByEligibility()`, `removedPlayersNotice()`).

- **Kind:** browser (Playwright). The `page` fixture loads the app in Chromium and the tests call the pure function.
- **Needs:** Chromium; the tests skip without it.
- **Covers:** the outcome for each kind of filter change, partial removal, and Comparison shrink and dissolve rules; the shared eligibility rule (inclusive threshold, exact position, missing player or value, order kept, empty pool) and that Pinned invalidation agrees with it; the removal toast text (none, one name, up to three, "and N more"); the colour contrast of the warning notice, read from the real `style.css` (at least 4.5:1).
- **Not here:** popup placement → `TEST_POPUP_POSITION.md`.
- **Known gaps:** the pure functions only. Axis controls and display toggles must never reset cards (INVARIANTS 16), and the Players filter must re-check selections on commit rather than while dragging (INVARIANTS 17), and the toast switching to its yellow warning variant, but that wiring has no test.
