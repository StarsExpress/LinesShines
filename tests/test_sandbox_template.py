"""The template builder in tools/sandbox_template.py, without a network or a key.

A fake client records what would be sent to Novita. The template definition itself is rendered to a Dockerfile
by the SDK when the SDK is installed, and that test is skipped when it is not.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from tools import sandbox_template, sandbox_tests

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeTemplateApi:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple] = []

    def build(self, template, name, **options):
        self.calls.append((template, name, options))

        if self.error:
            raise self.error

        return type(
            "Info",
            (),
            {
                "template_id": "tid",
                "build_id": "bid",
                "name": name,
                "tags": options["tags"],
            },
        )()


class FakeClient:
    def __init__(self, error: Exception | None = None):
        self.template = FakeTemplateApi(error)


def test_the_template_uses_the_python_of_the_ci_jobs():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    versions = set(re.findall(r'python-version:\s*"?([0-9.]+)"?', workflow))

    assert versions == {sandbox_template.PYTHON_VERSION}


def test_the_runner_starts_the_template_this_module_builds():
    assert sandbox_tests.DEFAULT_TEMPLATE == f"{sandbox_template.TEMPLATE_NAME}:latest"


def test_every_build_gets_the_date_and_latest():
    assert sandbox_template.build_tags(date(2026, 11, 27)) == ["2026-11-27", "latest"]


def test_the_requirement_files_the_template_copies_exist():
    for name in sandbox_template.REQUIREMENT_FILES:
        assert (REPO_ROOT / name).is_file()


def test_the_dockerfile_installs_chromium_as_root_and_the_requirements_after_it():
    template_class = pytest.importorskip("novita_sandbox").Template
    lines = template_class.to_dockerfile(
        sandbox_template.browser_template()
    ).splitlines()
    chromium = next(
        n
        for n, line in enumerate(lines)
        if "playwright install --with-deps chromium" in line
    )
    requirements = next(
        n for n, line in enumerate(lines) if "pip install" in line and "-r " in line
    )

    assert lines[0] == "FROM python:3.12"
    assert lines.index("USER root") < chromium < requirements
    assert "ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright" in lines
    assert lines[-1] == "USER user"
    assert "COPY requirements-dev.txt /opt/lines-shines/" in lines


def test_main_builds_with_the_tags_the_size_and_the_cache_setting(monkeypatch, capsys):
    client = FakeClient()
    monkeypatch.setattr(sandbox_template, "connect", lambda: client)
    monkeypatch.setattr(sandbox_template, "browser_template", lambda: "the template")

    code = sandbox_template.main(["--no-cache"])
    template, name, options = client.template.calls[0]

    assert code == sandbox_tests.EXIT_PASSED
    assert (template, name) == ("the template", "lines-shines-browser")
    assert options["tags"] == sandbox_template.build_tags(date.today())
    assert (options["cpu_count"], options["memory_mb"]) == (2, 4096)
    assert options["skip_cache"] is True
    assert "start it as lines-shines-browser:latest" in capsys.readouterr().out


def test_main_can_name_another_template(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(sandbox_template, "connect", lambda: client)
    monkeypatch.setattr(sandbox_template, "browser_template", lambda: "t")

    sandbox_template.main(["--name", "other"])

    assert client.template.calls[0][1] == "other"
    assert client.template.calls[0][2]["skip_cache"] is False


def test_a_failed_build_is_exit_code_1_and_says_why(monkeypatch, capsys):
    monkeypatch.setattr(
        sandbox_template, "connect", lambda: FakeClient(RuntimeError("layer 3 failed"))
    )
    monkeypatch.setattr(sandbox_template, "browser_template", lambda: "t")

    code = sandbox_template.main([])

    assert code == sandbox_tests.EXIT_TESTS_FAILED
    assert "layer 3 failed" in capsys.readouterr().out


def test_no_key_or_no_sdk_is_exit_code_3(monkeypatch, capsys):
    monkeypatch.setattr(sandbox_tests, "load_api_key", lambda: False)

    code = sandbox_template.main([])

    assert code == sandbox_tests.EXIT_UNAVAILABLE
    assert "NOVITA_API_KEY" in capsys.readouterr().out
