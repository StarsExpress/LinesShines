# test_api_endpoints.py

> **Add tests here when:** adding or changing a JSON endpoint under `/api/nfl/` or `/api/ncaaf/` (query parameters, response shape, error codes).

- **Kind:** API (HTTP client).
- **Needs:** `client` and `seeded_db` (NFL) or `seeded_ncaaf_db` (college) from `conftest.py`. No browser.
- **Covers:** `/api/nfl/metadata` shape; the old unprefixed routes answering 404; the NFL metadata carrying no conference data; the college metadata (seasons, schools keyed by franchise id, conference order, each season's conference of every school), the college default thresholds 230 and 360, college records carrying `conference` and the franchise id as `team`, the college routes mirroring the NFL errors, and the two leagues never mixing; pass-rush and pass-block returning the seeded rows; errors for an unknown position and for missing query parameters; a request without a position returning every position.
- **Not here:** how the app is assembled → `TEST_APP_STARTUP.md`; Service Worker behaviour → `TEST_SW_CACHE_BYPASS.md`.
- **Known gaps:** `test_metadata_shape` checks the shape only, not every metric's `higher_is_better` value (INVARIANTS 6). The neutral Pass Cov Percent metrics (flags, listed after the required metrics) `player_id` in rows, and the Pass Cov Percent popup text (`pff_note`) with no metric carrying a `card_note` are covered.
