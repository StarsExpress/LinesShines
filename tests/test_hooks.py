"""The Claude Code hooks in tools/claude_hooks/ and the installer that registers them.

Each hook is run the way Claude Code runs it: a subprocess that reads one JSON event on stdin.
No test runs black, Prettier, ESLint or the real CI set; the gate's checks are replaced through
the environment variable the gate offers for this.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import install_claude_hooks

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "tools" / "claude_hooks"
STATE_DIR_ENV_VAR = "LINES_SHINES_HOOK_STATE_DIR"
CHECKS_ENV_VAR = "LINES_SHINES_HOOK_CHECKS"
PKILL_COMMAND = 'pkill -f "uvicorn main:app *"'


def run_hook(
    script_name: str, event: dict, state_dir: Path, checks: list[dict] | None = None
):
    """Run one hook script with the event on stdin; returns the finished process."""
    environment = {"PATH": "/usr/bin:/bin", STATE_DIR_ENV_VAR: str(state_dir)}

    if checks is not None:
        environment[CHECKS_ENV_VAR] = json.dumps(checks)

    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / script_name)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )


def bash_event(command: str, working_directory: Path = REPO_ROOT) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(working_directory),
    }


def write_event(file_path: str, working_directory: Path = REPO_ROOT) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "cwd": str(working_directory),
    }


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    return tmp_path / "state"


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "cd /somewhere && git log",
        'bash -c "git diff"',
        "ls | git apply",
        "/usr/bin/git status",
        "railway up",
        "psql $DATABASE_URL",
        "pkill python",
        PKILL_COMMAND + "; git status",
        PKILL_COMMAND + " && echo done",
        PKILL_COMMAND + " | cat",
        'pkill -f "uvicorn main:app $(whoami)"',
    ],
)
def test_bash_hook_blocks_forbidden_programs_in_the_repo(command: str, state_dir: Path):
    result = run_hook("pre_bash.py", bash_event(command), state_dir)

    assert result.returncode == 2
    assert "Blocked by the LinesShines hook" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "pytest -v",
        "black -S .",
        "cat .gitignore",
        "ls .github/workflows",
        "cat .git/config",
        "echo digit and widget",
        PKILL_COMMAND,
        "pkill -f 'uvicorn main:app --port 8000'",
    ],
)
def test_bash_hook_lets_ordinary_commands_and_the_one_pkill_through(
    command: str, state_dir: Path
):
    result = run_hook("pre_bash.py", bash_event(command), state_dir)

    assert result.returncode == 0
    assert result.stderr == ""


def test_bash_hook_catches_a_cd_by_folder_name_from_the_parent_folder(state_dir: Path):
    command = f"cd {REPO_ROOT.name} && git status"

    result = run_hook("pre_bash.py", bash_event(command, REPO_ROOT.parent), state_dir)

    assert result.returncode == 2


def test_bash_hook_leaves_other_projects_alone(tmp_path: Path, state_dir: Path):
    result = run_hook("pre_bash.py", bash_event("git status", tmp_path), state_dir)

    assert result.returncode == 0
    assert result.stderr == ""


def test_bash_hook_survives_empty_input(state_dir: Path):
    result = run_hook("pre_bash.py", {}, state_dir)

    assert result.returncode == 0


@pytest.mark.parametrize("name", ["pff.csv", "pff.XLSX", "data/2025/front_7.csv"])
def test_write_hook_blocks_pff_data_inside_the_repo(name: str, state_dir: Path):
    result = run_hook("pre_write.py", write_event(str(REPO_ROOT / name)), state_dir)

    assert result.returncode == 2
    assert "invariant 13" in result.stderr


def test_write_hook_allows_a_csv_outside_the_repo(tmp_path: Path, state_dir: Path):
    result = run_hook(
        "pre_write.py", write_event(str(tmp_path / "pff.csv"), tmp_path), state_dir
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_write_hook_resolves_a_relative_path_against_the_working_directory(
    state_dir: Path,
):
    result = run_hook("pre_write.py", write_event("pff.csv"), state_dir)

    assert result.returncode == 2


def test_write_hook_asks_before_writing_into_discussions(state_dir: Path):
    file_path = REPO_ROOT / "playbook" / "discussions" / "NEW-IDEA.md"

    result = run_hook("pre_write.py", write_event(str(file_path)), state_dir)
    decision = json.loads(result.stdout)["hookSpecificOutput"]

    assert result.returncode == 0
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "ask"


def test_write_hook_stays_silent_for_an_ordinary_repo_file(state_dir: Path):
    result = run_hook(
        "pre_write.py", write_event(str(REPO_ROOT / "main.py")), state_dir
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_post_write_hook_marks_the_session_when_the_repo_changed(state_dir: Path):
    event = {
        **write_event(str(REPO_ROOT / "playbook" / "COMMANDS.md")),
        "session_id": "abc",
    }

    result = run_hook("post_write.py", event, state_dir)

    assert result.returncode == 0
    assert (state_dir / "abc.changed").exists()


def test_post_write_hook_ignores_a_file_outside_the_repo(
    tmp_path: Path, state_dir: Path
):
    event = {**write_event(str(tmp_path / "notes.py"), tmp_path), "session_id": "abc"}

    result = run_hook("post_write.py", event, state_dir)

    assert result.returncode == 0
    assert not (state_dir / "abc.changed").exists()


def test_stop_gate_does_nothing_when_the_repo_did_not_change(state_dir: Path):
    failing_check = [
        {
            "name": "always fails",
            "command": [sys.executable, "-c", "raise SystemExit(1)"],
        }
    ]

    result = run_hook("stop_gate.py", {"session_id": "abc"}, state_dir, failing_check)

    assert result.returncode == 0
    assert result.stdout == ""


def marked_state_dir(state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "abc.changed").touch()

    return state_dir


def test_stop_gate_blocks_once_and_names_the_failed_step(state_dir: Path):
    checks = [
        {"name": "good step", "command": [sys.executable, "-c", "print('fine')"]},
        {
            "name": "bad step",
            "command": [
                sys.executable,
                "-c",
                "print('boom detail'); raise SystemExit(1)",
            ],
        },
    ]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )
    decision = json.loads(result.stdout)

    assert result.returncode == 0
    assert decision["decision"] == "block"
    assert "[bad step]" in decision["reason"]
    assert "boom detail" in decision["reason"]
    assert "[good step]" not in decision["reason"]
    assert (state_dir / "abc.changed").exists()


def test_stop_gate_never_blocks_twice_in_one_turn(state_dir: Path):
    checks = [
        {"name": "bad step", "command": [sys.executable, "-c", "raise SystemExit(1)"]}
    ]
    event = {"session_id": "abc", "stop_hook_active": True}

    result = run_hook("stop_gate.py", event, marked_state_dir(state_dir), checks)
    output = json.loads(result.stdout)

    assert result.returncode == 0
    assert "decision" not in output
    assert "bad step" in output["systemMessage"]


def test_stop_gate_clears_the_marker_when_every_check_passes(state_dir: Path):
    checks = [{"name": "good step", "command": [sys.executable, "-c", "pass"]}]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert not (state_dir / "abc.changed").exists()


def test_stop_gate_counts_a_missing_program_as_a_failure(state_dir: Path):
    checks = [{"name": "ghost", "command": ["definitely-not-a-program-xyz"]}]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )

    assert json.loads(result.stdout)["decision"] == "block"


@pytest.mark.parametrize(
    "working_directory", [REPO_ROOT, REPO_ROOT / "tests", REPO_ROOT.parent]
)
def test_session_start_prints_the_working_rules(
    working_directory: Path, state_dir: Path
):
    result = run_hook(
        "session_start.py",
        {"cwd": str(working_directory), "source": "compact"},
        state_dir,
    )

    assert result.returncode == 0
    assert "Never run git commands" in result.stdout
    assert "playbook/next_steps/" in result.stdout
    assert "## Invariants" not in result.stdout
    assert len(result.stdout) < 10_000


def test_session_start_is_silent_elsewhere(tmp_path: Path, state_dir: Path):
    result = run_hook(
        "session_start.py", {"cwd": str(tmp_path), "source": "compact"}, state_dir
    )

    assert result.returncode == 0
    assert result.stdout == ""


def our_commands(settings: dict) -> list[str]:
    return [
        hook["command"]
        for groups in settings.get("hooks", {}).values()
        for group in groups
        for hook in group["hooks"]
        if install_claude_hooks.is_ours(hook)
    ]


def test_installer_registers_every_hook_with_absolute_paths():
    settings = install_claude_hooks.install_hooks({}, "/venv/bin/python")
    commands = our_commands(settings)

    assert len(commands) == len(install_claude_hooks.HOOK_DEFINITIONS)
    assert all(command.startswith("/venv/bin/python /") for command in commands)
    assert {event for event in settings["hooks"]} == {
        "SessionStart",
        "PreToolUse",
        "PostToolUse",
        "Stop",
    }
    assert "matcher" not in settings["hooks"]["Stop"][0]
    assert settings["hooks"]["SessionStart"][0]["matcher"] == "compact|resume"


def test_installer_is_idempotent():
    once = install_claude_hooks.install_hooks({}, "/venv/bin/python")
    twice = install_claude_hooks.install_hooks(once, "/venv/bin/python")

    assert twice == once


def test_installer_keeps_hooks_and_settings_that_are_not_ours():
    other_hook = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "echo mine"}],
    }
    settings = {
        "model": "x",
        "hooks": {"PreToolUse": [other_hook], "Notification": [other_hook]},
    }

    installed = install_claude_hooks.install_hooks(settings, "/venv/bin/python")
    removed = install_claude_hooks.remove_hooks(installed)

    assert installed["model"] == "x"
    assert other_hook in installed["hooks"]["PreToolUse"]
    assert removed == settings


def test_installer_remove_drops_the_hooks_key_when_nothing_is_left():
    installed = install_claude_hooks.install_hooks({"model": "x"}, "/venv/bin/python")

    assert install_claude_hooks.remove_hooks(installed) == {"model": "x"}


def test_installer_refuses_to_overwrite_a_broken_settings_file(tmp_path: Path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(SystemExit):
        install_claude_hooks.load_settings(settings_path)

    assert settings_path.read_text(encoding="utf-8") == "{ not json"


def test_installer_treats_a_missing_settings_file_as_empty(tmp_path: Path):
    assert install_claude_hooks.load_settings(tmp_path / "missing.json") == {}
