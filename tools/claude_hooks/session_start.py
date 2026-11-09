"""SessionStart hook (matchers `compact` and `resume`): put the working rules back into the context.

After a compaction or a resume Claude has lost `INVARIANTS.md`. This prints its "Working rules"
section and the names in `next_steps/` as plain stdout, which Claude Code adds to the context.
It prints only when the session starts in the repo, inside it, or in the folder directly above it.
"""

from __future__ import annotations

from hook_common import REPO_ROOT, read_event, session_concerns_repo

INVARIANTS_PATH = REPO_ROOT / "playbook" / "INVARIANTS.md"
NEXT_STEPS_DIR = REPO_ROOT / "playbook" / "next_steps"
RULES_HEADING = "## Working rules"

# Claude Code caps the context a SessionStart hook adds at 10,000 characters.
MAX_CHARACTERS = 9500


def working_rules_text() -> str:
    """The 'Working rules' section of INVARIANTS.md, up to the next '## ' heading."""
    if not INVARIANTS_PATH.is_file():
        return ""

    kept_lines: list[str] = []
    inside_rules = False

    for line in INVARIANTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(RULES_HEADING):
            inside_rules = True

        elif inside_rules and line.startswith("## "):
            break

        if inside_rules:
            kept_lines.append(line)

    return "\n".join(kept_lines)


def next_steps_names() -> list[str]:
    """File names in next_steps/, the work items the owner may name."""
    if not NEXT_STEPS_DIR.is_dir():
        return []

    return sorted(path.name for path in NEXT_STEPS_DIR.glob("*.md"))


def main() -> None:
    event = read_event()

    if not session_concerns_repo(event.get("cwd") or ""):
        return

    rules = working_rules_text()

    if not rules:
        return

    names = next_steps_names()
    names_text = ", ".join(names) if names else "(none)"

    text = (
        "LinesShines session restored. These are the working rules from playbook/INVARIANTS.md; "
        "re-read that file fully before editing anything.\n\n"
        f"{rules}\n\n"
        f"Files in playbook/next_steps/ (work only on the one the owner names): {names_text}\n"
    )

    print(text[:MAX_CHARACTERS])


if __name__ == "__main__":
    main()
