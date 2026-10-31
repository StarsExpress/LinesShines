# test_db_ingestion.py

> **Add tests here when:** changing `database/db_ingestion.py`: file path resolution, which season files are read, which league's tables are filled, the college team table, or how a season/position slice is replaced.

- **Kind:** pure Python.
- **Needs:** nothing beyond pandas and sqlalchemy. It writes tiny synthetic xlsx files in `tmp_path` and uses its own sqlite engine.
- **Covers:** reading from `data/nfl/<category>/<season>.xlsx`; storing `player_id` and the pass-rush percent columns; a missing required column or a null Player Id raising `ValueError`; discovery scanning only the requested league's subfolder; the college categories reading `data/ncaaf/<category>/<season>.xlsx` into the `ncaaf_*` tables with the `Franchise Id` as `team_code` and the `Conference`, never touching the NFL folder or tables, and refusing a workbook that lacks either column; a college pass-rush workbook storing the four snap counts behind Pass Cov Percent (and stopping the run when one is missing); only the college run rebuilding the Career members; the college team table holding every scoped school, rerunnable, with no colour set; the command line requiring `--league`; skipping a missing season file; no fallback to the old flat file names; the data-dir environment override for the repo root; re-ingesting replaces an existing season/position slice (NFL and college). The required columns and the row building come from `database/columns.py` through the shared `ingest_category()`, so these tests exercise that one declaration.
- **Not here:** the HTTP API that serves ingested rows → `TEST_API_ENDPOINTS.md`.
- **Known gaps:** none recorded.
