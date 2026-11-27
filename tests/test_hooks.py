"""The Claude Code hooks in tools/claude_hooks/ and the installer that registers them.

Each hook is run the way Claude Code runs it: a subprocess that reads one JSON event on stdin.
No test runs black, Prettier, ESLint or the real CI set; the gate's checks are replaced through
the environment variable the gate offers for this.
"""

from __future__ import annotations

import importlib.util
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
CLEAN_ROOT_ENV_VAR = "LINES_SHINES_HOOK_CLEAN_ROOT"
PKILL_COMMAND = 'pkill -f "uvicorn main:app *"'


def run_hook(
    script_name: str,
    event: dict,
    state_dir: Path,
    checks: list[dict] | None = None,
    clean_root: Path | None = None,
):
    """Run one hook script with the event on stdin; returns the finished process.

    The Stop gate's cleanup is pointed at a folder that does not exist unless a test names one,
    so no test run deletes the cache files of the real repo.
    """
    environment = {
        "PATH": "/usr/bin:/bin",
        STATE_DIR_ENV_VAR: str(state_dir),
        CLEAN_ROOT_ENV_VAR: str(clean_root or state_dir.parent / "nothing_to_clean"),
    }

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


def test_post_write_hook_notes_each_written_path_in_the_marker(state_dir: Path):
    for name in ("frontend/render.js", "playbook/COMMANDS.md"):
        event = {**write_event(str(REPO_ROOT / name)), "session_id": "abc"}
        run_hook("post_write.py", event, state_dir)

    marker_text = (state_dir / "abc.changed").read_text()

    assert marker_text.splitlines() == ["frontend/render.js", "playbook/COMMANDS.md"]


def test_post_write_hook_ignores_a_file_outside_the_repo(
    tmp_path: Path, state_dir: Path
):
    event = {**write_event(str(tmp_path / "notes.py"), tmp_path), "session_id": "abc"}

    result = run_hook("post_write.py", event, state_dir)

    assert result.returncode == 0
    assert not (state_dir / "abc.changed").exists()


