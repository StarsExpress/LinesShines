"""Seed the database with fictional pass-rush and pass-block records.

Purpose: give the deployed dashboard something to render before the real
PFF-derived xlsx files have been ingested via `ingest_to_db.py`. Player
names are randomly composed, stats are drawn from a plausible distribution
per position — the shapes match the real schema exactly so the frontend
behaves identically once real data replaces this.

Idempotent — running twice wipes and reseeds. Flags the DB as
`is_sample_data=true`, which is what makes the yellow banner render in the
UI. Ingesting real data via `ingest_to_db.py` flips that flag off.

    python seed_sample_data.py
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import delete

from database.db_models import (
    Base,
    DatasetInfo,
    PassBlockStat,
    PassRushStat,
    Team,
)
from main import engine, SessionLocal
from teams_reference import TEAMS

SEASONS = [2023, 2024, 2025]

FIRST_INITIALS = list("ABCDEFGHJKLMNPRST")
LAST_NAMES = [
    "Walker", "Brooks", "Carter", "Ellis", "Fenwick", "Gray", "Holt",
    "Ibarra", "Jensen", "Kowalski", "Lawson", "Mercer", "Nolan", "Ortega",
    "Pruitt", "Reyes", "Sanders", "Tate", "Underwood", "Voss", "Weaver",
    "Yarbrough", "Zimmer", "Adkins", "Bishop", "Cross",
]

FRONT_7 = ("DI", "ED", "LB")
OL = ("T", "G", "C")

random.seed(7)


def _fake_name(used: set[str]) -> str:
    while True:
        n = f"{random.choice(FIRST_INITIALS)}. {random.choice(LAST_NAMES)}"
        if n not in used:
            used.add(n)
            return n


def _upsert_teams(sess) -> None:
    existing = {t.code: t for t in sess.query(Team).all()}
    for code, (full_name, color) in TEAMS.items():
        if code in existing:
            existing[code].full_name = full_name
            existing[code].primary_color = color
        else:
            sess.add(Team(code=code, full_name=full_name, primary_color=color))
    sess.commit()


def _seed_pass_rush(sess) -> int:
    sess.execute(delete(PassRushStat))
    n = 0
    for season in SEASONS:
        for position in FRONT_7:
            used = set()
            for _ in range(random.randint(38, 46)):
                base_skill = random.gauss(0, 1)
                pr_opp = max(60, int(random.gauss(310, 90)))
                tps_pr_opp = max(20, int(pr_opp * random.uniform(0.35, 0.55)))
                win_rate = max(3.0, round(9 + base_skill * 4 + random.gauss(0, 1.5), 1))
                tps_win_rate = max(3.0, round(win_rate + random.gauss(1.5, 2.0), 1))
                pressure_rate = max(4.0, round(win_rate * 1.6 + random.gauss(0, 2.5), 1))
                tps_pressure_rate = max(4.0, round(pressure_rate + random.gauss(2.0, 2.5), 1))
                havoc_rate = max(1.0, round(pressure_rate * 0.42 + random.gauss(0, 1.2), 1))
                tps_havoc_rate = max(1.0, round(havoc_rate + random.gauss(1.2, 1.5), 1))

                sess.add(PassRushStat(
                    season=season,
                    position=position,
                    team_code=random.choice(list(TEAMS)),
                    player=_fake_name(used),
                    abbr_name="",  # filled below to keep names identical
                    games=random.randint(8, 17),
                    pr_opp=pr_opp,
                    tps_pr_opp=tps_pr_opp,
                    win_rate=win_rate,
                    tps_win_rate=tps_win_rate,
                    pressure_rate=pressure_rate,
                    tps_pressure_rate=tps_pressure_rate,
                    havoc_rate=havoc_rate,
                    tps_havoc_rate=tps_havoc_rate,
                ))
                n += 1
    sess.commit()

    # abbr_name mirrors `player` for sample data — the real ingestion path
    # runs PFF's names through utils/renamers.py:shorten_first_name.
    for row in sess.query(PassRushStat).all():
        row.abbr_name = row.player
    sess.commit()
    return n


def _seed_pass_block(sess) -> int:
    sess.execute(delete(PassBlockStat))
    n = 0
    for season in SEASONS:
        for position in OL:
            used = set()
            for _ in range(random.randint(34, 42)):
                base_skill = random.gauss(0, 1)
                snaps = max(100, int(random.gauss(430, 110)))
                tps_snaps = max(30, int(snaps * random.uniform(0.30, 0.50)))
                allowed_pressure = max(1.5, round(6.5 - base_skill * 2.0 + random.gauss(0, 1.3), 1))
                tps_allowed_pressure = max(1.5, round(allowed_pressure + random.gauss(1.2, 1.6), 1))
                allowed_havoc = max(0.5, round(allowed_pressure * 0.4 + random.gauss(0, 0.8), 1))
                tps_allowed_havoc = max(0.5, round(allowed_havoc + random.gauss(0.8, 1.0), 1))

                sess.add(PassBlockStat(
                    season=season,
                    position=position,
                    team_code=random.choice(list(TEAMS)),
                    player=_fake_name(used),
                    abbr_name="",
                    games=random.randint(8, 17),
                    non_spike_pb_snaps=snaps,
                    tps_non_spike_pb_snaps=tps_snaps,
                    allowed_pressure_pct=allowed_pressure,
                    tps_allowed_pressure_pct=tps_allowed_pressure,
                    allowed_havoc_pct=allowed_havoc,
                    tps_allowed_havoc_pct=tps_allowed_havoc,
                ))
                n += 1
    sess.commit()

    for row in sess.query(PassBlockStat).all():
        row.abbr_name = row.player
    sess.commit()
    return n


def _mark_sample(sess) -> None:
    updates = {
        "is_sample_data": "true",
        "sample_data_note": (
            "示例数据 (SAMPLE DATA) —— 球员姓名为虚构占位符,数值为随机生成,"
            "仅用于演示前端交互。运行 ingest_to_db.py 处理你本地的真实 PFF "
            "导出数据后 sample banner 会自动消失。"
        ),
        "last_ingested_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    for key, value in updates.items():
        existing = sess.get(DatasetInfo, key)
        if existing:
            existing.value = value
        else:
            sess.add(DatasetInfo(key=key, value=value))
    sess.commit()


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as sess:
        _upsert_teams(sess)
        pr = _seed_pass_rush(sess)
        pb = _seed_pass_block(sess)
        _mark_sample(sess)
    print(f"seeded {pr} pass-rush + {pb} pass-block sample rows.")


if __name__ == "__main__":
    main()
