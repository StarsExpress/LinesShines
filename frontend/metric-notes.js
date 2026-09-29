/* Shared "which metric notes apply to this export" logic — used by
 * chart-export.js (the scatter plot's Plotly/canvas export) and
 * card-export.js (the html2canvas-based Player/Merge/Linemate Card
 * exports), so it lives as its own dependency-free leaf, same reasoning as
 * table-sort.js/info-popover.js: neither export module needs a new
 * dependency on the other, or on any of the three card modules, just to
 * share this.
 *
 * A metric's own note is main.py's `note` (Havoc/Allowed Havoc family) or
 * `formula_note` (PRP/PBE family) — whichever is set. Most metrics (Win
 * Rate, Pressure Rate, Allowed Pressure %, ...) have neither and are
 * silently skipped, not padded with a boilerplate line — the appendix only
 * ever covers metrics that actually have a defined formula/note.
 *
 * Deduped by note TEXT, not by metric key: a metric and its "TPS "
 * counterpart intentionally share the same note (config.py's
 * HAVOC_RATE_NOTE/PRP_NOTE/PBE_NOTE convention, same one
 * frontend/main.js's axisFormulaContent() already relies on for the axis
 * popovers), so this collapses them to one line for free rather than
 * needing a separate "is this a TPS duplicate" check.
 *
 * `tpsNote` (config.py's TPS_NOTE, exposed at metadata.tps_note) is a
 * shared concept, not a per-metric formula — appended once, last, whenever
 * ANY of the given metricKeys is a "TPS "-prefixed variant, never
 * duplicated per TPS metric and never included when none of the export's
 * metrics are TPS.
 */
export function collectMetricNotes(cat, metricKeys, tpsNote) {
  if (!cat || !cat.metrics) return [];
  const seen = new Set();
  const notes = [];
  let anyTps = false;
  metricKeys.forEach((key) => {
    const meta = cat.metrics[key];
    if (!meta) return;
    if (key.startsWith("TPS ")) anyTps = true;
    const text = meta.note || meta.formula_note;
    if (!text || seen.has(text)) return;
    seen.add(text);
    notes.push(text);
  });
  if (anyTps && tpsNote) notes.push(tpsNote);
  return notes;
}

// Player/Merge/Linemate Cards all render every metric in their category,
// unconditionally (Object.entries(cat.metrics)/Object.keys(cat.metrics) in
// scout-card.js/merge-card.js/linemate-card.js — no subsetting by position
// or membership anywhere), so "which metrics appear in this card" is always
// just "every metric in its category" — this is that one-line convenience
// wrapper, shared by all three card modules' getAppendixNotes callbacks.
export function categoryAppendixNotes(cat, tpsNote) {
  if (!cat || !cat.metrics) return [];
  return collectMetricNotes(cat, Object.keys(cat.metrics), tpsNote);
}