def load_post_write_module(monkeypatch: pytest.MonkeyPatch):
    """The post-write hook, loaded by path; it imports `hook_common` from its own folder."""
    monkeypatch.syspath_prepend(str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        "post_write", HOOKS_DIR / "post_write.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_post_write_style_check_reports_a_new_violation_and_names_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    post_write = load_post_write_module(monkeypatch)
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("VALUE = 1\n", encoding="utf-8")

    failures = post_write.style_failures(
        bad_file, root=tmp_path, baseline_path=tmp_path / "none.json"
    )

    assert len(failures) == 1
    assert "bad.py" in failures[0]
    assert "module-docstring" in failures[0]
    assert "do not add them to tools/code_style_baseline.json" in failures[0]


def test_post_write_style_check_is_silent_for_a_clean_file_and_for_a_baselined_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from tools import check_code_style

    post_write = load_post_write_module(monkeypatch)
    clean_file = tmp_path / "clean.py"
    clean_file.write_text('"""Clean."""\n\nVALUE = 1\n', encoding="utf-8")
    old_file = tmp_path / "old.py"
    old_file.write_text("VALUE = 1\n", encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"
    check_code_style.write_baseline(
        check_code_style.check_files([old_file], root=tmp_path), baseline_path
    )

    assert post_write.style_failures(clean_file, tmp_path, baseline_path) == []
    assert post_write.style_failures(old_file, tmp_path, baseline_path) == []


def test_post_write_style_check_leaves_node_modules_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    post_write = load_post_write_module(monkeypatch)
    vendored_file = tmp_path / "node_modules" / "package" / "tool.py"
    vendored_file.parent.mkdir(parents=True)
    vendored_file.write_text("VALUE = 1\n", encoding="utf-8")

    assert post_write.style_failures(vendored_file, tmp_path, tmp_path / "x.json") == []


def test_post_write_runs_the_style_check_only_after_black_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    post_write = load_post_write_module(monkeypatch)
    python_file = tmp_path / "module.py"
    style_calls: list[Path] = []

    def fake_style_failures(file_path: Path) -> list[str]:
        style_calls.append(file_path)

        return ["style says no"]

    monkeypatch.setattr(post_write, "style_failures", fake_style_failures)

    monkeypatch.setattr(post_write, "run_tool", lambda command: (True, ""))
    assert post_write.format_file(python_file) == ["style says no"]

    monkeypatch.setattr(post_write, "run_tool", lambda command: (False, "boom"))
    failures = post_write.format_file(python_file)

    assert len(failures) == 1
    assert "black -S failed" in failures[0]
    assert style_calls == [python_file]


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


def load_stop_gate_module(monkeypatch: pytest.MonkeyPatch):
    """The Stop gate, loaded by path; it imports `hook_common` and `cache_files` from its own folder."""
    monkeypatch.syspath_prepend(str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        "stop_gate", HOOKS_DIR / "stop_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


@pytest.mark.parametrize(
    "relative_path, relevant",
    [
        ("frontend/render.js", True),
        ("frontend/vendor/html2canvas.min.js", True),
        ("main.py", True),
        ("database/db_models.py", True),
        ("config/metrics.py", True),
        ("teams/nfl.py", True),
        ("tests/test_browser_smoke.py", True),
        ("tests/conftest.py", True),
        ("requirements-dev.txt", True),
        ("pytest.ini", True),
        ("tools/sandbox_tests.py", True),
        ("tests/js/percentiles.test.mjs", False),
        ("playbook/INVARIANTS.md", False),
        ("preprocessing/front_7.py", False),
        ("tools/check_code_style.py", False),
        ("README.md", False),
        ("mainly.py", False),
    ],
)
def test_stop_gate_runs_the_sandbox_check_only_for_browser_relevant_paths(
    relative_path: str, relevant: bool, monkeypatch: pytest.MonkeyPatch
):
    stop_gate = load_stop_gate_module(monkeypatch)

    assert stop_gate.is_browser_relevant(relative_path) is relevant


def test_stop_gate_adds_the_sandbox_check_last_and_only_when_asked(
    monkeypatch: pytest.MonkeyPatch,
):
    stop_gate = load_stop_gate_module(monkeypatch)
    monkeypatch.delenv(CHECKS_ENV_VAR, raising=False)

    without_sandbox = stop_gate.build_checks(False)
    with_sandbox = stop_gate.build_checks(True)

    assert len(without_sandbox) == 5
    assert with_sandbox[:5] == without_sandbox
    assert with_sandbox[5]["command"][1:] == ["-m", "tools.sandbox_tests"]
    assert with_sandbox[5]["unavailable_exit_code"] == 3


def sandbox_like_check(exit_code: int, text: str) -> dict:
    """A stand-in for the sandbox check: prints something and ends with the exit code, flagged as the real one is."""
    return {
        "name": "sandbox step",
        "command": [
            sys.executable,
            "-c",
            f"print({text!r}); raise SystemExit({exit_code})",
        ],
        "unavailable_exit_code": 3,
    }


def test_stop_gate_only_warns_when_the_sandbox_check_could_not_run(state_dir: Path):
    checks = [
        {"name": "good step", "command": [sys.executable, "-c", "pass"]},
        sandbox_like_check(3, "RESULT: UNAVAILABLE: no NOVITA_API_KEY"),
    ]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )
    output = json.loads(result.stdout)

    assert result.returncode == 0
    assert "decision" not in output
    assert "[sandbox step] could not run" in output["systemMessage"]
    assert "no NOVITA_API_KEY" in output["systemMessage"]
    assert not (state_dir / "abc.changed").exists()


def test_stop_gate_blocks_on_a_failing_sandbox_test(state_dir: Path):
    checks = [sandbox_like_check(1, "RESULT: browser tests FAILED in the sandbox.")]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )
    decision = json.loads(result.stdout)

    assert decision["decision"] == "block"
    assert "FAILED in the sandbox" in decision["reason"]
    assert (state_dir / "abc.changed").exists()


def test_stop_gate_exit_code_3_is_a_failure_for_a_check_that_does_not_use_it(
    state_dir: Path,
):
    checks = [
        {"name": "plain step", "command": [sys.executable, "-c", "raise SystemExit(3)"]}
    ]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )

    assert json.loads(result.stdout)["decision"] == "block"


def test_stop_gate_says_what_it_skipped_when_a_check_failed_and_another_could_not_run(
    state_dir: Path,
):
    checks = [
        {"name": "bad step", "command": [sys.executable, "-c", "raise SystemExit(1)"]},
        sandbox_like_check(3, "RESULT: UNAVAILABLE: no balance"),
    ]

    result = run_hook(
        "stop_gate.py", {"session_id": "abc"}, marked_state_dir(state_dir), checks
    )
    reason = json.loads(result.stdout)["reason"]

    assert "[bad step]" in reason
    assert "WARNING: [sandbox step] could not run" in reason


