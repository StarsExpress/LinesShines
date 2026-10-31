"""The preprocessing scripts take a league: where files live, the column check, the command line."""

from __future__ import annotations
import pandas as pd
import pytest
import config
from config import League
from preprocessing.front_7 import preprocess_front_7
from preprocessing.offensive_line import preprocess_offensive_line
from preprocessing.preprocess import (
    apply_league_scope,
    main,
    parse_arguments,
    percent_of,
    season_file_path,
)

AKRON_ID = 102  # MAC in every season.
ALABAMA_ID = 103  # SEC in every season.
BYU_ID = 128  # Independent until 2022, Big 12 from 2023.
FCS_ID = 101  # Out of scope.
UNKNOWN_ID = 999999

FRONT_7_RAW = {
    "player": ["Alex Edge"],
    "team_name": ["AKRON"],
    "franchise_id": [AKRON_ID],
    "position": ["ED"],
    "player_game_count": [5],
    "pass_rush_opp": [100],
    "sacks": [2],
    "hits": [3],
    "total_pressures": [10],
    "true_pass_set_pass_rush_opp": [60],
    "true_pass_set_sacks": [1],
    "true_pass_set_hits": [2],
    "true_pass_set_total_pressures": [6],
}

OL_RAW = {
    "player": ["Taylor Tackle"],
    "team_name": ["AKRON"],
    "franchise_id": [AKRON_ID],
    "position": ["T"],
    "player_game_count": [5],
    "non_spike_pass_block": [200],
    "sacks_allowed": [1],
    "hits_allowed": [2],
    "pressures_allowed": [8],
    "true_pass_set_non_spike_pass_block": [120],
    "true_pass_set_sacks_allowed": [0],
    "true_pass_set_hits_allowed": [1],
    "true_pass_set_pressures_allowed": [5],
}

CASES = [
    ("front_7_pass_rush", preprocess_front_7, FRONT_7_RAW),
    ("ol_pass_block", preprocess_offensive_line, OL_RAW),
]


@pytest.fixture
def league_folders(tmp_path, monkeypatch):
    """Point both leagues at empty temporary folders."""
    paths = {League.NFL: str(tmp_path / "nfl"), League.NCAAF: str(tmp_path / "ncaaf")}
    monkeypatch.setattr(config.leagues, "LEAGUE_DATA_PATHS", paths)
    monkeypatch.setattr("preprocessing.preprocess.LEAGUE_DATA_PATHS", paths)

    for folder in paths.values():
        for category, _, _ in CASES:
            (tmp_path / folder / category).mkdir(parents=True)
    return paths


def test_there_are_two_leagues_named_after_their_data_folders():
    assert [league.value for league in League] == ["nfl", "ncaaf"]
    assert config.LEAGUE_DATA_PATHS[League.NFL] == config.NFL_DATA_PATH
    assert config.LEAGUE_DATA_PATHS[League.NCAAF] == config.NCAAF_DATA_PATH


def test_an_unknown_league_is_refused():
    with pytest.raises(ValueError):
        League("mlb")


def test_a_season_file_sits_under_its_leagues_folder():
    path = season_file_path(League.NCAAF, "ol_pass_block", 2026, "csv")

    assert path == f"{config.NCAAF_DATA_PATH}/ol_pass_block/2026.csv"


@pytest.mark.parametrize("category, preprocess, raw", CASES)
@pytest.mark.parametrize("league", list(League))
def test_the_workbook_is_written_beside_the_csv_of_the_same_league(
    league_folders, category, preprocess, raw, league
):
    other = next(candidate for candidate in League if candidate != league)
    pd.DataFrame(raw).to_csv(
        season_file_path(league, category, 2026, "csv"), index=False
    )

    preprocess(league, 2026)

    assert pd.ExcelFile(season_file_path(league, category, 2026, "xlsx")).sheet_names
    assert not pd.io.common.file_exists(season_file_path(other, category, 2026, "xlsx"))


