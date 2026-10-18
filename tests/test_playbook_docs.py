"""Every test script has a document in playbook/tests/, and every document has a script.

Every document must also be linked from INDEX.md, the routing table, and every link in
INDEX.md must point at a file that exists.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
DOCS_DIR = ROOT / "playbook" / "tests"

# Third line of each document is what `grep -H "Add tests here when" ...` scans.
TRIGGER = "Add tests here when:"

# Target of a Markdown link: the part in parentheses right after `]`.
LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")
# A web address or any other scheme (https:, mailto:), which is not a file to look for.
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _expected_doc_name(script: Path) -> str:
    """tests/test_pinned_impact.py -> TEST_PINNED_IMPACT.md, conftest.py -> CONFTEST.md."""
    return f"{script.stem.upper()}.md"


def _scripts() -> list[Path]:
    return sorted([*TESTS_DIR.glob("test_*.py"), TESTS_DIR / "conftest.py"])


def _docs() -> list[Path]:
    """Every document in playbook/tests/ except the INDEX, which is not about one script."""
    assert DOCS_DIR.is_dir(), "playbook/tests/ is missing"

    return sorted(p for p in DOCS_DIR.glob("*.md") if p.name != "INDEX.md")


def _index() -> str:
    path = DOCS_DIR / "INDEX.md"
    assert path.is_file(), "playbook/tests/INDEX.md is missing"

    return path.read_text(encoding="utf-8")


def test_every_test_script_has_a_document():
    present = {doc.name for doc in _docs()}
    missing = [
        f"{script.name} -> playbook/tests/{_expected_doc_name(script)}"
        for script in _scripts()
        if _expected_doc_name(script) not in present
    ]

    assert not missing, (
        "These test scripts have no document in playbook/tests/ "
        "(copy the shape of an existing one, and add it to INDEX.md):\n  "
        + "\n  ".join(missing)
    )


def test_every_document_has_a_test_script():
    expected = {_expected_doc_name(script) for script in _scripts()}
    orphans = [doc.name for doc in _docs() if doc.name not in expected]

    assert not orphans, (
        "These documents in playbook/tests/ match no test script "
        "(delete them, or fix the name: upper-case stem of the script + .md):\n  "
        + "\n  ".join(orphans)
    )


def test_every_document_is_listed_in_the_index():
    index = _index()
    unlisted = [doc.name for doc in _docs() if f"({doc.name})" not in index]

    assert not unlisted, (
        "INDEX.md has no link to these documents "
        "(add a row to its routing table, linking them as (NAME.md)):\n  "
        + "\n  ".join(unlisted)
    )


def test_every_link_in_the_index_points_at_a_file_that_exists():
    dead = []
    for target in LINK_TARGET.findall(_index()):
        if SCHEME.match(target) or target.startswith("#"):
            continue  # A web address or an anchor within the page.

        path = target.split("#", 1)[0]  # Drop an anchor such as TEST_PATHS.md#covers.
        if not (DOCS_DIR / path).exists():
            dead.append(target)

    assert not dead, (
        "INDEX.md links to files that do not exist "
        "(fix the name, or delete the row):\n  " + "\n  ".join(dead)
    )


def test_every_document_opens_with_its_trigger_line():
    wrong = []
    for doc in _docs():
        lines = doc.read_text(encoding="utf-8").splitlines()
        if len(lines) < 3 or TRIGGER not in lines[2]:
            wrong.append(doc.name)

    assert (
        not wrong
    ), f'The third line of these documents must hold "{TRIGGER}":\n  ' + "\n  ".join(
        wrong
    )
