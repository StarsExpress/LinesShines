"""The sandbox runner in tools/sandbox_tests.py, without a network, the SDK or a sandbox.

Fake sandboxes stand in for Novita's, so every branch of one shard's life and of the report can run.
"""

from __future__ import annotations

import io
import tarfile
from collections import Counter
from pathlib import Path

import pytest

from tools import sandbox_tests


class FakeResult:
    def __init__(self, stdout: str = ""):
        self.stdout = stdout


class FakeCommandFailure(Exception):
    """What the SDK raises for a command that ran and exited non-zero: it carries an exit code."""

    def __init__(self, stdout: str = "", stderr: str = "", exit_code: int = 1):
        super().__init__(f"exit {exit_code}")
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class FakeSandbox:
    def __init__(self, on_pytest=None, fail_on: str = ""):
        self.on_pytest = on_pytest
        self.fail_on = fail_on
        self.commands = self
        self.files = self
        self.killed = False
        self.ran: list[str] = []
        self.uploaded: list[str] = []

    def write(self, path: str, data: bytes) -> None:
        self.uploaded.append(path)

    def run(self, command: str, timeout: int = 0) -> FakeResult:
        self.ran.append(command)

        if self.fail_on and self.fail_on in command:
            raise ConnectionError("the service went away")

        if "pytest" in command and self.on_pytest:
            return self.on_pytest(command)

        return FakeResult("ok")

    def kill(self) -> None:
        self.killed = True


class FakeClient:
    def __init__(self, sandbox: FakeSandbox):
        self.sandbox = self
        self.made = sandbox

    def create(self, template: str, **options) -> FakeSandbox:
        self.template = template
        self.options = options

        return self.made


