"""Database engine and session factory, shared by the API and the ingestion.

Split out of `main.py` so `database/db_ingestion.py` can reach the engine
without importing `main` (which would pull in the whole FastAPI app). Both the
SQLite (local dev) and PostgreSQL (Railway) branches behave exactly as before.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./data/lines_shines.db")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    # Force SQLAlchemy to use psycopg3, which is installed as `psycopg[binary]`.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    return url


DATABASE_URL = _resolve_database_url()

_engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    # SQLite locally: relax the same-thread guard so uvicorn's threadpool
    # can serve requests off the main import thread.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
