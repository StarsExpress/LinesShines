"""The columns of each stat category, declared once for models, ingestion and the API.

Each `DataColumn` ties the Excel header in the preprocessed workbook to the model
attribute, the API payload key, and how the value is read. This one declaration
feeds the ingestion's required-column check and row building and the API
serializer, so a category's columns are added in a single place; a test checks
that the models carry exactly these attributes. The NFL tables use it now and the
college tables reuse it unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataColumn:
    excel_header: str  # Column name in the preprocessed xlsx sheet.
    attr: str  # Model attribute and ORM column name.
    api_key: str  # Key in the /api payload.
    kind: str  # "int", "float", or "complement" (stored as 100 - the Excel value).


# Identity columns read from every sheet. "Team" serializes as "team" and reads
# into team_code; "Player Id" reads into player_id.
IDENTITY_EXCEL_HEADERS = ("Team", "Player Id", "Player", "Abbr Name")


PASS_RUSH_DATA_COLUMNS = (
    DataColumn("Games", "games", "games", "int"),
    DataColumn("PR Opp", "pr_opp", "PR Opp", "int"),
    DataColumn("TPS PR Opp", "tps_pr_opp", "TPS PR Opp", "int"),
    DataColumn(
        "Pass Rush Percent", "pass_cov_percent", "Pass Cov Percent", "complement"
    ),
    DataColumn(
        "TPS Pass Rush Percent",
        "tps_pass_cov_percent",
        "TPS Pass Cov Percent",
        "complement",
    ),
    DataColumn("Win Rate", "win_rate", "Win Rate", "float"),
    DataColumn("TPS Win Rate", "tps_win_rate", "TPS Win Rate", "float"),
    DataColumn("Pressure Rate", "pressure_rate", "Pressure Rate", "float"),
    DataColumn("TPS Pressure Rate", "tps_pressure_rate", "TPS Pressure Rate", "float"),
    DataColumn("Havoc Rate", "havoc_rate", "Havoc Rate", "float"),
    DataColumn("TPS Havoc Rate", "tps_havoc_rate", "TPS Havoc Rate", "float"),
    DataColumn("PRP", "prp", "PRP", "float"),
    DataColumn("TPS PRP", "tps_prp", "TPS PRP", "float"),
)


PASS_BLOCK_DATA_COLUMNS = (
    DataColumn("Games", "games", "games", "int"),
    DataColumn("Non Spike PB Snaps", "non_spike_pb_snaps", "Non Spike PB Snaps", "int"),
    DataColumn(
        "TPS Non Spike PB Snaps",
        "tps_non_spike_pb_snaps",
        "TPS Non Spike PB Snaps",
        "int",
    ),
    DataColumn(
        "Allowed Pressure %", "allowed_pressure_pct", "Allowed Pressure %", "float"
    ),
    DataColumn(
        "TPS Allowed Pressure %",
        "tps_allowed_pressure_pct",
        "TPS Allowed Pressure %",
        "float",
    ),
    DataColumn("Allowed Havoc %", "allowed_havoc_pct", "Allowed Havoc %", "float"),
    DataColumn(
        "TPS Allowed Havoc %", "tps_allowed_havoc_pct", "TPS Allowed Havoc %", "float"
    ),
    DataColumn("PBE", "pbe", "PBE", "float"),
    DataColumn("TPS PBE", "tps_pbe", "TPS PBE", "float"),
)


# The four snap counts behind Pass Cov Percent, kept only for the college Career merge
# (Career Pass Cov Percent = 100 - the sum of the rush snaps over the sum of the pass plays,
# which the stored percentage alone cannot rebuild). They are never part of the /api payload,
# so they are not in PASS_RUSH_DATA_COLUMNS; the ingestion reads them as extra columns.
NCAAF_PASS_RUSH_SNAP_COLUMNS = (
    DataColumn("PR Snaps", "pass_rush_snaps", "PR Snaps", "int"),
    DataColumn("Snap Counts Pass Play", "pass_play_snaps", "Pass Play Snaps", "int"),
    DataColumn("TPS PR Snaps", "tps_pass_rush_snaps", "TPS PR Snaps", "int"),
    DataColumn(
        "TPS Snap Counts Pass Play",
        "tps_pass_play_snaps",
        "TPS Pass Play Snaps",
        "int",
    ),
)


# The OL-only share of pass block snaps that were true pass sets. It is never stored: the API
# computes it from the two snap counts, so the season and Career payloads stay in step.
TPS_PROPORTION_API_KEY = "TPS Proportion %"
TPS_PROPORTION_DECIMALS = 1


def tps_proportion_pct(tps_snaps: int | None, snaps: int | None) -> float | None:
    """TPS Non Spike PB Snaps / Non Spike PB Snaps x 100, or None when it is undefined."""
    if tps_snaps is None or not snaps:
        return None

    return round(100.0 * tps_snaps / snaps, TPS_PROPORTION_DECIMALS)


def with_tps_proportion(payload: dict) -> dict:
    """The pass block payload with its TPS Proportion % added, from its two snap counts."""
    payload[TPS_PROPORTION_API_KEY] = tps_proportion_pct(
        payload.get("TPS Non Spike PB Snaps"), payload.get("Non Spike PB Snaps")
    )

    return payload


def required_excel_headers(data_columns: tuple[DataColumn, ...]) -> tuple[str, ...]:
    """The headers a sheet must have: the identity columns plus every data column."""
    return IDENTITY_EXCEL_HEADERS + tuple(
        column.excel_header for column in data_columns
    )


def row_to_payload(row, data_columns: tuple[DataColumn, ...]) -> dict:
    """The /api payload for one ORM row: the common identity keys plus each data key."""
    payload = {
        "id": row.id,
        "season": row.season,
        "position": row.position,
        "team": row.team_code,
        "player_id": row.player_id,
        "player": row.player,
        "abbr_name": row.abbr_name,
    }

    for column in data_columns:
        payload[column.api_key] = getattr(row, column.attr)

    return payload
