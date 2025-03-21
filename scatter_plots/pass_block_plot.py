import os
import pandas as pd
import seaborn as sns
from matplotlib.offsetbox import AnnotationBbox
import matplotlib.pyplot as plt
from adjustText import adjust_text
from config import DATA_FOLDER_PATH, OUTPUTS_FOLDER_PATH, OL_NAMES
from utils.logo_boxes import load_logo_boxes
from utils.finders import find_median


def plot_pass_block(
    season: int, position: str, non_spike_threshold: int,
    x_metric: str, y_metric: str, custom_title: str = None, extra_note: str = "",
) -> None:
    plt.figure(figsize=(10, 10))
    name_size = 6
    line_width = 3
    logo_boxes = load_logo_boxes()  # Each plot needs its own settings. Can't share across plots.

    if position not in OL_NAMES.keys():
        raise ValueError("Invalid position. Choose from T, G, or C.")

    pass_block_path = os.path.join(
        DATA_FOLDER_PATH, f"{season} NFL OL Pass Block.xlsx"
    )
    pass_block_df_dict = pd.read_excel(pass_block_path, sheet_name=None)

    pass_block_df = pass_block_df_dict[position].dropna()
    pass_block_df = pass_block_df[pass_block_df["Non Spike PB Snaps"] >= non_spike_threshold]
    if len(pass_block_df) <= 0:
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
        data=pass_block_df,
        x=x_axis_dict["col"],
        y=y_axis_dict["col"],
        s=100,
        color="white",
    )

    placed_texts = []  # To prevent overlapping.
    for _, row in pass_block_df.iterrows():  # Logo & name annotations.
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

    title = f"{season} NFL {OL_NAMES[position]} {x_metric} & {y_metric}" if custom_title is None else custom_title
    plt.title(title, fontsize=14, pad=40)

    note = (
        f"players with at least {non_spike_threshold} non spike pass block snaps. Source: PFF."
    )
    if len(extra_note) > 0:
        note += f"\n{extra_note}"

    plt.text(
        x=0.5,
        y=1.05,
        s=f"Note: {len(pass_block_df)} {note}",
        fontsize=10,
        ha="center",
        va="top",
        transform=plt.gca().transAxes,
    )

    plt.gca().invert_xaxis()  # OL metrics are better when allowed numbers are lower.
    plt.xlabel(x_axis_dict["label"])
    plt.gca().invert_yaxis()  # OL metrics are better when allowed numbers are lower.
    plt.ylabel(y_axis_dict["label"])

    x_median = find_median(pass_block_df[x_axis_dict["col"]])
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

    y_median = find_median(pass_block_df[y_axis_dict["col"]])
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
        OUTPUTS_FOLDER_PATH, f"{season}", "Pass Block", f"{position} {x_metric} V.S {y_metric}.jpeg"
    )
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close("all")


if __name__ == "__main__":
    queries = [
        [2024, "T", 300], [2024, "G", 300], [2024, "C", 300]
    ]
    for query_season, query_position, query_threshold in queries:
        plot_pass_block(
            query_season, query_position, query_threshold,
            "TPS Allowed Pressure %", "Allowed Pressure %"
        )
        plot_pass_block(
            query_season, query_position, query_threshold,
            "TPS Allowed Havoc %", "Allowed Havoc %"
        )
