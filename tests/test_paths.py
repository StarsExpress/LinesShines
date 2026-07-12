"""Guards against the data/ and frontend/ layouts silently drifting.

These are the two paths that broke before: the /logos mount pointed at a
folder that didn't exist, and data/ was flat with descriptive filenames
that preprocessing/db_ingestion had to reproduce exactly by hand.

NOTE: data/*.csv and data/*.xlsx are git-ignored on purpose (raw PFF exports
never get committed — see .gitignore), and front_7_pass_rush/ and
ol_pass_block/ hold nothing else, so a CI checkout doesn't have those
directories at all (git doesn't track empty dirs). Tests here only assert
what's true regardless of whether real season data is checked out.
"""

from __future__ import annotations
from pathlib import Path
import config

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_data_folder_path_matches_repo_layout():
    assert config.DATA_FOLDER_PATH == str(REPO_ROOT / "data")


def test_no_legacy_flat_data_files():
    """Catches regression back to the old `{season} NFL ....csv` flat files."""
    legacy = list(Path(config.DATA_FOLDER_PATH).glob("* NFL *"))
    assert not legacy, f"legacy flat data files found at data/ root: {legacy}"


def test_team_logo_directory():
    logos_dir = REPO_ROOT / "frontend" / "images" / "team_logos"
    assert logos_dir.is_dir()
    assert list(logos_dir.glob("*.png")), "no logo PNGs found"
