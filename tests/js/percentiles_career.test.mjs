// INVARIANT #1 on the Career page: one pool per exact position, never split by status, and each member in by
// the bar of his own status. Its own file because the page (Season or Career) is fixed once per process.

import assert from "node:assert/strict";
import { test } from "node:test";

import { categoryMetadata, installBrowser } from "./support/browser_stub.mjs";

installBrowser({ career: true });

const data = await import("../../frontend/data.js");

const JOINED = "Joined NFL";
const PROSPECTS = "Prospects";

// (player, status, position, opportunities, metric value).
const ROWS = [
  ["j-high", JOINED, "ED", 400, 10],
  ["j-low", JOINED, "ED", 200, 20],
  ["p-high", PROSPECTS, "ED", 200, 30],
  ["p-low", PROSPECTS, "ED", 100, 40],
  ["j-other", JOINED, "DI", 400, 50],
];

function load() {
  data.setMetadata({
    pass_rush: categoryMetadata(),
    pass_block: categoryMetadata({ thresholdField: "PB Snaps" }),
    team_conferences: {},
  });
  data.setCurrentSlice(
    ROWS.map(([player, status, position, opportunities, m]) => ({
      player,
      status,
      position,
      team: "X",
      "PR Opp": opportunities,
      m,
    })),
    "pass_rush"
  );
  data.setAppliedFilters({
    category: "pass_rush",
    season: "Career",
    position: "ED",
    threshold: "300",
    prospectThreshold: "150",
    statuses: PROSPECTS,
  });
}

test("the Career pool is one pool of the exact position, each member in by the bar of his own status", () => {
  load();
  const names = data.positionPool("ED").map((r) => r.player);

  assert.deepEqual(names, ["j-high", "p-high"]);
});

test("a status that is off or lit never changes who is in the pool", () => {
  load();
  const lit = data.positionPool("ED").map((r) => r.player);

  data.setAppliedFilters({ ...data.appliedFilters, statuses: "" });

  assert.deepEqual(
    data.positionPool("ED").map((r) => r.player),
    lit
  );
});
