import os
from matplotlib.offsetbox import OffsetImage
import matplotlib.pyplot as plt
import pickle
from config import LOGOS_FOLDER_PATH, LOGOS_PICKLE_PATH, TEAMS


def save_logo_boxes(zoom: float) -> None:
    teams_logos = dict()
    for team in TEAMS:
        logo_path = os.path.join(LOGOS_FOLDER_PATH, f"{team}.png")
        teams_logos.update({team: OffsetImage(plt.imread(logo_path), zoom=zoom)})

    with open(LOGOS_PICKLE_PATH, "wb") as file:
        pickle.dump(teams_logos, file)


def load_logo_boxes() -> dict:
    with open(LOGOS_PICKLE_PATH, "rb") as file:
        logo_boxes = pickle.load(file)
    return logo_boxes


if __name__ == "__main__":
    save_logo_boxes(0.006)
