# test_career_merge.py

> **Add tests here when:** changing `database/career_merge.py` (how a member's seasons are merged into one Career row) or the `/api/ncaaf/career/*` routes (metadata, the two default thresholds, the position filter, errors).

- **Kind:** pure Python for the merge (an in-memory sqlite database with synthetic rows) and API (HTTP client) for the routes.
- **Needs:** nothing beyond sqlalchemy for the merge; `client` from `conftest.py` and the file's own `seeded_career_db` for the routes. No browser.
- **Covers:** counts (games, PR Opp, TPS PR Opp) summed over seasons; a rate weighted by its own denominator and the TPS rates by the TPS one; Pass Cov Percent rebuilt from the pass-rush and pass-play snap counts and not from PR Opp; the hidden snap columns never reaching a record; position, team, conference and status taken from the last college season; the row with more opportunities standing for a player who has two positions in that season; the position filter reading the last position; a non-member never listed; a zero denominator giving `None`; a season with no opportunities and an infinite stored rate being skipped instead of turning the Career rate into NaN (Postgres); the order (opportunities, then player id); the offensive line weighting by Non Spike PB Snaps; the conference lookup of each member's last school; the Career metadata (statuses, positions, one default threshold per status, teams, conferences); the Joined NFL default being stricter than the Potential Draftee one; every member sent with no server-side threshold; an unknown position answering 400.
- **Not here:** who is a member -> `TEST_CAREER_MEMBERS.md`; the Season routes -> `TEST_API_ENDPOINTS.md`; the Career page and its sliders (not built yet).
- **Known gaps:** none recorded.
