// INVARIANT #3 on the Career page: the Status Filter joins the same union and only highlights, and each
// player must clear the bar of his own status. Its own file because the page is fixed once per process.

import assert from "node:assert/strict";
import { test } from "node:test";

import { categoryMetadata, installBrowser } from "./support/browser_stub.mjs";

installBrowser({ career: true });

const data = await import("../../frontend/data.js");
const { render } = await import("../../frontend/render.js");
const { DIM_OPACITY } = await import("../../frontend/config.js");

const JOINED = "Joined NFL";
const PROSPECTS = "Prospects";

// (player, status, team, opportunities). Bars: Joined 300, Prospects 150. "P-short" is a Prospect under his bar.
const ROWS = [
  ["J-one", JOINED, "AAA", 400],
  ["J-two", JOINED, "BBB", 400],
  ["P-one", PROSPECTS, "AAA", 200],
  ["P-two", PROSPECTS, "BBB", 200],
  ["P-short", PROSPECTS, "AAA", 100],
];

function drawn({ teams = "", players = "", statuses = "", threshold = "300", prospectThreshold = "150" }) {
  data.setMetadata({
    pass_rush: categoryMetadata(),
    pass_block: categoryMetadata({ thresholdField: "PB Snaps" }),
    team_conferences: {},
  });
  data.setCurrentSlice(
    ROWS.map(([player, status, team, opportunities], i) => ({
      player,
      abbr_name: player,
      status,
      team,
      conference: "C",
      position: "ED",
      "PR Opp": opportunities,
      x_metric: 10 + i,
      y_metric: 20 + 2 * i,
    })),
    "pass_rush"
  );
  data.setAppliedFilters({
    category: "pass_rush",
    season: "Career",
    position: "ED",
    xMetric: "x_metric",
    yMetric: "y_metric",
    threshold,
    prospectThreshold,
    teams,
    players,
    statuses,
  });
  globalThis.Plotly.reactCalls.length = 0;
  render();

  const [, [trace]] = globalThis.Plotly.reactCalls.at(-1);

  return Object.fromEntries(trace.text.map((name, i) => [name, trace.marker.opacity[i] === DIM_OPACITY.marker]));
}

test("each player is judged against the bar of his own status", () => {
  assert.deepEqual(Object.keys(drawn({})).sort(), ["J-one", "J-two", "P-one", "P-two"]);
});

test("a lit status lights its players and dims the other status", () => {
  assert.deepEqual(drawn({ statuses: PROSPECTS }), { "J-one": true, "J-two": true, "P-one": false, "P-two": false });
});

test("a lit status joins the union with a chosen team and a picked player", () => {
  assert.deepEqual(drawn({ statuses: PROSPECTS, teams: "AAA|C", players: "J-two" }), {
    "J-one": false,
    "J-two": false,
    "P-one": false,
    "P-two": false,
  });
});

test("a status that is off lights nobody and never changes who is plotted", () => {
  const off = drawn({ statuses: "" });

  assert.deepEqual(Object.values(off), [true, true, true, true]);
  assert.deepEqual(Object.keys(off), Object.keys(drawn({ statuses: `${JOINED},${PROSPECTS}` })));
});

test("a stricter bar for one status removes only that status", () => {
  assert.deepEqual(Object.keys(drawn({ prospectThreshold: "250" })).sort(), ["J-one", "J-two"]);
});

test("the chart title puts the position before the word Career", () => {
  drawn({});

  const [, , layout] = globalThis.Plotly.reactCalls.at(-1);

  assert.equal(layout.title.text, "NCAAF Edge Career x_metric & y_metric");
});
