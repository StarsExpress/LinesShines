# tests/js/ (the browser-free invariant tests)

> **Add tests here when:** a rule in INVARIANTS 1, 2, 3, 9 or 17 changes, or a regression in one of them is only found by a browser test. These run in seconds and in the Stop gate, which runs the browser tests only in a sandbox and only when a browser-relevant file changed. Run them with `npm run test:js`.

- **Kind:** Node's built-in runner (`node --test`), no install and no browser. `tests/js/run.mjs` lists the `*.test.mjs` files and starts the runner on them by name (Node 20 in CI and Node 22 locally treat directory and glob arguments differently). One file is one process, so each file picks the Season or the Career page once.
- **Needs:** Node 20 or newer. `support/browser_stub.mjs` installs a just-enough `document`, `window`, `localStorage` and a recording `Plotly` before the app modules are imported (`dom.js` looks up its elements while it loads). `pinned_impact.test.mjs` needs no stub: `pinned-impact.js` is pure.
- **Covers:**
  - `percentiles.test.mjs`, `percentiles_career.test.mjs` (1, 2): the pool is the exact position above the threshold, inclusive; the percentile does not depend on the selected position; ties share a rank (competition ranking); on Career one pool, each member in by the bar of his own status, and a lit or off status never changes the pool.
  - `highlight_union.test.mjs`, `highlight_union_career.test.mjs` (3): run the real `render()` and read what it hands to `Plotly.react`. Teams and Players join by OR; Teams only highlights; no team and no player dims everyone alike; the threshold is a hard gate; on Career the Status Filter joins the union, an off status lights nobody and none of them changes who is plotted.
  - `pinned_impact.test.mjs` (9, 17): reset, partial, refresh and unaffected outcomes, Comparison Cards shrinking, dissolving and de-duplicating, the Career bars, and the one eligibility function (`partitionByEligibility()`) the Players filter shares with Pinned Players.
- **Not here:** the wiring (Apply, drag and release, toasts, the confirm dialog) → `TEST_PINNED_IMPACT.md`, `TEST_FILTERS.md` and `TEST_BROWSER_SMOKE.md`. The browser tests stay; these are their fast twins for the rules.
- **Known gaps:** the stub is permissive, so a change that only breaks real DOM behaviour is not seen here. ESLint and Prettier cover `tests/js/` too (`lint:js`, `format:js:check`).
