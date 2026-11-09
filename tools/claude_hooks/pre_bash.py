"""PreToolUse hook on Bash: never run git, railway, psql or pkill (the owner does).

The command text is searched, not only its first word, so `cd x && git status` and
`bash -c "git ..."` are caught too. One `pkill` is let through, the one the project
allows to stop its dev server; chaining anything after it blocks it again.
"""

from __future__ import annotations

import re

from hook_common import block, command_concerns_repo, read_event

# A forbidden program name, not part of a longer word, path piece or option (`.gitignore`, `.github`, `git-lfs`).
FORBIDDEN_PROGRAM_PATTERN = re.compile(
    r"(?<![\w.\-])(git|railway|psql|pkill)(?![\w\-])"
)

# The whole command must be this and nothing else: quoted pattern without shell operators inside.
ALLOWED_PKILL_PATTERN = re.compile(
    r"""pkill -f (?:"uvicorn main:app [^"`$\\]*"|'uvicorn main:app [^'`$\\]*')"""
)

BLOCK_MESSAGE = (
    "Blocked by the LinesShines hook: '{program}' is not run by Claude. "
    "The owner does all git, Railway and database work (playbook/INVARIANTS.md, Working rules). "
    "Do not reword the command to get around this; say what you wanted to learn and ask the owner."
)


def forbidden_program(command: str) -> str | None:
    """The first forbidden program in the command, or None when the command is allowed."""
    if ALLOWED_PKILL_PATTERN.fullmatch(command.strip()):
        return None

    match = FORBIDDEN_PROGRAM_PATTERN.search(command)

    return match.group(1) if match else None


def main() -> None:
    event = read_event()
    command = (event.get("tool_input") or {}).get("command") or ""

    if not command_concerns_repo(command, event.get("cwd") or ""):
        return

    program = forbidden_program(command)

    if program:
        block(BLOCK_MESSAGE.format(program=program))


if __name__ == "__main__":
    main()
