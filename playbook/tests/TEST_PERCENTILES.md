# test_percentiles.py

> **Add tests here when:** changing how percentiles and ranks are computed (`rankAndPercentile()`) or how a percentile pool is built (`positionPool()`), both in `data.js`.

- **Kind:** browser (Playwright). Imports `/data.js` inside the page and loads synthetic rows through the module's own setters (`setCurrentSlice`, `setAppliedFilters`). No chart interaction.
- **Needs:** Chromium; the tests skip without it. The page must have finished loading so the real metadata exists, which the fixture waits for. Its own `page` fixture.
- **Covers:** a pool is the exact position above the threshold; the percentile does not change with the position selected on the chart; the threshold is a hard gate on membership; why pools are partitioned (50th among EDs, 25th once DIs are mixed in); tied values share one rank and percentile (competition ranking); lower-is-better; pool order does not matter; missing values are left out; no result without a value or without two players.
- **Not here:** Teams and Players highlighting → `TEST_FILTERS.md`. The Merge and Linemate card rows that call these functions have no test file yet.
- **Known gaps:** "same season" is whatever slice `currentRecords` holds and is not tested separately (INVARIANTS 1). Only the shared functions are tested, not their call sites in the card modules.
