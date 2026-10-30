import pandas as pd
from config import OL_NAMES, League
from preprocessing.preprocess import (
    percent_of,
    require_columns,
    season_file_path,
    write_position_sheets,
)
from utils.renamers import rename_pass_block_columns, shorten_first_name

CATEGORY = "ol_pass_block"
REQUIRED_COLUMNS = [
    "Player",
    "Position",
    "Sacks",
    "Hits",
    "Pressures",
    "Non Spike PB Snaps",
    "TPS Sacks",
    "TPS Hits",
    "TPS Pressures",
    "TPS Non Spike PB Snaps",
]


def preprocess_offensive_line(league: League, season: int) -> None:
    pass_block_df = pd.read_csv(season_file_path(league, CATEGORY, season, "csv"))

    pass_block_df.fillna(inplace=True, value=0)
    pass_block_df.columns = rename_pass_block_columns(pass_block_df.columns)
    require_columns(pass_block_df, REQUIRED_COLUMNS, league, season)
    pass_block_df["Abbr Name"] = pass_block_df["Player"].apply(shorten_first_name)

    positional_sheets = dict()
    for position in OL_NAMES.keys():
        positional_df = pass_block_df[pass_block_df["Position"] == position]

        positional_df["Havoc"] = positional_df["Sacks"] + positional_df["Hits"]
        positional_df["Havoc %"] = percent_of(
            positional_df["Havoc"], positional_df["Non Spike PB Snaps"]
        )

        positional_df["Pressure %"] = percent_of(
            positional_df["Pressures"], positional_df["Non Spike PB Snaps"]
        )

        positional_df["TPS Havoc"] = (
            positional_df["TPS Sacks"] + positional_df["TPS Hits"]
        )
        positional_df["TPS Havoc %"] = percent_of(
            positional_df["TPS Havoc"], positional_df["TPS Non Spike PB Snaps"]
        )

        positional_df["TPS Pressure %"] = percent_of(
            positional_df["TPS Pressures"], positional_df["TPS Non Spike PB Snaps"]
        )

        positional_df.rename(
            columns={
                "Havoc %": "Allowed Havoc %",
                "Pressure %": "Allowed Pressure %",
                "TPS Havoc %": "TPS Allowed Havoc %",
                "TPS Pressure %": "TPS Allowed Pressure %",
            },
            inplace=True,
        )

        positional_sheets.update({position: positional_df})

    write_position_sheets(league, CATEGORY, season, positional_sheets)
