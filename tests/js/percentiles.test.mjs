// INVARIANTS #1 and #2: a percentile pool is one exact position above the threshold, and ties share a rank.
// The browser-free twin of tests/test_percentiles.py, run by `npm run test:js`.

import assert from "node:assert/strict";
import { before, describe, test } from "node:test";

import { installBrowser } from "./support/browser_stub.mjs";

installBrowser();

const data = await import("../../frontend/data.js");
const { categoryMetadata } = await import("./support/browser_stub.mjs");

const THRESHOLD_FIELD = "PR Opp";

// (player, position, opportunities, metric value). e4 falls below a threshold of 100.
const ROWS = [
  ["e1", "ED", 300, 10],
  ["e2", "ED", 300, 20],
  ["e3", "ED", 300, 30],
  ["e4", "ED", 50, 99],
  ["d1", "DI", 300, 40],
  ["d2", "DI", 300, 50],
];

function load(selectedPosition, threshold) {
  data.setMetadata({ pass_rush: categoryMetadata(), teams: {} });
  data.setCurrentSlice(
    ROWS.map(([player, position, opportunities, m]) => ({ player, position, [THRESHOLD_FIELD]: opportunities, m })),
    "pass_rush"
  );
  data.setAppliedFilters({
    category: "pass_rush",
    season: "2025",
    position: selectedPosition,
    threshold: String(threshold),
  });
}

const pool = (...values) => values.map((m) => ({ m }));
const names = (records) => records.map((r) => r.player);

describe("#1 the percentile pool", () => {
  before(() => load("ED", 100));

  test("holds only the exact position above the threshold", () => {
    assert.deepEqual(names(data.positionPool("ED")), ["e1", "e2", "e3"]);
    assert.deepEqual(names(data.positionPool("DI")), ["d1", "d2"]);
  });

  test("treats the threshold as a hard gate that includes its own value", () => {
    load("ED", 50);
    assert.deepEqual(names(data.positionPool("ED")), ["e1", "e2", "e3", "e4"]);

    load("ED", 300);
    assert.deepEqual(names(data.positionPool("ED")), ["e1", "e2", "e3"]);

    load("ED", 301);
    assert.deepEqual(names(data.positionPool("ED")), []);
  });

  test("gives the same percentile whichever position is selected on the chart", () => {
    const percentileOf = (selected) => {
      load(selected, 100);
      const edPool = data.positionPool("ED");

      return data.rankAndPercentile(edPool, "m", true, 20).percentile;
    };

    assert.equal(percentileOf("ED"), 50);
    assert.equal(percentileOf("DI"), 50);
  });

  test("would differ if positions were pooled together", () => {
    load("ED", 100);
    const combined = data.positionPool("ED").concat(data.positionPool("DI"));

    assert.equal(data.rankAndPercentile(combined, "m", true, 20).percentile, 25);
  });
});

describe("#2 ties and ranks", () => {
  const rank = (values, higherIsBetter, value) => data.rankAndPercentile(pool(...values), "m", higherIsBetter, value);

  test("tied values share one rank and one percentile, and the next rank is skipped", () => {
    assert.deepEqual(rank([10, 20, 20, 30], true, 30), { rank: 1, n: 4, percentile: 100 });
    assert.deepEqual(rank([10, 20, 20, 30], true, 20), { rank: 2, n: 4, percentile: 67 });
    assert.deepEqual(rank([10, 20, 20, 30], true, 10), { rank: 4, n: 4, percentile: 0 });
  });

  test("lower-is-better flips the direction", () => {
    assert.deepEqual(rank([1, 2, 2, 3], false, 1), { rank: 1, n: 4, percentile: 100 });
    assert.deepEqual(rank([1, 2, 2, 3], false, 2), { rank: 2, n: 4, percentile: 67 });
    assert.deepEqual(rank([1, 2, 2, 3], false, 3), { rank: 4, n: 4, percentile: 0 });
  });

  test("everyone tied shares the best rank", () => {
    assert.deepEqual(rank([5, 5, 5], true, 5), { rank: 1, n: 3, percentile: 100 });
  });

  test("pool order never changes the result", () => {
    for (const order of [
      [10, 20, 20, 30],
      [30, 20, 10, 20],
      [20, 30, 20, 10],
    ]) {
      assert.deepEqual(rank(order, true, 20), { rank: 2, n: 4, percentile: 67 });
    }
  });

  test("missing values are left out of the pool", () => {
    assert.deepEqual(rank([10, null, 20, 30], true, 20), { rank: 2, n: 3, percentile: 50 });
  });

  test("gives no result without a value or without two players", () => {
    assert.equal(rank([10, 20], true, null), null);
    assert.equal(rank([10], true, 10), null);
    assert.equal(rank([], true, 10), null);
  });
});
