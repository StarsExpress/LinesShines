# test_paths.py

> **Add tests here when:** changing the folder layout of `data/` or `frontend/`, or the paths `config.py` exposes.

- **Kind:** pure Python.
- **Needs:** nothing. Raw data files are git-ignored, so a CI checkout lacks the data folders; these tests assert only what is true with or without real season data.
- **Covers:** the data folder path matches the repo layout; no legacy flat data files; the team logo directory exists.
- **Not here:** ingestion behaviour → `TEST_DB_INGESTION.md`.
- **Known gaps:** none recorded.
