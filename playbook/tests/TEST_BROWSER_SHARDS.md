# test_browser_shards.py

> **Add tests here when:** changing `tools/browser_shards.py` (how browser test files are counted and dealt into shards, the `--index` output, its exit codes), which both the sandbox runner and the CI `browser` matrix use.

- **Kind:** pure Python. The collection is replaced by fixed counts; one test runs pytest's real collection (`-m browser --collect-only`) in a subprocess, which starts no browser.
- **Needs:** nothing.
- **Covers:** the per-file counts parsed from the collection output; dealing (balanced totals, no file lost or repeated, the same result every time, empty shards dropped); that the indexes `1..N` together print every file exactly once (what the CI matrix relies on); one index prints one line; an index outside the shards is exit code 2 with no files printed (so a CI job cannot silently run the whole suite); the listing without an index; a collection failure is exit code 1 with the reason; the real collection finds more than 100 browser tests and deals every file.
- **Not here:** the CI workflow itself (`.github/workflows/ci.yml`; only a pull request shows that the five jobs together pass), and the sandboxes (`TEST_SANDBOX_TESTS.md`).
- **Known gaps:** shard sizes are balanced by test count, not by run time, so job times differ.
