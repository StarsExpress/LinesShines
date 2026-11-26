// INVARIANTS #9 and #17: which Apply outcome a filter change implies for Pinned Players and Comparison Cards,
// and the one eligibility function that the Players filter shares with it.
// The browser-free twin of the rules in tests/test_pinned_impact.py, run by `npm run test:js`.

import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  evaluatePinnedImpact,
  mayApplyWithoutConfirm,
  partitionByEligibility,
  resolveCarriedRecord,
  thresholdRaised,
} from "../../frontend/pinned-impact.js";

const FIELD = "PR Opp";

const state = ({ season = 2025, position = "ED", threshold = 230, category = "pass_rush" } = {}) => ({
  category,
  season: String(season),
  position,
  threshold,
});

const rec = (player, opportunities, position = "ED") => ({ player, position, [FIELD]: opportunities });
const poolOf = (values) => Object.entries(values).map(([player, opportunities]) => rec(player, opportunities));

const impact = (applied, pending, pinned, pool, comparisons = []) =>
  evaluatePinnedImpact(
    applied,
    pending,
    pinned,
    pool,
    FIELD,
    comparisons.map(([id, memberKeys]) => ({ id, memberKeys }))
  );

const POOL = poolOf({ A: 300, B: 250, C: 240 });

describe("#9 the outcome of a change", () => {
  test("a Category or Position change clears everything, even with no data", () => {
    assert.equal(impact(state(), state({ category: "pass_block" }), ["A"], []).outcome, "reset");
    assert.equal(impact(state(), state({ position: "DI" }), ["A"], POOL).outcome, "reset");
  });

  test("nothing changed, or a looser threshold, leaves everyone alone", () => {
    assert.equal(impact(state(), state(), ["A"], POOL).outcome, "unaffected");
    assert.equal(impact(state(), state({ threshold: 100 }), ["ghost"], POOL).outcome, "unaffected");
  });

  test("a tighter threshold keeps those who still clear it (inclusive) and removes only the rest", () => {
    assert.equal(impact(state(), state({ threshold: 240 }), ["A", "B", "C"], POOL).outcome, "unaffected");

    const partial = impact(state(), state({ threshold: 241 }), ["A", "B", "C"], POOL);

    assert.equal(partial.outcome, "partial");
    assert.deepEqual([partial.kept, partial.removed], [["A", "B"], ["C"]]);
  });

  test("everyone falling short is a reset, not a partial", () => {
    const result = impact(state(), state({ threshold: 240 }), ["A", "B"], poolOf({ A: 10, B: 20 }));

    assert.equal(result.outcome, "reset");
    assert.deepEqual(result.kept, []);
  });

  test("a season change refreshes when everyone is still eligible and is partial when someone is not", () => {
    const pool = poolOf({ A: 260, B: 230 });

    assert.equal(impact(state(), state({ season: 2024 }), ["A", "B"], pool).outcome, "refresh");
    assert.equal(impact(state(), state({ season: 2024 }), ["A", "B"], poolOf({ A: 260 })).outcome, "partial");
    assert.equal(
      impact(state(), state({ season: 2024 }), ["A", "B"], [rec("A", 260), rec("B", 300, "DI")]).outcome,
      "partial"
    );
    assert.equal(impact(state(), state({ season: 2024 }), [], []).outcome, "refresh");
  });

  test("only a refresh or an unaffected change applies without a confirm", () => {
    assert.deepEqual(["unaffected", "refresh", "partial", "reset"].map(mayApplyWithoutConfirm), [
      true,
      true,
      false,
      false,
    ]);
  });
});

describe("#9 Comparison Cards", () => {
  const next = state({ threshold: 240 });
  const pool = poolOf({ A: 300, B: 250, C: 100, D: 260 });

  test("a comparison shrinks while two members remain", () => {
    const { comparisons } = impact(state(), next, ["A", "B", "C"], pool, [["m1", ["A", "B", "C"]]]);

    assert.deepEqual(comparisons.dissolved, []);
    assert.deepEqual(
      comparisons.shrunk.map((s) => [s.id, s.kept, s.removed]),
      [["m1", ["A", "B"], ["C"]]]
    );
  });

  test("a comparison dissolves below two members", () => {
    const one = impact(state(), next, ["A", "B", "C"], pool, [["m1", ["A", "C"]]]).comparisons;
    const none = impact(state(), next, ["A", "B", "C"], poolOf({ A: 300, B: 100, C: 100 }), [
      ["m1", ["B", "C"]],
    ]).comparisons;

    assert.deepEqual(one.shrunk, []);
    assert.deepEqual(
      one.dissolved.map((d) => [d.id, d.survivors]),
      [["m1", ["A"]]]
    );
    assert.deepEqual(
      none.dissolved.map((d) => d.survivors),
      [[]]
    );
  });

  test("a shrunk comparison that duplicates another is dissolved, and equal ones keep only the first", () => {
    const duplicate = impact(state(), next, ["A", "B", "C"], pool, [
      ["m1", ["A", "B", "C"]],
      ["m2", ["A", "B"]],
    ]).comparisons;

    assert.deepEqual(duplicate.shrunk, []);
    assert.deepEqual(
      duplicate.dissolved.map((d) => [d.id, d.duplicate]),
      [["m1", true]]
    );

    const equal = impact(state(), next, ["A", "B", "C", "D"], poolOf({ A: 300, B: 250, C: 100, D: 100 }), [
      ["m1", ["A", "B", "C"]],
      ["m2", ["A", "B", "D"]],
      ["m3", ["B", "A", "C", "D"]],
    ]).comparisons;

    assert.deepEqual(
      equal.shrunk.map((s) => s.id),
      ["m1"]
    );
    assert.deepEqual(
      equal.dissolved.map((d) => d.id),
      ["m2", "m3"]
    );
  });
});

