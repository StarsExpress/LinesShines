# test_config.py

> **Add tests here when:** changing season-threshold routing in `config.py` (`resolve_default_threshold`, `DEFAULT_THRESHOLDS`, `DYNAMIC_THRESHOLDS` and the `NCAAF_` pair).

- **Kind:** pure Python.
- **Needs:** nothing. Tests pass `today=` explicitly, so they do not depend on the real date.
- **Covers:** routing between the static default and the dynamic value for finalized, in-progress and future seasons, for both leagues (the college has its own values: 230 and 360).
- **Not here:** the threshold number box and its clamp in the browser (no test file yet).
- **Known gaps:** routing only. The rule that the threshold is display-only and never read by preprocessing has no test (INVARIANTS 5).
