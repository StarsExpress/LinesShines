# test_db_ingestion.py

> **Add tests here when:** changing `database/db_ingestion.py`: file path resolution, which season files are read, or how a season/position slice is replaced.

- **Kind:** pure Python.
- **Needs:** nothing beyond pandas and sqlalchemy. It writes tiny synthetic xlsx files in `tmp_path` and uses its own sqlite engine.
- **Covers:** reading from `data/nfl/<category>/<season>.xlsx`; storing `player_id` and the pass-rush percent columns; a missing required column or a null Player Id raising `ValueError`; discovery scanning only the `nfl` subfolder; skipping a missing season file; no fallback to the old flat file names; the data-dir environment override for the repo root; re-ingesting replaces an existing season/position slice.
- **Not here:** the HTTP API that serves ingested rows → `TEST_API_ENDPOINTS.md`.
- **Known gaps:** none recorded.
