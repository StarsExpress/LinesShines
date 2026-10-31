"""The college Career page's members, rebuilt from the season tables.

Career Stats lists only two kinds of college player, and the two never overlap:

- Joined NFL: the `player_id` also occurs in the NFL table of the same category.
  A college player keeps his PFF id in the NFL files, so the id is the link.
- Potential Draftees: the player has a row in the latest college season and is
  not Joined NFL.

The membership is precomputed into one small table per category, so the website
never runs the join. It holds no stat and no percentile: the Career row of each
member is merged from the season tables at request time, and the browser ranks.

Rebuilt whole (delete, then insert) at the end of every `--league ncaaf` ingestion,
never by the NFL run, so a member added by the NFL tables since the last college
run shows up only at the next college run. Run the NFL ingestion first when both
run on the same day.
"""

from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from config import CareerStatus
from database.db_models import (
    NCAAFPassBlockCareerMember,
    NCAAFPassBlockStat,
    NCAAFPassRushCareerMember,
    NCAAFPassRushStat,
    NFLPassBlockStat,
    NFLPassRushStat,
)


@dataclass(frozen=True)
class _CareerTables:
    """The three tables one category's membership is built from and written to."""

    label: str  # Wording of the printed line.
    college_model: type
    nfl_model: type
    member_model: type


CAREER_TABLES = (
    _CareerTables(
        "pass rush",
        NCAAFPassRushStat,
        NFLPassRushStat,
        NCAAFPassRushCareerMember,
    ),
    _CareerTables(
        "pass block",
        NCAAFPassBlockStat,
        NFLPassBlockStat,
        NCAAFPassBlockCareerMember,
    ),
)


def rebuild_career_members(sess: Session, tables: _CareerTables) -> dict[str, int]:
    """Replace one category's members and return how many there are per status."""
    college_model = tables.college_model

    joined_ids = set(
        sess.scalars(
            select(college_model.player_id)
            .where(college_model.player_id.in_(select(tables.nfl_model.player_id)))
            .distinct()
        )
    )

    # The latest season comes from the table itself, never from the seasons just
    # ingested, so back-filling an old season cannot change who is a Potential Draftee.
    latest_season = sess.scalar(select(func.max(college_model.season)))
    latest_ids = set()

    if latest_season is not None:
        latest_ids = set(
            sess.scalars(
                select(college_model.player_id)
                .where(college_model.season == latest_season)
                .distinct()
            )
        )

    potential_ids = latest_ids - joined_ids

    sess.execute(delete(tables.member_model))
    sess.add_all(
        [
            tables.member_model(
                player_id=player_id, status=CareerStatus.JOINED_NFL.value
            )
            for player_id in sorted(joined_ids)
        ]
    )
    sess.add_all(
        [
            tables.member_model(
                player_id=player_id, status=CareerStatus.POTENTIAL_DRAFTEES.value
            )
            for player_id in sorted(potential_ids)
        ]
    )
    sess.commit()

    return {
        CareerStatus.JOINED_NFL.value: len(joined_ids),
        CareerStatus.POTENTIAL_DRAFTEES.value: len(potential_ids),
    }


def rebuild_all_career_members(sess: Session) -> None:
    """Rebuild the members of every category and print what each now holds."""
    for tables in CAREER_TABLES:
        counts = rebuild_career_members(sess, tables)
        summary = ", ".join(f"{count} {status}" for status, count in counts.items())
        print(f"  career members, {tables.label}: {summary}")

        nfl_row_count = sess.scalar(select(func.count()).select_from(tables.nfl_model))

        if nfl_row_count == 0:
            print(
                f"  Warning: the NFL {tables.label} table is empty, so nobody can be "
                "Joined NFL. Run the NFL ingestion first."
            )
