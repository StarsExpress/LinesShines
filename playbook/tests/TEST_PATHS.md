# test_paths.py

> **Add tests here when:** changing the folder layout of `data/` or `frontend/`, or the paths `config.py` exposes.

- **Kind:** pure Python.
- **Needs:** nothing. Raw data files are git-ignored, so a CI checkout lacks the data folders; these tests assert only what is true with or without real season data.
- **Covers:** `NFL_DATA_PATH` is `data/nfl` and `NCAAF_DATA_PATH` is `data/ncaaf`; the data folder path matches the repo layout; no legacy flat data files; the NFL logo directory `team_logos/nfl/` exists and holds PNGs, and no PNG sits loose in `team_logos/`.
- **Not here:** ingestion behaviour → `TEST_DB_INGESTION.md`.
- **Known gaps:** none recorded.
