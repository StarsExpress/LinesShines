# test_playbook_docs.py

> **Add tests here when:** changing how test scripts and their documents in `playbook/tests/` must match: the naming rule, what counts as a document, or the opening line every document needs.

- **Kind:** pure Python. It only reads files, so it needs no browser and no fixtures, and it runs in CI like any other test.
- **Needs:** the repository layout: `tests/` beside `playbook/tests/`. The documents are tracked in git (the `!playbook/tests/` line in `.gitignore`), so CI sees them.
- **Covers:** every `tests/test_*.py` and `conftest.py` has a document named after it (upper-case stem plus `.md`, so `test_pinned_impact.py` needs `TEST_PINNED_IMPACT.md` and `conftest.py` needs `CONFTEST.md`); every document in `playbook/tests/` except `INDEX.md` matches a script, so there are no orphans; every document is linked from `INDEX.md` as `(NAME.md)`, the form its routing table uses; every link in `INDEX.md` points at a file that exists (web addresses and `#` anchors are skipped, and an anchor after a file name is ignored); the third line of every document contains "Add tests here when:".
- **Not here:** what a document says about its script. Only that it exists, is listed and opens correctly is checked.
- **Known gaps:** a row that links the right file next to the wrong description is not caught; that needs a person. Only `INDEX.md` is checked for links, not the other documents.
