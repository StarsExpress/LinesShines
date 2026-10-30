import pandas as pd
from config import FRONT_7_NAMES, ROUNDING_DECIMALS, League
from preprocessing.preprocess import (
    percent_of,
    require_columns,
    season_file_path,
    write_position_sheets,
)
from utils.renamers import rename_pass_rush_columns, shorten_first_name

CATEGORY = "front_7_pass_rush"
REQUIRED_COLUMNS = [
    "Player",
    "Position",
    "Games",
    "PR Opp",
    "Sacks",
    "Hits",
    "Pressures",
    "TPS PR Opp",
    "TPS Sacks",
    "TPS Hits",
    "TPS Pressures",
]


def preprocess_front_7(league: League, season: int) -> None:
    pass_rush_df = pd.read_csv(season_file_path(league, CATEGORY, season, "csv"))

    pass_rush_df.fillna(inplace=True, value=0)
    pass_rush_df.columns = rename_pass_rush_columns(pass_rush_df.columns)
    require_columns(pass_rush_df, REQUIRED_COLUMNS, league, season)
    pass_rush_df["Abbr Name"] = pass_rush_df["Player"].apply(shorten_first_name)

    positional_sheets = dict()
    for position in FRONT_7_NAMES.keys():
        positional_df = pass_rush_df[pass_rush_df["Position"] == position]

        positional_df["Avg PR Opp"] = positional_df["PR Opp"] / positional_df["Games"]
        positional_df["Avg PR Opp"] = positional_df["Avg PR Opp"].round(
            ROUNDING_DECIMALS
        )

        positional_df["Havoc"] = positional_df["Sacks"] + positional_df["Hits"]
        positional_df["Havoc Rate"] = percent_of(
            positional_df["Havoc"], positional_df["PR Opp"]
        )

        positional_df["Pressure Rate"] = percent_of(
            positional_df["Pressures"], positional_df["PR Opp"]
        )

        positional_df["TPS Havoc"] = (
            positional_df["TPS Sacks"] + positional_df["TPS Hits"]
        )
        positional_df["TPS Havoc Rate"] = percent_of(
            positional_df["TPS Havoc"], positional_df["TPS PR Opp"]
        )

        positional_df["TPS Pressure Rate"] = percent_of(
            positional_df["TPS Pressures"], positional_df["TPS PR Opp"]
        )

        positional_sheets.update({position: positional_df})

    write_position_sheets(league, CATEGORY, season, positional_sheets)
