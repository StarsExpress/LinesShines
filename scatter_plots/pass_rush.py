import os
import pandas as pd
import seaborn as sns
from matplotlib.offsetbox import AnnotationBbox
import matplotlib.pyplot as plt
from adjustText import adjust_text
from config import DATA_FOLDER_PATH, OUTPUTS_FOLDER_PATH, FRONT_7_NAMES
from utils.logo_boxes import load_logo_boxes
from utils.finders import find_median


def plot_pass_rush(
    season: int, position: str, opp_threshold: int,
    x_metric: str, y_metric: str, custom_title: str = None, extra_note: str = "",
) -> None:
    plt.figure(figsize=(10, 10))
    name_size = 6
    line_width = 3
    logo_boxes = load_logo_boxes()  # Each plot needs its own settings. Can't share across plots.

    if position not in FRONT_7_NAMES.keys():
        raise ValueError("Invalid position. Choose from DI, ED, or LB.")

    pass_rush_path = os.path.join(
        DATA_FOLDER_PATH, f"{season} NFL Front 7 Pass Rush.xlsx"
    )
    pass_rush_df_dict = pd.read_excel(pass_rush_path, sheet_name=None)

    pass_rush_df = pass_rush_df_dict[position].dropna()
    pass_rush_df = pass_rush_df[pass_rush_df["PR Opp"] >= opp_threshold]

    if len(pass_rush_df) <= 0:
        return

    x_axis_dict = {"metric": f"{x_metric}"}
    x_label_suffix = " (%)" if "Rate" in x_metric else ""
    x_axis_dict.update(
        {
            "col": f"{x_axis_dict['metric']}",
            "label": f"PFF {x_axis_dict['metric']}{x_label_suffix}",
        }
    )

    y_axis_dict = {"metric": f"{y_metric}"}
    y_label_suffix = " (%)" if "Rate" in y_metric else ""
    y_axis_dict.update(
        {
            "col": f"{y_axis_dict['metric']}",
            "label": f"PFF {y_axis_dict['metric']}{y_label_suffix}",
        }
    )

    # White dots prevent blocking team logos.
    sns.scatterplot(
        data=pass_rush_df,
        x=x_axis_dict["col"],
        y=y_axis_dict["col"],
        s=100,
        color="white",
    )

    placed_texts = []  # To prevent overlapping.
    for _, row in pass_rush_df.iterrows():  # Logo & name annotations.
        x_value, y_value = row[x_axis_dict["col"]], row[y_axis_dict["col"]]
        logo_box = AnnotationBbox(
            logo_boxes[row["Team"]],
            (x_value, y_value),
            frameon=False,
            box_alignment=(0.5, 0.5),
        )
        plt.gca().add_artist(logo_box)

        text = plt.text(
            x=x_value,
            y=y_value,
            s=row["Abbr Name"],
            fontdict=dict(color="black", size=name_size, ha="left", va="center"),
        )
        placed_texts.append(text)

    title = f"{season} NFL {FRONT_7_NAMES[position]} {x_metric} & {y_metric}" if custom_title is None else custom_title
    plt.title(title, fontsize=14, pad=40)

    note = (
        f"players with at least {opp_threshold} pass rush opportunities. Source: PFF."
    )
    if len(extra_note) > 0:
        note += f"\n{extra_note}"

    plt.text(
        x=0.5,
        y=1.05,
        s=f"Note: {len(pass_rush_df)} {note}",
        fontsize=10,
        ha="center",
        va="top",
        transform=plt.gca().transAxes,
    )

    plt.xlabel(x_axis_dict["label"])
    plt.ylabel(y_axis_dict["label"])

    x_median = find_median(pass_rush_df[x_axis_dict["col"]])
    plt.axvline(x=x_median, color="gray", linestyle="--")
    plt.text(
        x_median,
        plt.ylim()[0],
        f"Median: {x_median}",
        color="black",
        ha="center",
        va="top",
        fontsize=8,
    )

    y_median = find_median(pass_rush_df[y_axis_dict["col"]])
    plt.axhline(y=y_median, color="gray", linestyle="--")
    plt.text(
        plt.xlim()[0],
        y_median,
        f"Median: {y_median}",
        color="black",
        ha="right",
        va="center",
        fontsize=8,
        rotation="vertical",
    )

    adjust_text(placed_texts, dict(arrowstyle="-", color="black", linewidth=line_width))

    plot_path = os.path.join(
        OUTPUTS_FOLDER_PATH, f"{season}", "Pass Rush", f"{position} {x_metric} V.S {y_metric}.jpeg"
    )
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close("all")


if __name__ == "__main__":
    from config import HAVOC_NOTE

    queries = [
        [2025, "DI", 120], [2025, "ED", 120]
    ]
    for query_season, query_position, query_threshold in queries:
        plot_pass_rush(
            query_season, query_position, query_threshold,
            "TPS Win Rate", "Win Rate"
        )
    for query_season, query_position, query_threshold in queries:
        plot_pass_rush(
            query_season, query_position, query_threshold,
            "Pressure Rate", "Havoc Rate", extra_note=HAVOC_NOTE
        )
    for query_season, query_position, query_threshold in queries:
        plot_pass_rush(
            query_season, query_position, query_threshold,
            "TPS Pressure Rate", "Pressure Rate"
        )
