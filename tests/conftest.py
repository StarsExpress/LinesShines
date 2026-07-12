"""Shared pytest fixtures.

Points DATABASE_URL at an ephemeral sqlite file *before* anything imports
`main`, since main.py resolves its engine at import time — setting the env
var inside a fixture would be too late for the first `from main import ...`.
"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path

_TEST_DB_DIR = tempfile.mkdtemp(prefix="lines_shines_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TEST_DB_DIR) / 'test.db'}"

import pytest
from fastapi.testclient import TestClient
from database.db_models import Base, PassBlockStat, PassRushStat, Team
from main import app, engine, SessionLocal

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def seeded_db():
    """Wipe and load a small, deterministic dataset for API-level tests."""
    with SessionLocal() as sess:
        sess.query(PassRushStat).delete()
        sess.query(PassBlockStat).delete()
        sess.query(Team).delete()
        sess.commit()

        sess.add(Team(code="BUF", full_name="Buffalo Bills", primary_color="#00338D"))
        sess.add(Team(code="MIA", full_name="Miami Dolphins", primary_color="#008E97"))

        sess.add(
            PassRushStat(
                season=2025,
                position="ED",
                team_code="BUF",
                player="T. Test",
                abbr_name="T. Test",
                games=17,
                pr_opp=300,
                tps_pr_opp=120,
                win_rate=15.0,
                tps_win_rate=18.0,
                pressure_rate=20.0,
                tps_pressure_rate=25.0,
                havoc_rate=8.0,
                tps_havoc_rate=10.0,
            )
        )

        sess.add(
            PassBlockStat(
                season=2025,
                position="T",
                team_code="MIA",
                player="O. Line",
                abbr_name="O. Line",
                games=17,
                non_spike_pb_snaps=500,
                tps_non_spike_pb_snaps=200,
                allowed_pressure_pct=5.0,
                tps_allowed_pressure_pct=6.0,
                allowed_havoc_pct=2.0,
                tps_allowed_havoc_pct=3.0,
            )
        )

        sess.commit()

    yield