describe("#9 on the Career page", () => {
  const JOINED = "Joined NFL";
  const PROSPECTS = "Prospects";
  const career = (player, opportunities, status) => ({ player, position: "ED", [FIELD]: opportunities, status });
  const CAREER_POOL = [
    career("J-high", 400, JOINED),
    career("J-low", 200, JOINED),
    career("P-high", 200, PROSPECTS),
    career("P-low", 100, PROSPECTS),
  ];
  const careerState = (joined, prospect) => ({
    category: "pass_rush",
    season: "Career",
    position: "ED",
    threshold: { joined, prospect },
  });

  test("raising either bar counts as stricter, lowering never does", () => {
    const base = { joined: 300, prospect: 150 };

    assert.ok(thresholdRaised({ joined: 300, prospect: 151 }, base));
    assert.ok(thresholdRaised({ joined: 301, prospect: 150 }, base));
    assert.ok(!thresholdRaised({ joined: 200, prospect: 100 }, base));
    assert.ok(!thresholdRaised(base, base));
  });

  test("a stricter Prospect bar removes only Prospects", () => {
    const result = impact(careerState(300, 150), careerState(300, 250), ["J-high", "P-high"], CAREER_POOL);

    assert.equal(result.outcome, "partial");
    assert.deepEqual([result.kept, result.removed], [["J-high"], ["P-high"]]);
  });

  test("a looser bar, or the one Career season, changes nothing", () => {
    const pinned = ["J-high", "P-high"];

    assert.equal(impact(careerState(300, 150), careerState(250, 100), pinned, CAREER_POOL).outcome, "unaffected");
    assert.equal(impact(careerState(300, 150), careerState(300, 150), pinned, CAREER_POOL).outcome, "unaffected");
  });
});

describe("#17 one eligibility function", () => {
  const partition = (names, pool, threshold, position = "ED") =>
    partitionByEligibility(names, pool, position, threshold, FIELD);

  test("keeps those who clear the threshold, inclusively, in the order given", () => {
    assert.deepEqual(partition(["C", "A", "B"], POOL, 245), { kept: ["A", "B"], removed: ["C"] });
    assert.deepEqual(partition(["A", "B", "C"], POOL, 250).kept, ["A", "B"]);
    assert.deepEqual(partition(["C", "A", "B"], POOL, 0).kept, ["C", "A", "B"]);
  });

  test("removes a player who is missing, at another position, without a value, or in an empty pool", () => {
    assert.deepEqual(partition(["A", "Z"], POOL, 0), { kept: ["A"], removed: ["Z"] });
    assert.deepEqual(partition(["A", "D"], [rec("A", 300), rec("D", 300, "DI")], 0), { kept: ["A"], removed: ["D"] });
    assert.deepEqual(partition(["A", "N"], [rec("A", 300), { player: "N", position: "ED", [FIELD]: null }], 0), {
      kept: ["A"],
      removed: ["N"],
    });
    assert.deepEqual(partition(["A", "B"], [], 0), { kept: [], removed: ["A", "B"] });
    assert.deepEqual(partition(["A", "B"], null, 0), { kept: [], removed: ["A", "B"] });
  });

  test("Pinned Players and the Players filter draw the same line at the same boundary", () => {
    const pinned = ["A", "B", "C"];
    const viaImpact = impact(state(), state({ threshold: 250 }), pinned, POOL);
    const viaFilter = partition(pinned, POOL, 250);

    assert.equal(viaImpact.outcome, "partial");
    assert.deepEqual([viaImpact.kept, viaImpact.removed], [viaFilter.kept, viaFilter.removed]);
  });

  test("on Career each player is judged against the bar of his own status", () => {
    const pool = [
      { player: "J-high", position: "ED", [FIELD]: 400, status: "Joined NFL" },
      { player: "J-low", position: "ED", [FIELD]: 200, status: "Joined NFL" },
      { player: "P-high", position: "ED", [FIELD]: 200, status: "Prospects" },
      { player: "P-low", position: "ED", [FIELD]: 100, status: "Prospects" },
    ];

    assert.deepEqual(partition(["J-high", "J-low", "P-high", "P-low"], pool, { joined: 300, prospect: 150 }), {
      kept: ["J-high", "P-high"],
      removed: ["J-low", "P-low"],
    });
  });

  test("a card follows a teammate on the line and closes when he is out", () => {
    const line = ["ED", "DI"];
    const pool = [rec("Edge", 200, "ED"), rec("Tackle", 150, "DI"), rec("Guard", 300, "G")];
    const resolve = (name, preferred, threshold) => resolveCarriedRecord(pool, name, preferred, line, threshold, FIELD);

    assert.equal(resolve("Tackle", "DI", 100).position, "DI");
    assert.equal(resolve("Tackle", "DI", 151), null);
    assert.notEqual(resolve("Tackle", "DI", 150), null);
    assert.equal(resolve("Guard", "G", 100), null);
    assert.equal(resolve("Nobody", "ED", 100), null);
  });
});
