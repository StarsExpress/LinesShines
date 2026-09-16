/* Pure constants — no DOM, no fetch, no other module dependency.
 * Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3 step 1.
 */

// Teams are global (not category/season-scoped like positions/metrics are),
// so this only runs once at startup rather than from
// populateCategoryDependentControls() — repopulating on every category
// switch would silently reset an in-progress team selection back to "all".
// NFL conference/division structure — not exposed by /api/metadata (it's
// static league structure, not PFF-derived data), so it lives here purely
// to lay the Teams checklist out like NFL.com: AFC in the left column, NFC
// in the right, each divided into East/North/South/West groups. Codes match
// the LinesShines/PFF spellings in teams_reference.py (BLT, CLV, HST, LA,
// LV, ...), not the NFL's own abbreviations.
export const CONFERENCES = {
  AFC: {
    East: ["BUF", "MIA", "NE", "NYJ"],
    North: ["BLT", "CIN", "CLV", "PIT"],
    South: ["HST", "IND", "JAX", "TEN"],
    West: ["DEN", "KC", "LAC", "LV"],
  },
  NFC: {
    East: ["DAL", "NYG", "PHI", "WAS"],
    North: ["CHI", "DET", "GB", "MIN"],
    South: ["ATL", "CAR", "NO", "TB"],
    West: ["ARZ", "LA", "SEA", "SF"],
  },
};

// Teams is a highlight, not a filter — a player whose team isn't selected
// stays on the plot (still visible, still clickable, still counted in the
// median) but fades to these opacities instead of disappearing.
export const DIM_OPACITY = { marker: 0.15, logo: 0.22, label: 0.12 };
export const LABEL_ALPHA = 0.8; // normal (non-dimmed) player-name opacity

export const MERGE_CARD_MAX_MEMBERS = 5;
export const MERGE_QUOTA = 8;

// Position-group pulled into a Linemate Card's roster and the per-category
// cap on how many can be shown — both keyed by category, not position,
// since a Linemate Card spans every position within its anchor's category
// (BLUEPRINT.md §2.2).
export const LINEMATE_POSITIONS = { pass_block: ["T", "G", "C"], pass_rush: ["ED", "DI"] };
export const LINEMATE_CAP = { pass_block: 5, pass_rush: 7 };
export const LINEMATE_VISIBLE_DEFAULT = 5;

// Mirrors config.py's DISPLAY_DECIMALS — keep in sync. UI-display rounding
// only: plots (render.js's xVals/yVals, drawn straight from record[key])
// stay full-precision, since rounding coordinates would visibly shift point
// positions. This only governs formatValue()'s rendered stat-table text.
export const DISPLAY_DECIMALS = 1;
