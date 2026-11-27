# Browser tests in Novita sandboxes

> **Load when:** changing `tools/sandbox_tests.py`, `tools/sandbox_template.py` or `requirements-sandbox.txt`, the sandbox check in the Stop gate, or asking how many shards, which template, or why not snapshots. The gate's side (which writes trigger it, the exit codes) is in `CLAUDE-HOOKS.md`.

The full browser suite (321 tests, about ten minutes in one process) used to be the owner's local run. The Stop gate now runs it in parallel in [Novita Agent Sandboxes](https://novita.ai/docs/guides/sandbox-overview), about two and a half minutes in all, whenever a browser-relevant file was written in the session. Nothing here adds a dependency to the product: the SDK is in `requirements-sandbox.txt` and is imported only by `tools/`.

## Parts

- **Runner:** `python -m tools.sandbox_tests [--shards N]` (default 5). It counts the browser tests locally with pytest's collection (no browser starts), deals the test files into shards of about equal test count (largest file first, each to the lightest shard), and starts one sandbox per shard from the template. Each sandbox gets the repo as one archive (without `data/`, `playbook/`, `.git`, `node_modules`, `sandbox/`, `.env`, caches, `.db`, `.xlsx`, `.csv`), runs `pip install -r` to catch up with the requirements, runs its files with `-m browser`, and is killed at the end; it also expires by itself after 15 minutes. Exit code 0 passed, 1 a test (or the collection) failed, 3 could not run (no key, no SDK, no network, no balance, no template, a service error).
- **Template `lines-shines-browser`:** built by `python -m tools.sandbox_template` (`--no-cache` ignores the layer cache). `from_python_image("3.12")` (CI uses 3.12; the service's `base` image ran 3.11), root for the Playwright layer, `PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright` (also set at run time), `pip install playwright`, `playwright install --with-deps chromium`, the two requirements files copied and installed, then back to `user`; 2 vCPU, 4096 MB; tagged with the build date and `latest`. Start it as `lines-shines-browser:latest`: the bare name returned `404: template '<id>' not found` while the list kept showing `build_status='waiting'` and `get_build_status` said `READY`; the cause is unknown.
- **When to rebuild:** when Playwright's version changes. The Chromium in the template has to match it, and its folder is read-only for the sandbox user, so nothing can install a newer one at run time. A change in `requirements*.txt` needs no rebuild: the in-sandbox `pip install` takes seconds when the template is current and installs only what changed, so there is no version check to maintain.
- **Key:** `NOVITA_API_KEY` in the environment, else a `.env` in the repo root (git-ignored). The account needs a balance; with only the free quota, creating a sandbox returned `402: insufficient balance`. The key never goes into the repo, a hook, a log or `playbook/`.
- **Throwaway checks** live in the git-ignored `sandbox/` (outside the style check): `chromium_check.py`, `run_browser_tests.py` (one sandbox; the way to run a single test file, `python sandbox/run_browser_tests.py tests/test_x.py`), `check_template.py` (after a rebuild: Python version, packages, Chromium starts), `template_status.py`, `delete_template.py`.
- **Tests:** `tests/test_sandbox_tests.py` and `tests/test_sandbox_template.py` (fake sandboxes, no network), `tests/test_hooks.py` (how the gate reacts).

## Measurements (2026-11-27, region `us-phx-1`, five sandboxes at once)

| Run | Time |
|---|---|
| One sandbox from `base`, full suite (321 passed) | 491 s of tests, about 537 s in all, of which about 45 s was setup |
| One sandbox from the template | setup about 11 s; tests 577 s (one run: host variation, or a smaller machine than `base`; not checked) |
| Three shards, with a snapshot | 230 s parallel part, 254 s whole script |
| Five shards, with a snapshot | 136 s parallel part, 169 s whole script (33 s of that making the snapshot) |
| Five shards from the template, repo uploaded to each | 147 s parallel part, 166 s whole script |
| `python -m tools.sandbox_tests` (five shards, counting done locally) | 141 s whole |

Shard times run from about 100 s to 135 s; the slowest decides the total, about a fifth above an even split. The shard times add up to the single-sandbox time, so sharding costs nothing. A full single-sandbox browser run cost about one US cent. Snapshots: taking one 3.1 s, starting from it 0.7 s; its files and a background process survive.

## Decisions

- **The template is the base,** with the in-sandbox `pip install` as a catch-up.
- **No snapshots in this check.** Same time as starting from the template (166 s against 169 s), and the SDK makes them awkward: `list_snapshots()` returns ids only (no name, time or metadata) and `create_snapshot()` takes no name, so finding the right one would need a local key-to-id file, plus expiry and stale files to manage. Snapshots stay for agent loops (a checkpoint before a risky fix, several attempts from one failing state), which is separate work.
- **No reuse of paused sandboxes.** A snapshot does not run out of life; the events API carries no timeout or end time; whether a pause stops the lifetime clock is undocumented; and files and processes survive a pause, so old state can leak into a run.
- **Five shards, dealt by test count.** Five is what the quota allowed when measured. Dealing by recorded run time would narrow the spread but needs saved state.
- **A check that could not run is a warning; a failing test blocks.** An SDK exception that carries `exit_code` (`CommandExitException`) means the command ran and failed; any other exception (timeout, network, service) means the service could not be used. Checked in a real sandbox with a test file that does not exist.
- **Not in this check:** touch, pinch-zoom, standalone mode and a real phone (`INVARIANTS.md`: say what could not be verified); they were never the browser tests' job.
- **Not done:** Claude Code itself inside a sandbox (the one-hour cap cuts long sessions off); a code sandbox for the in-site Agent operator (it needs no code execution); PFF raw data in a sandbox (licensed data on a third-party service is a separate question, and `data/` is never packed).

## What the SDK gives (2.1.x, `novita-sandbox`)

- `Novita().sandbox.create(template, timeout=..., metadata=...)`; the default life is 5 minutes, so a run needs `timeout=`. At expiry a sandbox is killed unless it is set to pause. Kill is final.
- `sandbox.files.write(path, bytes)`, `sandbox.commands.run(command, timeout=...)` (foreground; there is no working-directory option, so `cd repo && ...` goes in the command; a non-zero exit raises `CommandExitException` with `exit_code`, `stdout`, `stderr`).
- Outbound internet is on by default; the browser tests, including `test_external_requests.py`, pass with it on.
- Templates: the `Template(...)` builder (`from_python_image`, `run_cmd`, `copy`, `set_envs`, `set_user`) and `novita.template.build(...)`; layers are cached; tags with `tags=[...]`; `template.list`, `get_tags`, `get_build_status` (returns only the first part of the build log), `delete` (permanent).
- Snapshots (v2 regions only): `sandbox.create_snapshot()` pauses while it captures; `novita.sandbox.create(snapshot_id)` starts from it; `list_snapshots()` and `delete_snapshot(id)` exist. Never snapshot a sandbox that holds a secret.
- Storage (templates, snapshots, paused sandboxes) is billed above a free allowance; a sandbox is billed per second.

## Sources

- https://novita.ai/docs/guides/sandbox-overview.md
- https://docs.novita.ai/guides/sandbox-create
- https://docs.novita.ai/guides/sandbox-pause-resume
- https://docs.novita.ai/guides/sandbox-timeout-handle
- https://docs.novita.ai/guides/sandbox-run-command
- https://docs.novita.ai/guides/sandbox-internet-access
- https://docs.novita.ai/guides/sandbox-events
- https://docs.novita.ai/guides/sandbox-template-build-operations
- https://docs.novita.ai/guides/sandbox-template-tags
- https://docs.novita.ai/guides/sandbox-template-caching
- https://docs.novita.ai/guides/sandbox-snapshot-create
- https://docs.novita.ai/guides/sandbox-snapshot-sandbox-use
- https://docs.novita.ai/guides/sandbox-pricing
