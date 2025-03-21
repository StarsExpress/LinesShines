import os
import pandas as pd
from config import DATA_FOLDER_PATH, OL_NAMES, ROUNDING_DIGITS
from utils.renamers import rename_pass_block_columns, shorten_first_name


def preprocess_offensive_line(season: int) -> None:
    pass_block_csv_path = os.path.join(
        DATA_FOLDER_PATH, f"{season} NFL OL Pass Block.csv"
    )
    pass_block_df = pd.read_csv(pass_block_csv_path)
    pass_block_df.fillna(inplace=True, value=0)
    pass_block_df.columns = rename_pass_block_columns(pass_block_df.columns)
    pass_block_df["Abbr Name"] = pass_block_df["Player"].apply(shorten_first_name)

    positional_sheets = dict()
    for position in OL_NAMES.keys():
        positional_df = pass_block_df[pass_block_df["Position"] == position]

        positional_df["Havoc"] = positional_df["Sacks"] + positional_df["Hits"]
        positional_df["Havoc %"] = positional_df["Havoc"] / positional_df["Non Spike PB Snaps"]
        positional_df["Havoc %"].fillna(inplace=True, value=0)
        positional_df["Havoc %"] *= 100
        positional_df["Havoc %"] = positional_df["Havoc %"].round(ROUNDING_DIGITS)

        positional_df["Pressure %"] = positional_df["Pressures"] / positional_df["Non Spike PB Snaps"]

        positional_df["Pressure %"].fillna(inplace=True, value=0)
        positional_df["Pressure %"] *= 100
        positional_df["Pressure %"] = positional_df["Pressure %"].round(ROUNDING_DIGITS)

        positional_df["TPS Havoc"] = positional_df["TPS Sacks"] + positional_df["TPS Hits"]

        positional_df["TPS Havoc %"] = positional_df["TPS Havoc"] / positional_df["TPS Non Spike PB Snaps"]

        positional_df["TPS Havoc %"].fillna(inplace=True, value=0)
        positional_df["TPS Havoc %"] *= 100
        positional_df["TPS Havoc %"] = positional_df["TPS Havoc %"].round(ROUNDING_DIGITS)

        positional_df["TPS Pressure %"] = positional_df["TPS Pressures"] / positional_df["TPS Non Spike PB Snaps"]

        positional_df["TPS Pressure %"].fillna(inplace=True, value=0)
        positional_df["TPS Pressure %"] *= 100
        positional_df["TPS Pressure %"] = positional_df["TPS Pressure %"].round(ROUNDING_DIGITS)

        positional_df.rename(
            columns={
                "Havoc %": "Allowed Havoc %",
                "Pressure %": "Allowed Pressure %",
                "TPS Havoc %": "TPS Allowed Havoc %",
                "TPS Pressure %": "TPS Allowed Pressure %"
            },
            inplace=True
        )

        positional_sheets.update({position: positional_df})

    destination_path = os.path.join(
        DATA_FOLDER_PATH, f"{season} NFL OL Pass Block.xlsx"
    )
    with pd.ExcelWriter(destination_path, engine="openpyxl") as writer:
        for position, sheet in positional_sheets.items():
            sheet.to_excel(writer, sheet_name=position, index=False)


if __name__ == "__main__":
    preprocess_offensive_line(2024)
