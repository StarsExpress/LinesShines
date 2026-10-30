# test_db_models.py

> **Add tests here when:** changing `database/db_models.py`: table names, columns, constraints or indexes.

- **Kind:** pure Python.
- **Needs:** nothing beyond sqlalchemy. It inspects the models and an in-memory sqlite database.
- **Covers:** the `nfl_` prefix on every table; the `(season, position, player_id)` unique key and duplicate rejection; `player_id` NOT NULL; the pass-rush percent columns existing on the pass-rush table only the pass-rush percent columns existing on the pass-rush table only; the models' columns (from the identity and metric mixins) are exactly the identity columns plus the attributes declared in `database/columns.py`.
- **Not here:** how files become rows → `TEST_DB_INGESTION.md`.
- **Known gaps:** none recorded.
