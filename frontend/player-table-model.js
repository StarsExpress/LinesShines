/* The structure of the player tables of the Comparison (Merge) Card and the Linemate Card, with no DOM and no data
 * lookups, so its two layouts come from ONE model and the transposition between
 * them can be unit tested. merge-card.js turns each cell descriptor into DOM.
 * Dependency-free, like table-sort.js.
 *
 * A model is { players, columns }. `players` are the card's members in the order
 * they should appear (already sorted by the card's current sort state); each
 * entry is opaque to this file. `columns` are Player, Team, Linemates, Status (Career only), Games,
 * the threshold field, then one per metric, each tagged with a `kind`.
 *
 * Both layouts hold exactly the same cells ({ player, column }), laid out as
 * { head, body }:
 *   Sort — one header row of columns, one body row per player. The original layout.
 *   Read — the same cells turned on their side: one column per player, one row
 *          per column. The player's identity cells (name, team, Linemates button)
 *          form the head block; Status, Games, the threshold field and the metrics are
 *          the body rows. Easier to read, and the default.
 */

export const TABLE_MODE_READ = "read";
export const TABLE_MODE_SORT = "sort";

// The identity columns of the Comparison Card: the per-player cells that head each
// column in the Read layout. The Linemate Card passes its own (name, position, Card).
const MERGE_IDENTITY_COLUMNS = [
  { key: "Player", kind: "name" },
  { key: "Team", kind: "team" },
  { key: "Linemates", kind: "linemates" },
];

// `bonusKeys` are the metrics flagged `bonus` in the metadata (Pass Cov Percent,
// DL only): Read shows them in their own section after the required ones.
export function buildPlayerTableModel(
  players,
  thresholdField,
  metricKeys,
  bonusKeys = [],
  identityColumns = MERGE_IDENTITY_COLUMNS,
  includeStatus = false
) {
  const columns = [
    ...identityColumns.map((column) => ({ ...column, identity: true })),
    // Career only: whether the player is a Joined NFL or a Potential Draftee.
    ...(includeStatus ? [{ key: "Status", kind: "status" }] : []),
    { key: "Games", kind: "games" },
    { key: thresholdField, kind: "snaps" },
    ...metricKeys.map((key) => ({ key, kind: "metric", bonus: bonusKeys.includes(key) })),
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
//
// `body` is the flat list of rows; `sections` is the same rows grouped for display —
// Metadata (Status on Career, Games, the threshold field), Required Metrics, and Bonus Metrics, which
// is left out when the category has none (pass block).
export function readLayout(model) {
  const row = (column) => ({ column, cells: model.players.map((player) => ({ player, column })) });
  const body = model.columns.filter((column) => !column.identity).map(row);
  const section = (title, keep) => ({ title, rows: body.filter((r) => keep(r.column)) });
  const sections = [
    section("Metadata", (c) => c.kind === "status" || c.kind === "games" || c.kind === "snaps"),
    section("Required Metrics", (c) => c.kind === "metric" && !c.bonus),
    section("Bonus Metrics", (c) => c.kind === "metric" && c.bonus),
  ].filter((s) => s.rows.length > 0);
  return {
    head: model.columns.filter((column) => column.identity).map(row),
    body,
    sections,
  };
}
