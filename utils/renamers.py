
def shorten_first_name(player_name: str) -> str:
    names_components = player_name.split(" ")
    if "." not in names_components[0]:  # First name isn't already shortened.
        names_components[0] = names_components[0][0] + "."
    return " ".join(names_components)

def rename_pass_rush_columns(columns: list[str]) -> list[str]:
    renamed_cols = []
    for column in columns:
        split_text = column.split("_")
        renamed_col = " ".join(text.capitalize() for text in split_text)

        if "Team Name" in renamed_col:
            renamed_col = renamed_col.replace(" Name", "")

        if "Player Game Count" in renamed_col:
            renamed_col = renamed_col.replace("Player Game Count", "Games")

        if "Wins" in renamed_col:
            renamed_col = renamed_col.replace("Pass Rush ", "")

        if "Total Pressures" in renamed_col:
            renamed_col = renamed_col.replace("Total ", "")

        if "Prp" in renamed_col:
            renamed_col = renamed_col.replace("Prp", "PRP")

        if "Grades Pass Rush Defense" in renamed_col:
            renamed_col = renamed_col.replace(
                "Grades Pass Rush Defense", "Pass Rush Grade"
            )

        if "Snap Counts Pass Rush" in renamed_col:
            renamed_col = renamed_col.replace("Snap Counts Pass Rush", "PR Snaps")

        if "Pass Rush Opp" in renamed_col:
            renamed_col = renamed_col.replace("Pass Rush Opp", "PR Opp")

        if "Pass Rush Win Rate" in renamed_col:
            renamed_col = renamed_col.replace("Pass Rush Win Rate", "Win Rate")

        renamed_cols.append(renamed_col.replace("True Pass Set", "TPS"))
    return renamed_cols


def rename_pass_block_columns(columns: list[str]) -> list[str]:
    renamed_cols = []
    for column in columns:
        split_text = column.split("_")
        renamed_col = " ".join(text.capitalize() for text in split_text)

        if "Team Name" in renamed_col:
            renamed_col = renamed_col.replace(" Name", "")

        if "Player Game Count" in renamed_col:
            renamed_col = renamed_col.replace("Player Game Count", "Games")

        if " Allowed" in renamed_col:
            renamed_col = renamed_col.replace(" Allowed", "")

        if "Pbe" in renamed_col:
            renamed_col = renamed_col.replace("Pbe", "PBE")

        if "Snap Counts Pass Block" in renamed_col:
            renamed_col = renamed_col.replace("Snap Counts Pass Block", "All PB Snaps")

        if "Non Spike Pass Block" in renamed_col:
            renamed_col = renamed_col.replace(
                "Non Spike Pass Block", "Non Spike PB Snaps"
            )

        renamed_cols.append(renamed_col.replace("True Pass Set", "TPS"))
    return renamed_cols
