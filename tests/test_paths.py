"""Guards against the data/ and frontend/ layouts silently drifting.

These are the two paths that broke before: the /logos mount pointed at a
folder that didn't exist, and data/ was flat with descriptive filenames
that preprocessing/db_ingestion had to reproduce exactly by hand.

NOTE: data/*.csv and data/*.xlsx are git-ignored on purpose (raw PFF exports
never get committed — see .gitignore), so a CI checkout has the
front_7_pass_rush/ and ol_pass_block/ directories (kept alive via
.gitkeep) but none of the actual season files. These tests therefore
assert on *structure and naming convention*, not on any specific season
being present — real per-season coverage only happens where files exist
(e.g. local dev machines with real data checked out).
"""

from __future__ import annotations
import re
from pathlib import Path
import config


REPO_ROOT = Path(__file__).resolve().parent.parent
SEASON_FILENAME_RE = re.compile(r"^\d{4}\.(csv|xlsx)$")


def test_data_folder_path_matches_repo_layout():
    assert config.DATA_FOLDER_PATH == str(REPO_ROOT / "data")
    assert Path(config.DATA_FOLDER_PATH).is_dir()


def _assert_category_dir_well_formed(category_dir: Path):
    assert category_dir.is_dir()
    for path in category_dir.iterdir():
        if path.name not in (".gitkeep", ".DS_Store"):
            assert SEASON_FILENAME_RE.match(path.name), (
                f"{path} doesn't match the `{{season}}.csv`/`{{season}}.xlsx` "
                "naming convention"
            )


def test_front_7_pass_rush_category_layout():
    _assert_category_dir_well_formed(
        Path(config.DATA_FOLDER_PATH) / "front_7_pass_rush"
    )


def test_ol_pass_block_category_layout():
    _assert_category_dir_well_formed(Path(config.DATA_FOLDER_PATH) / "ol_pass_block")


def test_no_legacy_flat_data_files():
    """Catches regression back to the old `{season} NFL ....csv` flat files."""
    legacy = list(Path(config.DATA_FOLDER_PATH).glob("* NFL *"))
    assert not legacy, f"legacy flat data files found at data/ root: {legacy}"


def test_team_logo_directory():
    logos_dir = REPO_ROOT / "frontend" / "images" / "team_logos"
    assert logos_dir.is_dir()
    assert list(logos_dir.glob("*.png")), "no logo PNGs found"
