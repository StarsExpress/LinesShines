"""PreToolUse hook on Write and Edit: keep PFF data out of the repo, ask before touching discussions/.

Invariant 13: raw PFF CSV and xlsx never enter the repo. `playbook/discussions/` holds the
owner's own files, so a write there is put to the owner as a question, not refused.
"""

from __future__ import annotations

import json

from hook_common import REPO_ROOT, block, file_path_of, is_under_repo, read_event

FORBIDDEN_SUFFIXES = {".csv", ".xlsx"}
DISCUSSIONS_DIR = REPO_ROOT / "playbook" / "discussions"

DATA_MESSAGE = (
    "Blocked by the LinesShines hook: {name} is a {suffix} file inside the repo. "
    "PFF raw data never enters the repo (playbook/INVARIANTS.md, invariant 13). "
    "Write it outside the repo, or ask the owner."
)
ASK_REASON = (
    "This writes into playbook/discussions/, which holds the owner's own files. "
    "Allow it only if the owner asked for this file."
)


def main() -> None:
    event = read_event()
    file_path = file_path_of(event)

    if file_path is None or not is_under_repo(file_path):
        return

    if file_path.suffix.lower() in FORBIDDEN_SUFFIXES:
        block(DATA_MESSAGE.format(name=file_path.name, suffix=file_path.suffix.lower()))

    if DISCUSSIONS_DIR in file_path.parents:
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": ASK_REASON,
            }
        }
        print(json.dumps(decision))


if __name__ == "__main__":
    main()
