"""Removes the cache files a session leaves behind in the repo.

These are `__pycache__` folders (Python), `__MACOSX` folders (macOS archive extraction) and
`.DS_Store` files (Finder). The Stop gate calls it after its checks, because the checks are
what create most of them. It is the same as running, from the repo root:

    find . -name "__pycache__" -type d -exec rm -r {} +
    find . -name "__MACOSX" -type d -exec rm -rf {} +
    find . -name ".DS_Store" -delete

Plain standard library, like every hook script, so it needs no package from the repo's Python.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

CACHE_DIRECTORY_NAMES = {"__pycache__", "__MACOSX"}
CACHE_FILE_NAMES = {".DS_Store"}

# Never walked: nothing of ours lives there, and node_modules alone holds thousands of folders.
SKIPPED_DIRECTORY_NAMES = {".git", "node_modules"}


def remove_cache_files(root: Path) -> int:
    """Delete every cache folder and file under the root and return how many were removed.

    A path that cannot be deleted (permissions, a file that vanished meanwhile) is left alone:
    cleaning up must never fail a session.
    """
    removed_count = 0

    for directory_path, directory_names, file_names in os.walk(root):
        # Pruning the list in place is how os.walk is told not to enter a folder.
        directory_names[:] = [
            name for name in directory_names if name not in SKIPPED_DIRECTORY_NAMES
        ]

        for directory_name in list(directory_names):
            if directory_name not in CACHE_DIRECTORY_NAMES:
                continue

            directory_names.remove(directory_name)
            shutil.rmtree(Path(directory_path) / directory_name, ignore_errors=True)
            removed_count += 1

        for file_name in file_names:
            if file_name not in CACHE_FILE_NAMES:
                continue

            try:
                (Path(directory_path) / file_name).unlink()
                removed_count += 1

            except OSError:
                continue

    return removed_count
