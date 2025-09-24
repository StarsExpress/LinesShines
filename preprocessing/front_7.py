import os
import pandas as pd
from config import DATA_FOLDER_PATH, FRONT_7_NAMES, ROUNDING_DIGITS
from utils.renamers import rename_pass_rush_columns, shorten_first_name


def preprocess_front_7(season: int) -> None:
    pass_rush_csv_path = os.path.join(
        DATA_FOLDER_PATH, f"{season} NFL Front 7 Pass Rush.csv"
    )
    pass_rush_df = pd.read_csv(pass_rush_csv_path)
    pass_rush_df.fillna(inplace=True, value=0)
    pass_rush_df.columns = rename_pass_rush_columns(pass_rush_df.columns)
    pass_rush_df["Abbr Name"] = pass_rush_df["Player"].apply(shorten_first_name)

    positional_sheets = dict()
    for position in FRONT_7_NAMES.keys():
        positional_df = pass_rush_df[pass_rush_df["Position"] == position]

        positional_df["Avg PR Opp"] = positional_df["PR Opp"] / positional_df["Games"]
        positional_df["Avg PR Opp"] = positional_df["Avg PR Opp"].round(ROUNDING_DIGITS)

        positional_df["Havoc"] = positional_df["Sacks"] + positional_df["Hits"]
        positional_df["Havoc Rate"] = positional_df["Havoc"] / positional_df["PR Opp"]
        positional_df["Havoc Rate"].fillna(inplace=True, value=0)
        positional_df["Havoc Rate"] *= 100
        positional_df["Havoc Rate"] = positional_df["Havoc Rate"].round(ROUNDING_DIGITS)

        positional_df["Pressure Rate"] = positional_df["Pressures"] / positional_df["PR Opp"]

        positional_df["Pressure Rate"].fillna(inplace=True, value=0)
        positional_df["Pressure Rate"] *= 100
        positional_df["Pressure Rate"] = positional_df["Pressure Rate"].round(ROUNDING_DIGITS)

        positional_df["TPS Havoc"] = positional_df["TPS Sacks"] + positional_df["TPS Hits"]

        positional_df["TPS Havoc Rate"] = positional_df["TPS Havoc"] / positional_df["TPS PR Opp"]

        positional_df["TPS Havoc Rate"].fillna(inplace=True, value=0)
        positional_df["TPS Havoc Rate"] *= 100
        positional_df["TPS Havoc Rate"] = positional_df["TPS Havoc Rate"].round(ROUNDING_DIGITS)

        positional_df["TPS Pressure Rate"] = positional_df["TPS Pressures"] / positional_df["TPS PR Opp"]

        positional_df["TPS Pressure Rate"].fillna(inplace=True, value=0)
        positional_df["TPS Pressure Rate"] *= 100
        positional_df["TPS Pressure Rate"] = positional_df["TPS Pressure Rate"].round(ROUNDING_DIGITS)

        positional_sheets.update({position: positional_df})

    destination_path = os.path.join(
        DATA_FOLDER_PATH, f"{season} NFL Front 7 Pass Rush.xlsx"
    )
    with pd.ExcelWriter(destination_path, engine="openpyxl") as writer:
        for position, sheet in positional_sheets.items():
            sheet.to_excel(writer, sheet_name=position, index=False)


if __name__ == "__main__":
    preprocess_front_7(2025)
