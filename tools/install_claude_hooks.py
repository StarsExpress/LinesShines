"""Register the LinesShines Claude Code hooks in the user-level settings, or remove them.

Dev-only tool, never imported by `main.py`. The hook scripts live in `tools/claude_hooks/` and
stay the source of truth; this writes only pointers (the Python to use plus an absolute script
path) into `~/.claude/settings.json`, so the hooks fire in every directory on the computer.
It touches only its own entries, so other hooks in the file are kept, and running it twice
changes nothing the second time.

Usage (from repo root, with the Python that has black and pytest installed):
    python -m tools.install_claude_hooks
    python -m tools.install_claude_hooks --remove
    python -m tools.install_claude_hooks --settings-path /tmp/settings.json
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent / "claude_hooks"
DEFAULT_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# (event, matcher or None, script, timeout in seconds). The gate may run pytest, so it gets the longest.
HOOK_DEFINITIONS: list[tuple[str, str | None, str, int]] = [
    ("SessionStart", "compact|resume", "session_start.py", 30),
    ("PreToolUse", "Bash", "pre_bash.py", 10),
    ("PreToolUse", "Write|Edit|MultiEdit", "pre_write.py", 10),
    ("PostToolUse", "Write|Edit|MultiEdit", "post_write.py", 180),
    ("Stop", None, "stop_gate.py", 600),
]


def load_settings(settings_path: Path) -> dict:
    """The settings as a dict; a missing file is an empty one, a broken file stops the run unchanged."""
    if not settings_path.exists():
        return {}

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8") or "{}")

    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{settings_path} is not valid JSON ({error}); nothing was changed."
        )

    if not isinstance(settings, dict):
        raise SystemExit(f"{settings_path} is not a JSON object; nothing was changed.")

    return settings


def is_ours(hook: dict) -> bool:
    """True for a hook entry whose command points into tools/claude_hooks/."""
    return str(HOOKS_DIR) in (hook.get("command") or "")


def remove_hooks(settings: dict) -> dict:
    """Drop this repo's hook entries; groups, events and the hooks key are dropped when they end up empty."""
    kept_events: dict[str, list] = {}

    for event_name, groups in (settings.get("hooks") or {}).items():
        kept_groups = []

        for group in groups:
            kept_hooks = [hook for hook in group.get("hooks", []) if not is_ours(hook)]

            if kept_hooks:
                kept_groups.append({**group, "hooks": kept_hooks})

        if kept_groups:
            kept_events[event_name] = kept_groups

    result = {key: value for key, value in settings.items() if key != "hooks"}

    if kept_events:
        result["hooks"] = kept_events

    return result


def install_hooks(settings: dict, python_path: str) -> dict:
    """Remove any earlier entries of ours, then add one group per hook definition."""
    result = remove_hooks(settings)
    events = result.setdefault("hooks", {})

    for event_name, matcher, script_name, timeout_seconds in HOOK_DEFINITIONS:
        command = (
            f"{shlex.quote(python_path)} {shlex.quote(str(HOOKS_DIR / script_name))}"
        )
        group: dict = {
            "hooks": [
                {"type": "command", "command": command, "timeout": timeout_seconds}
            ]
        }

        if matcher:
            group = {"matcher": matcher, **group}

        events.setdefault(event_name, []).append(group)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the hooks instead of installing them.",
    )
    parser.add_argument("--settings-path", type=Path, default=DEFAULT_SETTINGS_PATH)
    parser.add_argument(
        "--python-path", default=sys.executable, help="Python that runs the hooks."
    )
    arguments = parser.parse_args()

    settings = load_settings(arguments.settings_path)

    if arguments.remove:
        updated_settings = remove_hooks(settings)

    else:
        updated_settings = install_hooks(settings, arguments.python_path)

    arguments.settings_path.parent.mkdir(parents=True, exist_ok=True)
    arguments.settings_path.write_text(
        json.dumps(updated_settings, indent=2) + "\n", encoding="utf-8"
    )

    action = "removed from" if arguments.remove else "written to"
    print(f"LinesShines hooks {action} {arguments.settings_path}")


if __name__ == "__main__":
    main()
