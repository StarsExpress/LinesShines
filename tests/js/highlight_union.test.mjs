// INVARIANT #3 on a Season page: Teams and Players join by union (OR), Teams only highlights, the threshold gates.
// Drives the real `render()` against a recording `Plotly`, so what it asserts is what the chart is handed.
// The browser-free twin of tests/test_filters.py, run by `npm run test:js`.

import assert from "node:assert/strict";
import { test } from "node:test";

import { categoryMetadata, installBrowser } from "./support/browser_stub.mjs";

installBrowser();

const data = await import("../../frontend/data.js");
const { render } = await import("../../frontend/render.js");
const { DIM_OPACITY } = await import("../../frontend/config.js");

// (player, team, opportunities). "E. Low" is under the threshold of 100 on a team that is chosen.
const ROWS = [
  ["A. Buf", "BUF", 300],
  ["B. Buf", "BUF", 300],
  ["C. Mia", "MIA", 300],
  ["D. Mia", "MIA", 300],
  ["E. Low", "BUF", 50],
];

// What render() drew: each plotted player, and whether he was dimmed.
function drawn({ teams = "", players = "", threshold = "100" }) {
  data.setMetadata({ pass_rush: categoryMetadata(), teams: {} });
  data.setCurrentSlice(
    ROWS.map(([player, team, opportunities], i) => ({
      player,
      abbr_name: player,
      team,
      position: "ED",
      "PR Opp": opportunities,
      x_metric: 10 + i,
      y_metric: 20 + 2 * i,
    })),
    "pass_rush"
  );
  data.setAppliedFilters({
    category: "pass_rush",
    season: "2025",
    position: "ED",
    xMetric: "x_metric",
    yMetric: "y_metric",
    threshold,
    teams,
    players,
  });
  globalThis.Plotly.reactCalls.length = 0;
  render();

  const [, [trace]] = globalThis.Plotly.reactCalls.at(-1);

  return Object.fromEntries(trace.text.map((name, i) => [name, trace.marker.opacity[i] === DIM_OPACITY.marker]));
}

test("a chosen team lights its players and dims everyone else", () => {
  assert.deepEqual(drawn({ teams: "BUF" }), { "A. Buf": false, "B. Buf": false, "C. Mia": true, "D. Mia": true });
});

test("Teams only highlights: choosing a team never changes who is plotted", () => {
  const everyone = Object.keys(drawn({ teams: "" })).sort();

  assert.deepEqual(Object.keys(drawn({ teams: "BUF" })).sort(), everyone);
  assert.deepEqual(Object.keys(drawn({ teams: "MIA" })).sort(), everyone);
});

test("a picked player is lit even when his team is not chosen (the union)", () => {
  assert.deepEqual(drawn({ teams: "BUF", players: "C. Mia" }), {
    "A. Buf": false,
    "B. Buf": false,
    "C. Mia": false,
    "D. Mia": true,
  });
});

test("Players alone lights only the players picked", () => {
  assert.deepEqual(drawn({ players: "D. Mia" }), { "A. Buf": true, "B. Buf": true, "C. Mia": true, "D. Mia": false });
});

test("no team and no player dims everyone alike", () => {
  assert.deepEqual(Object.values(drawn({})), [true, true, true, true]);
});

test("the threshold is a hard gate: a player under it is not plotted even on a chosen team or picked", () => {
  assert.ok(!("E. Low" in drawn({ teams: "BUF", players: "E. Low" })));
  assert.ok("E. Low" in drawn({ teams: "BUF", threshold: "50" }));
});

test("the chart title starts with the season on a Season page", () => {
  drawn({});

  const [, , layout] = globalThis.Plotly.reactCalls.at(-1);

  assert.equal(layout.title.text, "2025 NFL Edge x_metric & y_metric");
});
