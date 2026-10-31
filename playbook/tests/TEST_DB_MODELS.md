# test_db_models.py

> **Add tests here when:** changing `database/db_models.py`: table names, columns, constraints or indexes.

- **Kind:** pure Python.
- **Needs:** nothing beyond sqlalchemy. It inspects the models and an in-memory sqlite database.
- **Covers:** the `nfl_` prefix on every table; the `(season, position, player_id)` unique key and duplicate rejection; `player_id` NOT NULL; the pass-rush percent columns existing on the pass-rush table only the pass-rush percent columns existing on the pass-rush table only; the two college Career member tables keyed by `player_id` alone with a NOT NULL `status`; the four hidden snap columns on the college pass-rush table only; the four stat tables (NFL and NCAAF) each carry their league prefix on every constraint and index name and the `(season, position, player_id)` key; the models' columns (from the identity and metric mixins) are exactly the identity columns plus the attributes declared in `database/columns.py`, plus `conference` on the NCAAF tables.
- **Not here:** how files become rows → `TEST_DB_INGESTION.md`.
- **Known gaps:** none recorded.
