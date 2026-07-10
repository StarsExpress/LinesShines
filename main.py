"""Game of Trenches API + static frontend, single deployable FastAPI service.

Routes:
  GET  /api/metadata                    → seasons, positions, metric defs, teams
  GET  /api/pass_rush?season=&position= → per-slice records
  GET  /api/pass_block?season=&position= → per-slice records
  GET  /health                          → readiness probe for Railway

Anything else falls through to StaticFiles serving `frontend/`.
"""

from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from config import DEFAULT_THRESHOLDS
from database.db_models import (
    Base,
    DatasetInfo,
    PassBlockStat,
    PassRushStat,
    Team,
    pass_block_row_to_dict,
    pass_rush_row_to_dict,
)


# ---- database wiring -------------------------------------------------------


def _resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./data/lines_shines.db")
    # Railway historically hands out `postgres://…`, but SQLAlchemy 2.x
    # only recognizes the `postgresql://` prefix. Normalize it here so the
    # user doesn't have to remember.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


DATABASE_URL = _resolve_database_url()

_engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    # SQLite locally: relax the same-thread guard so uvicorn's threadpool
    # can serve requests off the main import thread.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


# ---- static metric/position descriptions (schema-level, not row-level) -----

PASS_RUSH_POSITIONS = {"ED": "Edge", "DI": "Defensive Interior"}
PASS_BLOCK_POSITIONS = {"T": "Offensive Tackle", "G": "Guard", "C": "Center"}

PASS_RUSH_METRICS = {
    "Win Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Pass rush win rate",
    },
    "TPS Win Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Win rate on true pass sets",
    },
    "Pressure Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Pressures / pass rush opportunities",
    },
    "TPS Pressure Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Pressure rate on true pass sets",
    },
    "Havoc Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "(Sacks + Hits) / pass rush opportunities",
    },
    "TPS Havoc Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Havoc rate on true pass sets",
    },
}

PASS_BLOCK_METRICS = {
    "Allowed Pressure %": {
        "unit": "%",
        "higher_is_better": False,
        "pff_note": "Pressures allowed / non-spike pass block snaps",
    },
    "TPS Allowed Pressure %": {
        "unit": "%",
        "higher_is_better": False,
        "pff_note": "Allowed pressure rate on true pass sets",
    },
    "Allowed Havoc %": {
        "unit": "%",
        "higher_is_better": False,
        "pff_note": "(Sacks + Hits) allowed / non-spike snaps",
    },
    "TPS Allowed Havoc %": {
        "unit": "%",
        "higher_is_better": False,
        "pff_note": "Allowed havoc rate on true pass sets",
    },
}


# ---- FastAPI app. -----------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if missing. Real schema migrations belong in Alembic
    # once the schema starts evolving; for a static dataset this is enough.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Game of Trenches API",
    description="PFF-derived front-7 & O-line metrics for the LinesShines dashboard.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/metadata")
def metadata() -> dict:
    with SessionLocal() as sess:
        pass_rush_seasons = sorted(
            {season for (season,) in sess.execute(select(PassRushStat.season).distinct())},
            reverse=True,
        )

        pass_block_seasons = sorted(
            {season for (season,) in sess.execute(select(PassBlockStat.season).distinct())},
            reverse=True,
        )

        teams = sess.execute(select(Team)).scalars().all()

        info_rows = sess.execute(select(DatasetInfo)).scalars().all()
        info = {row.key: row.value for row in info_rows}

    return {
        "is_sample_data": info.get("is_sample_data", "true").lower() == "true",
        "sample_data_note": info.get(
            "sample_data_note",
            "示例数据 (SAMPLE DATA) —— 球员姓名为虚构占位符,数值为随机生成,"
            "仅用于演示前端交互。运行 ingest_to_db.py 处理你本地的真实 PFF "
            "导出数据后 sample banner 会自动消失。",
        ),
        "last_ingested_at": info.get("last_ingested_at"),
        "pass_rush": {
            "positions": PASS_RUSH_POSITIONS,
            "metrics": PASS_RUSH_METRICS,
            "threshold_field": "PR Opp",
            "seasons": pass_rush_seasons,
            "default_threshold": DEFAULT_THRESHOLDS["pass_rush"],
        },
        "pass_block": {
            "positions": PASS_BLOCK_POSITIONS,
            "metrics": PASS_BLOCK_METRICS,
            "threshold_field": "Non Spike PB Snaps",
            "seasons": pass_block_seasons,
            "default_threshold": DEFAULT_THRESHOLDS["pass_block"],
        },
        "teams": {
            team.code: {"full_name": team.full_name, "primary_color": team.primary_color}
            for team in teams
        },
    }


@app.get("/api/pass_rush")
def pass_rush(
    season: int = Query(..., ge=1980, le=2100),
    position: str = Query(..., min_length=1, max_length=4),
) -> dict:
    if position not in PASS_RUSH_POSITIONS:
        raise HTTPException(
            400,
            f"invalid position: {position!r} — choose from {list(PASS_RUSH_POSITIONS)}",
        )

    with SessionLocal() as sess:
        rows = (
            sess.execute(
                select(PassRushStat)
                .where(PassRushStat.season == season, PassRushStat.position == position)
                .order_by(PassRushStat.pr_opp.desc())
            )
            .scalars()
            .all()
        )

    return {
        "category": "pass_rush",
        "season": season,
        "position": position,
        "records": [pass_rush_row_to_dict(r) for r in rows],
    }


@app.get("/api/pass_block")
def pass_block(
    season: int = Query(..., ge=1980, le=2100),
    position: str = Query(..., min_length=1, max_length=4),
) -> dict:
    if position not in PASS_BLOCK_POSITIONS:
        raise HTTPException(
            400,
            f"invalid position: {position!r} — choose from {list(PASS_BLOCK_POSITIONS)}",
        )

    with SessionLocal() as sess:
        rows = (
            sess.execute(
                select(PassBlockStat)
                .where(
                    PassBlockStat.season == season, PassBlockStat.position == position
                )
                .order_by(PassBlockStat.non_spike_pb_snaps.desc())
            )
            .scalars()
            .all()
        )

    return {
        "category": "pass_block",
        "season": season,
        "position": position,
        "records": [pass_block_row_to_dict(r) for r in rows],
    }


# ---- Static frontend (mounted LAST so /api/* routes above win). -------------

_here = Path(__file__).parent

# Team logos live in the LinesShines repo's /logos/ folder. When this
# service is deployed as a sibling folder (e.g. LinesShines/web/), the
# logos folder sits one directory up. When deployed standalone, we look
# inside frontend/logos/ instead. First match wins.

_logo_candidates = [
    _here.parent / "logos",  # <repo>/logos when this is <repo>/web
    _here / "logos",  # bundled copy
    _here / "frontend" / "logos",  # bundled inside frontend/
]

for _logos_dir in _logo_candidates:
    if _logos_dir.exists() and _logos_dir.is_dir():
        app.mount("/logos", StaticFiles(directory=str(_logos_dir)), name="logos")
        break

_frontend_dir = _here / "frontend"
if _frontend_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_frontend_dir), html=True),
        name="frontend",
    )
else:

    @app.get("/")
    def _no_frontend() -> JSONResponse:
        return JSONResponse(
            {"message": "frontend/ folder not found; API endpoints under /api/*."},
            status_code=200,
        )
