# test_merge_table.py

> **Add tests here when:** changing the Comparison (Merge) Card's table: its Read and Sort layouts, the model they come from (`player-table-model.js`), or how the table follows the card's sort order.

- **Kind:** browser (Playwright). The model tests import `/player-table-model.js` and pass plain strings as players. The renderer tests call the real `renderMergeCardBody()` on a detached card built in the page, using the app's own modules and metadata, and read the resulting table as text.
- **Needs:** Chromium; the tests skip without it. The page must have finished loading so the real metadata exists, which the fixture waits for. Its own `page` fixture.
- **Covers:** the Sort layout (one head row of columns, one row per player); the Read layout (head block of name, team and Linemates, then Games, the threshold field and the metrics); Read is the exact transposition of Sort; both keep the order they are given and follow every sort the same way; the default mode is Read; only Sort has sortable headers, and Linemates never does; Read and Sort show the same percentiles; rendering never changes the sort state.
- **Sections in Read:** `readLayout()` groups the rows into Metadata, Required Metrics and Bonus Metrics (the last left out when no metric is flagged `bonus`); the rendered Read table shows one heading row per section spanning the label and player columns, with Pass Cov Percent and TPS Pass Cov Percent under Bonus; Sort has no headings.
- **Identity columns:** the model takes them from the caller (the Linemate Card passes name, position, Card); one test checks the Read head and sections with such columns. The Linemate Card's own Read tests are in `TEST_LINEMATE_CARD.md`.
- **Not here:** the cell contents and percentile rules themselves → `TEST_PERCENTILES.md`; popups → `TEST_POPUP_POSITION.md`.
- **Known gaps:** the wiring is not tested: the Read | Sort switch buttons, the (i) popover, the scroll hint following the mode, the frozen head block, and the PNG export being forced to Read (including re-fitting the clone). Check those by hand (INVARIANTS 18).