def test_the_api_key_comes_from_the_environment_first(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_tests, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("NOVITA_API_KEY=from-file\n")
    monkeypatch.setenv("NOVITA_API_KEY", "from-environment")

    assert sandbox_tests.load_api_key() is True
    assert sandbox_tests.os.environ["NOVITA_API_KEY"] == "from-environment"


@pytest.mark.parametrize(
    "line",
    [
        "NOVITA_API_KEY=abc123",
        'NOVITA_API_KEY="abc123"',
        "  NOVITA_API_KEY = 'abc123' ",
    ],
)
def test_the_api_key_falls_back_to_a_dotenv_file_in_the_repo_root(
    line, monkeypatch, tmp_path
):
    monkeypatch.setattr(sandbox_tests, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("NOVITA_API_KEY", raising=False)
    (tmp_path / ".env").write_text(f"OTHER=1\n{line}\n")

    assert sandbox_tests.load_api_key() is True
    assert sandbox_tests.os.environ["NOVITA_API_KEY"] == "abc123"


@pytest.mark.parametrize("content", [None, "OTHER=1\n", "NOVITA_API_KEY=\n"])
def test_no_api_key_anywhere_is_reported_as_missing(content, monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_tests, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("NOVITA_API_KEY", raising=False)

    if content is not None:
        (tmp_path / ".env").write_text(content)

    assert sandbox_tests.load_api_key() is False


def test_the_archive_leaves_out_data_secrets_and_caches(monkeypatch, tmp_path):
    for name in (
        "main.py",
        "frontend/app.js",
        "data/2025/front_7.csv",
        ".env",
        "sandbox/.env",
        "playbook/INVARIANTS.md",
        "tests/__pycache__/x.pyc",
        "seed.db",
        "table.xlsx",
        "node_modules/pkg/index.js",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")

    monkeypatch.setattr(sandbox_tests, "REPO_ROOT", tmp_path)

    with tarfile.open(fileobj=io.BytesIO(sandbox_tests.pack_repo())) as archive:
        names = {name for name in archive.getnames() if not name.endswith("/")}

    assert {"main.py", "frontend/app.js"} <= names
    assert not any(
        name.startswith(("data", "sandbox", "playbook", "node_modules"))
        or name in {".env", "seed.db", "table.xlsx"}
        or "__pycache__" in name
        for name in names
    )


def test_a_shard_that_passes_is_marked_passed_and_its_sandbox_is_killed():
    sandbox = FakeSandbox(on_pytest=lambda command: FakeResult("a\nb\n3 passed in 1s"))
    client = FakeClient(sandbox)

    outcome = sandbox_tests.run_shard(client, b"archive", 1, ["tests/test_a.py"], 3)

    assert outcome.passed is True
    assert outcome.infrastructure_error == ""
    assert outcome.output_tail.endswith("3 passed in 1s")
    assert sandbox.killed is True
    assert any("tests/test_a.py -m browser" in command for command in sandbox.ran)
    assert sandbox.uploaded == [sandbox_tests.REMOTE_ARCHIVE]


def test_the_sandbox_expires_on_its_own_and_is_named_for_the_gate():
    sandbox = FakeSandbox()
    client = FakeClient(sandbox)

    sandbox_tests.run_shard(client, b"archive", 2, ["tests/test_a.py"], 1)

    assert client.options["timeout"] == sandbox_tests.SANDBOX_LIFETIME_SECONDS
    assert client.options["metadata"]["purpose"] == "gate-shard-2"
    assert client.template == sandbox_tests.DEFAULT_TEMPLATE


def test_the_template_can_be_named_in_the_environment(monkeypatch):
    monkeypatch.setenv("NOVITA_TEMPLATE", "my-template:v2")
    client = FakeClient(FakeSandbox())

    sandbox_tests.run_shard(client, b"archive", 1, ["tests/test_a.py"], 1)

    assert client.template == "my-template:v2"


def test_a_failing_test_is_a_failed_shard_not_an_infrastructure_error():
    def failing(command: str):
        raise FakeCommandFailure(
            stdout="FAILED tests/test_a.py::test_x\n1 failed in 2s"
        )

    sandbox = FakeSandbox(on_pytest=failing)

    outcome = sandbox_tests.run_shard(
        FakeClient(sandbox), b"a", 1, ["tests/test_a.py"], 1
    )

    assert outcome.passed is False
    assert outcome.infrastructure_error == ""
    assert "1 failed in 2s" in outcome.output_tail
    assert sandbox.killed is True


def test_a_service_error_is_an_infrastructure_error_and_still_kills_the_sandbox():
    sandbox = FakeSandbox(fail_on="tar xzf")

    outcome = sandbox_tests.run_shard(
        FakeClient(sandbox), b"a", 1, ["tests/test_a.py"], 1
    )

    assert outcome.passed is False
    assert "ConnectionError" in outcome.infrastructure_error
    assert sandbox.killed is True


def test_a_failure_to_create_the_sandbox_is_an_infrastructure_error():
    class Broken:
        sandbox = None

        def create(self, template, **options):
            raise RuntimeError("402: insufficient balance")

    client = Broken()
    client.sandbox = client

    outcome = sandbox_tests.run_shard(client, b"a", 1, ["tests/test_a.py"], 1)

    assert "insufficient balance" in outcome.infrastructure_error


def outcome_with(**fields) -> sandbox_tests.ShardOutcome:
    return sandbox_tests.ShardOutcome(
        number=fields.pop("number", 1), expected_tests=5, **fields
    )


def test_the_report_passes_when_every_shard_passed(capsys):
    code = sandbox_tests.report(
        [outcome_with(passed=True), outcome_with(passed=True, number=2)], 10
    )

    assert code == sandbox_tests.EXIT_PASSED
    assert "every shard passed" in capsys.readouterr().out


def test_the_report_fails_on_a_failed_test_even_when_another_shard_could_not_run(
    capsys,
):
    outcomes = [
        outcome_with(passed=False, output_tail="1 failed"),
        outcome_with(number=2, infrastructure_error="TimeoutError: x"),
    ]

    code = sandbox_tests.report(outcomes, 10)

    assert code == sandbox_tests.EXIT_TESTS_FAILED
    assert "1 failed" in capsys.readouterr().out


def test_the_report_is_unavailable_when_only_the_service_failed(capsys):
    code = sandbox_tests.report(
        [outcome_with(infrastructure_error="ConnectionError: x")], 10
    )

    assert code == sandbox_tests.EXIT_UNAVAILABLE
    assert "UNAVAILABLE" in capsys.readouterr().out


def test_main_is_unavailable_without_an_api_key_and_never_prints_one(
    monkeypatch, capsys
):
    monkeypatch.setattr(sandbox_tests, "load_api_key", lambda: False)

    code = sandbox_tests.main([])

    assert code == sandbox_tests.EXIT_UNAVAILABLE
    assert "NOVITA_API_KEY" in capsys.readouterr().out


def test_main_is_unavailable_when_the_sdk_is_not_installed(monkeypatch, capsys):
    monkeypatch.setattr(sandbox_tests, "load_api_key", lambda: True)
    monkeypatch.setitem(sandbox_tests.sys.modules, "novita_sandbox", None)

    code = sandbox_tests.main([])

    assert code == sandbox_tests.EXIT_UNAVAILABLE
    assert "requirements-sandbox.txt" in capsys.readouterr().out


def test_main_fails_when_the_browser_tests_cannot_be_collected(monkeypatch, capsys):
    class FakeNovita:
        pass

    monkeypatch.setattr(sandbox_tests, "connect", lambda: FakeNovita())

    def broken_collection() -> Counter:
        raise RuntimeError("pytest could not collect the browser tests")

    monkeypatch.setattr(sandbox_tests, "count_browser_tests", broken_collection)

    code = sandbox_tests.main([])

    assert code == sandbox_tests.EXIT_TESTS_FAILED
    assert "could not collect" in capsys.readouterr().out