@pytest.mark.parametrize("category, preprocess, raw", CASES)
def test_a_missing_column_names_the_league_the_season_and_the_column(
    league_folders, category, preprocess, raw
):
    broken = {key: value for key, value in raw.items() if key != "sacks"}
    broken.pop("sacks_allowed", None)
    pd.DataFrame(broken).to_csv(
        season_file_path(League.NCAAF, category, 2025, "csv"), index=False
    )

    with pytest.raises(ValueError, match=r"ncaaf 2025.*Sacks"):
        preprocess(League.NCAAF, 2025)

    assert not pd.io.common.file_exists(
        season_file_path(League.NCAAF, category, 2025, "xlsx")
    )


def test_the_command_line_needs_a_league_and_a_season():
    with pytest.raises(SystemExit):
        parse_arguments(["--seasons", "2026"])

    with pytest.raises(SystemExit):
        parse_arguments(["--league", "nfl"])


def test_the_command_line_refuses_an_unknown_league():
    with pytest.raises(SystemExit):
        parse_arguments(["--league", "mlb", "--seasons", "2026"])


def test_the_command_line_reads_a_league_and_one_season():
    arguments = parse_arguments(["--league", "ncaaf", "--seasons", "2026"])

    assert (arguments.league, arguments.seasons) == ("ncaaf", [2026])


def test_the_command_line_reads_several_seasons():
    arguments = parse_arguments(["--league", "nfl", "--seasons", "2024", "2025"])

    assert arguments.seasons == [2024, 2025]


def test_the_command_line_does_not_accept_a_shortened_flag():
    with pytest.raises(SystemExit):
        parse_arguments(["--league", "nfl", "--season", "2026"])


def test_an_error_in_one_csv_is_printed_and_the_rest_still_run(monkeypatch, capsys):
    done = []

    def front_7(league, season):
        if season == 2025:
            raise ValueError("ncaaf 2025: the CSV lacks the columns ['PR Opp']")
        done.append(("front_7", season))

    def offensive_line(league, season):
        done.append(("ol", season))

    monkeypatch.setattr("preprocessing.front_7.preprocess_front_7", front_7)
    monkeypatch.setattr(
        "preprocessing.offensive_line.preprocess_offensive_line", offensive_line
    )

    failures = main(["--league", "ncaaf", "--seasons", "2024", "2025", "2026"])

    assert done == [
        ("front_7", 2024),
        ("ol", 2024),
        ("ol", 2025),
        ("front_7", 2026),
        ("ol", 2026),
    ]
    assert len(failures) == 1
    assert failures[0].startswith("ncaaf 2025 front_7_pass_rush:")
    assert "FAILED ncaaf 2025 front_7_pass_rush" in capsys.readouterr().err


def test_without_an_error_nothing_is_reported_as_failed(monkeypatch, capsys):
    monkeypatch.setattr("preprocessing.front_7.preprocess_front_7", lambda *_: None)
    monkeypatch.setattr(
        "preprocessing.offensive_line.preprocess_offensive_line", lambda *_: None
    )

    assert main(["--league", "nfl", "--seasons", "2026"]) == []
    assert capsys.readouterr().err == ""


def test_percent_of_is_a_rounded_percentage():
    numerator = pd.Series([2.0, 3.0, 0.0])
    denominator = pd.Series([8.0, 12.0, 50.0])

    result = percent_of(numerator, denominator)

    assert list(result) == [25.0, 25.0, 0.0]


def test_percent_of_fills_a_zero_denominator_with_zero():
    result = percent_of(pd.Series([0.0]), pd.Series([0.0]))

    assert list(result) == [0.0]


def test_percent_of_rounds_to_the_configured_decimals():
    result = percent_of(pd.Series([1.0]), pd.Series([3.0]))

    assert list(result) == [round(100.0 / 3.0, config.ROUNDING_DECIMALS)]


