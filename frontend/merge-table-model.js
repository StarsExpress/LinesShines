/* The structure of the Comparison (Merge) Card's table, with no DOM and no data
 * lookups, so its two layouts come from ONE model and the transposition between
 * them can be unit tested. merge-card.js turns each cell descriptor into DOM.
 * Dependency-free, like table-sort.js.
 *
 * A model is { players, columns }. `players` are the card's members in the order
 * they should appear (already sorted by the card's current sort state); each
 * entry is opaque to this file. `columns` are Player, Team, Linemates, Games,
 * the threshold field, then one per metric, each tagged with a `kind`.
 *
 * Both layouts hold exactly the same cells ({ player, column }), laid out as
 * { head, body }:
 *   Sort — one header row of columns, one body row per player. The original layout.
 *   Read — the same cells turned on their side: one column per player, one row
 *          per column. The player's identity cells (name, team, Linemates button)
 *          form the head block; Games, the threshold field and the metrics are
 *          the body rows. Easier to read, and the default.
 */

export const MERGE_MODE_READ = "read";
export const MERGE_MODE_SORT = "sort";

// The per-player identity cells that head each column in the Read layout.
const IDENTITY_KINDS = ["name", "team", "linemates"];

export function buildMergeTableModel(players, thresholdField, metricKeys) {
  const columns = [
    { key: "Player", kind: "name" },
    { key: "Team", kind: "team" },
    { key: "Linemates", kind: "linemates" },
    { key: "Games", kind: "games" },
    { key: thresholdField, kind: "snaps" },
    ...metricKeys.map((key) => ({ key, kind: "metric" })),
  ];
  return { players, columns };
}

// Sort layout: head is the list of columns; body has one row per player.
export function sortLayout(model) {
  return {
    head: model.columns,
    body: model.players.map((player) => ({
      player,
      cells: model.columns.map((column) => ({ player, column })),
    })),
  };
}

// Read layout: head and body are both lists of rows, one per column, each holding
// that column's cell for every player in the model's order.
export function readLayout(model) {
  const row = (column) => ({ column, cells: model.players.map((player) => ({ player, column })) });
  return {
    head: model.columns.filter((column) => IDENTITY_KINDS.includes(column.kind)).map(row),
    body: model.columns.filter((column) => !IDENTITY_KINDS.includes(column.kind)).map(row),
  };
}
