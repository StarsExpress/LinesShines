# test_teams_ncaaf.py

> **Add tests here when:** changing the NCAAF conference table in `teams/ncaaf.py` (a school's stints, the scoped conferences, the out-of-scope list) or `conference_of()`.

- **Kind:** pure Python.
- **Needs:** nothing. The tables are plain Python, so no PFF data and no database are involved.
- **Covers:** every stint names a scoped conference and starts in 2014 or later; one school's stints are in order and never overlap; no school is both scoped and out of scope; a school that changes conference changes label in the move season (Texas, Oregon, California); a scoped school outside its stints is out of scope for that season (BYU 2022, Texas State 2025); UMass has two separate MAC stints; Northern Illinois leaves the MAC after 2025; only Oregon State and Washington State are in the Pac-12 in 2024; Notre Dame is the only independent; the size of each conference in the seasons where it changed; a never-scoped school returns `None`; an unknown `franchise_id` raises `KeyError`; `scoped_franchise_ids()` returns every school with a scoped season.
- **Not here:** that every team in a real PFF export resolves → checked by hand against the CSVs when a season is added (raw data never enters the repo).
- **Known gaps:** the table is written from ESPN and Wikipedia; Sacramento State's 2026 MAC membership has one source so far.