def test_the_marker_lists_what_was_written_and_a_bare_marker_lists_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.syspath_prepend(str(HOOKS_DIR))
    hook_common = importlib.import_module("hook_common")
    marker = tmp_path / "state" / "abc.changed"

    assert hook_common.read_written_paths(marker) == []

    hook_common.record_written_path(marker, REPO_ROOT / "main.py")
    hook_common.record_written_path(marker, REPO_ROOT / "frontend" / "render.js")

    assert hook_common.read_written_paths(marker) == ["main.py", "frontend/render.js"]

    marker.write_text("")

    assert hook_common.read_written_paths(marker) == []


def load_cache_files_module():
    """The cache cleanup module, loaded by path: tools/claude_hooks/ is a script folder, not a package."""
    spec = importlib.util.spec_from_file_location(
        "cache_files", HOOKS_DIR / "cache_files.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def make_messy_tree(root: Path) -> None:
    """A tree with every kind of cache file, one each at the top and nested, and files that must stay."""
    for folder in ("pkg/__pycache__", "__MACOSX", "deep/er/__pycache__"):
        (root / folder).mkdir(parents=True)
        (root / folder / "inside.pyc").write_text("x")

    (root / ".DS_Store").write_text("x")
    (root / "deep" / ".DS_Store").write_text("x")
    (root / "main.py").write_text("keep")
    (root / "pkg" / "module.py").write_text("keep")
    (root / "node_modules" / "left").mkdir(parents=True)
    (root / "node_modules" / "left" / ".DS_Store").write_text("left alone")
    (root / ".git").mkdir()
    (root / ".git" / ".DS_Store").write_text("left alone")


def test_cache_cleanup_removes_pycache_macosx_and_ds_store_everywhere(tmp_path: Path):
    make_messy_tree(tmp_path)

    removed_count = load_cache_files_module().remove_cache_files(tmp_path)

    assert removed_count == 5
    assert not list(tmp_path.rglob("__pycache__"))
    assert not (tmp_path / "__MACOSX").exists()
    assert not (tmp_path / ".DS_Store").exists()
    assert not (tmp_path / "deep" / ".DS_Store").exists()


def test_cache_cleanup_keeps_real_files_and_skips_node_modules_and_git(tmp_path: Path):
    make_messy_tree(tmp_path)

    load_cache_files_module().remove_cache_files(tmp_path)

    assert (tmp_path / "main.py").read_text() == "keep"
    assert (tmp_path / "pkg" / "module.py").read_text() == "keep"
    assert (tmp_path / "node_modules" / "left" / ".DS_Store").exists()
    assert (tmp_path / ".git" / ".DS_Store").exists()


def test_cache_cleanup_of_a_missing_folder_is_a_quiet_zero(tmp_path: Path):
    assert load_cache_files_module().remove_cache_files(tmp_path / "nowhere") == 0


@pytest.mark.parametrize("check_passes", [True, False])
def test_stop_gate_cleans_the_cache_files_whether_the_checks_pass_or_fail(
    check_passes: bool, tmp_path: Path, state_dir: Path
):
    make_messy_tree(tmp_path / "repo")
    exit_code = 0 if check_passes else 1
    checks = [
        {
            "name": "step",
            "command": [sys.executable, "-c", f"raise SystemExit({exit_code})"],
        }
    ]

    run_hook(
        "stop_gate.py",
        {"session_id": "abc"},
        marked_state_dir(state_dir),
        checks,
        clean_root=tmp_path / "repo",
    )

    assert not list((tmp_path / "repo").rglob("__pycache__"))
    assert not (tmp_path / "repo" / ".DS_Store").exists()
    assert (tmp_path / "repo" / "main.py").exists()


def test_stop_gate_leaves_the_cache_files_when_the_repo_did_not_change(
    tmp_path: Path, state_dir: Path
):
    make_messy_tree(tmp_path / "repo")

    run_hook(
        "stop_gate.py",
        {"session_id": "abc"},
        state_dir,
        [],
        clean_root=tmp_path / "repo",
    )

    assert (tmp_path / "repo" / ".DS_Store").exists()


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
