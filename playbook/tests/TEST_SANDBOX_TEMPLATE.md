# test_sandbox_template.py

> **Add tests here when:** changing `tools/sandbox_template.py` (the template's layers, its tags and size, the build call, its exit codes).

- **Kind:** pure Python. A fake client records what would be sent to Novita; no network and no key are needed. One test renders the template to a Dockerfile with the SDK and is skipped when `novita-sandbox` is not installed (CI does not install it).
- **Needs:** nothing.
- **Covers:** the template's Python version equals the one in the CI jobs (`ci.yml`); the runner's default template is the one this module builds; the tags are the date and `latest`; the requirement files it copies exist; the rendered Dockerfile (Python 3.12 base, Chromium installed as root with `PLAYWRIGHT_BROWSERS_PATH` set, the requirements after Chromium, back to `user`); `main()` sends the name, tags, 2 vCPU, 4096 MB and the cache setting, can name another template, reports a failed build as exit code 1 with the reason, and a missing key as exit code 3.
- **Not here:** that Novita really builds the image and the template starts (only a real build shows that: `python -m tools.sandbox_template`, then `python -m tools.sandbox_tests`); the key lookup itself (`TEST_SANDBOX_TESTS.md`).
- **Known gaps:** the Dockerfile test needs the SDK, so it does not run in CI.
