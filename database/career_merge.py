"""One Career row per member, merged from the college season tables.

Career Stats pools a player's seasons into a single row, so there is no season to
rank in and no percentile stored: the browser ranks the merged rows. The merge is
a `GROUP BY player_id` over every season the player has in the category's table.

- Games and the opportunity or snap counts are summed.
- A rate is a weighted average over its own denominator (PR Opp for the front 7,
  Non Spike PB Snaps for the OL; the TPS versions use the TPS counts). The tables
  hold rates, not counts, so `SUM(rate * weight) / SUM(weight)` is the rate of the
  pooled counts, within the rounding of the stored rates.
- Pass Cov Percent cannot be weighted by PR Opp, because PR Opp is not Pass Rush
  Snaps. It is rebuilt from the four snap counts the college pass-rush table keeps:
  100 - SUM(pass rush snaps) / SUM(pass play snaps) x 100.

The name, position, team and conference are those of the player's last college season.
The columns come from `database/columns.py`, so a metric added there is merged too.
"""

from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session
from config import ROUNDING_DECIMALS
from database.columns import (
    PASS_BLOCK_DATA_COLUMNS,
    PASS_RUSH_DATA_COLUMNS,
    DataColumn,
)
from database.db_models import (
    NCAAFPassBlockCareerMember,
    NCAAFPassBlockStat,
    NCAAFPassRushCareerMember,
    NCAAFPassRushStat,
)


@dataclass(frozen=True)
class CareerSpec:
    """What one category's Career merge reads, and how each column is combined."""

    college_model: type
    member_model: type
    data_columns: tuple[DataColumn, ...]
    weight_attr: str  # The denominator of the rates.
    tps_weight_attr: str  # The denominator of the TPS rates.
    sum_attrs: tuple[str, ...]  # Columns that are plainly summed.
    order_attr: str  # The count a record is ordered by, descending.
    # (column attr, rush snaps attr, pass play snaps attr) of each Pass Cov Percent column.
    complement_snaps: tuple[tuple[str, str, str], ...] = ()


PASS_RUSH_CAREER = CareerSpec(
    college_model=NCAAFPassRushStat,
    member_model=NCAAFPassRushCareerMember,
    data_columns=PASS_RUSH_DATA_COLUMNS,
    weight_attr="pr_opp",
    tps_weight_attr="tps_pr_opp",
    sum_attrs=("games", "pr_opp", "tps_pr_opp"),
    order_attr="pr_opp",
    complement_snaps=(
        ("pass_cov_percent", "pass_rush_snaps", "pass_play_snaps"),
        ("tps_pass_cov_percent", "tps_pass_rush_snaps", "tps_pass_play_snaps"),
    ),
)

PASS_BLOCK_CAREER = CareerSpec(
    college_model=NCAAFPassBlockStat,
    member_model=NCAAFPassBlockCareerMember,
    data_columns=PASS_BLOCK_DATA_COLUMNS,
    weight_attr="non_spike_pb_snaps",
    tps_weight_attr="tps_non_spike_pb_snaps",
    sum_attrs=("games", "non_spike_pb_snaps", "tps_non_spike_pb_snaps"),
    order_attr="non_spike_pb_snaps",
)


def _aggregate_expressions(spec: CareerSpec) -> dict:
    """The SQL expression that merges each data column, keyed by its API key."""
    model = spec.college_model
    snaps_of = {attr: (rush, play) for attr, rush, play in spec.complement_snaps}
    expressions = dict()

    for column in spec.data_columns:
        attr = getattr(model, column.attr)

        if column.attr in spec.sum_attrs:
            expressions[column.api_key] = func.sum(attr)

        elif column.attr in snaps_of:
            rush_attr, play_attr = snaps_of[column.attr]
            rush_snaps = func.sum(getattr(model, rush_attr))
            play_snaps = func.sum(getattr(model, play_attr))
            expressions[column.api_key] = 100.0 - 100.0 * rush_snaps / func.nullif(
                play_snaps, 0
            )

        else:
            weight_name = (
                spec.tps_weight_attr
                if column.attr.startswith("tps_")
                else spec.weight_attr
            )

            weight = getattr(model, weight_name)

            # A season with no opportunities can hold an infinite rate (a pressure on a zero
            # denominator). Infinity times zero is NaN on Postgres, so such seasons are skipped.
            weighted_rate = case((weight > 0, attr * weight), else_=0)
            expressions[column.api_key] = func.sum(weighted_rate) / func.nullif(
                func.sum(weight), 0
            )

    return expressions


def _last_season_rows(sess: Session, spec: CareerSpec) -> dict:
    """Each member's row of his last college season, with his status.

    A player can hold two rows in one season (two positions); the one with more
    opportunities stands for him.
    """
    model = spec.college_model
    member_model = spec.member_model

    last_season = (
        select(model.player_id, func.max(model.season).label("last_season"))
        .group_by(model.player_id)
        .subquery()
    )

    rows = sess.execute(
        select(model, member_model.status)
        .join(
            last_season,
            and_(
                model.player_id == last_season.c.player_id,
                model.season == last_season.c.last_season,
            ),
        )
        .join(member_model, member_model.player_id == model.player_id)
    ).all()

    chosen = dict()

    for row, status in rows:
        current = chosen.get(row.player_id)
        count = getattr(row, spec.order_attr) or 0

        if current is None or count > (getattr(current[0], spec.order_attr) or 0):
            chosen[row.player_id] = (row, status)

    return chosen


def last_season_conferences(sess: Session, spec: CareerSpec) -> dict[int, str]:
    """The conference of each school a member last played for, for the Teams checklist."""
    return {
        row.team_code: row.conference
        for row, _status in _last_season_rows(sess, spec).values()
    }


def merged_career_rows(
    sess: Session, spec: CareerSpec, positions: tuple[str, ...]
) -> list[dict]:
    """The Career payload of every member whose last college position is in `positions`.

    Records come ordered by the category's count, most first. A member with no row
    left after the position filter (or none at all) is simply not listed.
    """
    model = spec.college_model
    expressions = _aggregate_expressions(spec)
    api_keys = list(expressions)
    sum_api_keys = {
        column.api_key for column in spec.data_columns if column.attr in spec.sum_attrs
    }

    aggregate_rows = sess.execute(
        select(
            model.player_id,
            func.min(model.season),
            func.max(model.season),
            func.count(func.distinct(model.season)),
            *expressions.values(),
        )
        .join(spec.member_model, spec.member_model.player_id == model.player_id)
        .group_by(model.player_id)
    ).all()

    last_rows = _last_season_rows(sess, spec)
    records = []

    for player_id, first_season, last_season, season_count, *values in aggregate_rows:
        last_row, status = last_rows[player_id]

        if last_row.position not in positions:
            continue

        record = {
            "id": player_id,
            "player_id": player_id,
            "player": last_row.player,
            "abbr_name": last_row.abbr_name,
            "position": last_row.position,
            "team": last_row.team_code,
            "conference": last_row.conference,
            "status": status,
            "first_season": first_season,
            "last_season": last_season,
            "seasons": season_count,
        }

        for api_key, value in zip(api_keys, values):
            if value is None:
                record[api_key] = None

            elif api_key in sum_api_keys:
                record[api_key] = int(value)

            else:
                record[api_key] = round(float(value), ROUNDING_DECIMALS)

        records.append(record)

    order_key = next(
        column.api_key for column in spec.data_columns if column.attr == spec.order_attr
    )
    records.sort(key=lambda record: (-(record[order_key] or 0), record["player_id"]))

    return records