def _schools_df(*franchise_ids: int) -> pd.DataFrame:
    """One renamed-CSV row per franchise id, as apply_league_scope sees it."""
    return pd.DataFrame(
        {
            "Team": [f"SCHOOL {franchise_id}" for franchise_id in franchise_ids],
            "Franchise Id": list(franchise_ids),
        }
    )


def test_the_nfl_keeps_every_row_and_gets_no_conference():
    schools_df = _schools_df(AKRON_ID, UNKNOWN_ID)

    scoped_df = apply_league_scope(schools_df, League.NFL, 2025)

    assert len(scoped_df) == 2
    assert "Conference" not in scoped_df.columns


def test_ncaaf_rows_get_the_conference_of_their_school_and_season():
    scoped_df = apply_league_scope(
        _schools_df(AKRON_ID, ALABAMA_ID), League.NCAAF, 2025
    )

    assert dict(zip(scoped_df["Franchise Id"], scoped_df["Conference"])) == {
        AKRON_ID: "MAC",
        ALABAMA_ID: "SEC",
    }


def test_ncaaf_schools_outside_the_scope_are_dropped():
    scoped_df = apply_league_scope(_schools_df(AKRON_ID, FCS_ID), League.NCAAF, 2025)

    assert list(scoped_df["Franchise Id"]) == [AKRON_ID]


def test_a_school_is_dropped_in_the_seasons_before_it_joined_the_scope():
    schools_df = _schools_df(BYU_ID)

    assert apply_league_scope(schools_df, League.NCAAF, 2022).empty
    assert list(apply_league_scope(schools_df, League.NCAAF, 2023)["Conference"]) == [
        "Big 12"
    ]


def test_an_unknown_school_raises_naming_the_school_and_the_season():
    with pytest.raises(ValueError, match=rf"ncaaf 2025.*SCHOOL {UNKNOWN_ID}"):
        apply_league_scope(_schools_df(AKRON_ID, UNKNOWN_ID), League.NCAAF, 2025)


def test_ncaaf_needs_the_franchise_id_column():
    schools_df = _schools_df(AKRON_ID).drop(columns=["Franchise Id"])

    with pytest.raises(ValueError, match=r"ncaaf 2025.*Franchise Id"):
        apply_league_scope(schools_df, League.NCAAF, 2025)


@pytest.mark.parametrize("category, preprocess, raw", CASES)
def test_the_ncaaf_workbook_carries_the_conference_and_only_scoped_schools(
    league_folders, category, preprocess, raw
):
    # Two rows per column: one scoped school and one out of scope.
    scoped_and_out = {key: value + value for key, value in raw.items()}
    scoped_and_out["franchise_id"] = [AKRON_ID, FCS_ID]
    pd.DataFrame(scoped_and_out).to_csv(
        season_file_path(League.NCAAF, category, 2025, "csv"), index=False
    )

    preprocess(League.NCAAF, 2025)

    sheets = pd.read_excel(
        season_file_path(League.NCAAF, category, 2025, "xlsx"), sheet_name=None
    )
    rows_df = pd.concat([sheet for sheet in sheets.values() if not sheet.empty])
    assert list(rows_df["Conference"]) == ["MAC"]
    assert list(rows_df["Franchise Id"]) == [AKRON_ID]


@pytest.mark.parametrize("category, preprocess, raw", CASES)
def test_the_nfl_workbook_has_no_conference_column(
    league_folders, category, preprocess, raw
):
    pd.DataFrame(raw).to_csv(
        season_file_path(League.NFL, category, 2025, "csv"), index=False
    )

    preprocess(League.NFL, 2025)

    sheets = pd.read_excel(
        season_file_path(League.NFL, category, 2025, "xlsx"), sheet_name=None
    )
    assert all("Conference" not in sheet.columns for sheet in sheets.values())
