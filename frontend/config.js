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
// label bumped 0.12 -> 0.4 per a Reddit legibility follow-up: faded labels
// were below WCAG's 3:1 contrast floor against the chart background.
// Spotlighted labels (LABEL_ALPHA below) were already at the 1.0 ceiling, so
// raising the floor here necessarily narrows the spotlighted/faded gap —
// verified against screenshots (dense-cluster + ~400px mobile-width) before
// picking this value over smaller candidates that didn't clear 3:1.
export const DIM_OPACITY = { marker: 0.15, logo: 0.22, label: 0.4 };
// Bumped from 0.8 to fully opaque as the "brighter" half of the spotlighted-
// label emphasis follow-up (Reddit: "needs more contrast") — render.js's
// applyLabelEmphasis() handles the "bolder" + halo/glow half, since neither
// is expressible through Plotly's textfont config at all.
export const LABEL_ALPHA = 1;

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

// Platform logos for the Install popup (main.js): each platform maps to a list
// of { d, fill } shapes, `d` being the 24x24 Simple Icons path (https://simpleicons.org,
// CC0) embedded verbatim — shapes/proportions must not be edited. `fill` is a
// CSS variable defined once in style.css's :root (--logo-*), so recoloring is
// a one-place change. iOS and macOS share the Apple mark but not its color.
// Windows' single Simple Icons path is four subpaths, split here only so each
// square can take its own color (same coordinates; the last one's relative
// `m12.623,0` written as the absolute point it resolves to).
const APPLE_PATH =
  "M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701";
const ANDROID_PATH =
  "M18.4395 5.5586c-.675 1.1664-1.352 2.3318-2.0274 3.498-.0366-.0155-.0742-.0286-.1113-.043-1.8249-.6957-3.484-.8-4.42-.787-1.8551.0185-3.3544.4643-4.2597.8203-.084-.1494-1.7526-3.021-2.0215-3.4864a1.1451 1.1451 0 0 0-.1406-.1914c-.3312-.364-.9054-.4859-1.379-.203-.475.282-.7136.9361-.3886 1.5019 1.9466 3.3696-.0966-.2158 1.9473 3.3593.0172.031-.4946.2642-1.3926 1.0177C2.8987 12.176.452 14.772 0 18.9902h24c-.119-1.1108-.3686-2.099-.7461-3.0683-.7438-1.9118-1.8435-3.2928-2.7402-4.1836a12.1048 12.1048 0 0 0-2.1309-1.6875c.6594-1.122 1.312-2.2559 1.9649-3.3848.2077-.3615.1886-.7956-.0079-1.1191a1.1001 1.1001 0 0 0-.8515-.5332c-.5225-.0536-.9392.3128-1.0488.5449zm-.0391 8.461c.3944.5926.324 1.3306-.1563 1.6503-.4799.3197-1.188.0985-1.582-.4941-.3944-.5927-.324-1.3307.1563-1.6504.4727-.315 1.1812-.1086 1.582.4941zM7.207 13.5273c.4803.3197.5506 1.0577.1563 1.6504-.394.5926-1.1038.8138-1.584.4941-.48-.3197-.5503-1.0577-.1563-1.6504.4008-.6021 1.1087-.8106 1.584-.4941z";
export const PLATFORM_ICONS = {
  ios: [{ d: APPLE_PATH, fill: "var(--logo-ios)" }],
  macos: [{ d: APPLE_PATH, fill: "var(--logo-macos)" }],
  android: [{ d: ANDROID_PATH, fill: "var(--logo-android)" }],
  windows: [
    { d: "M0,0H11.377V11.372H0Z", fill: "var(--logo-windows-red)" },
    { d: "M12.623,0H24V11.372H12.623Z", fill: "var(--logo-windows-green)" },
    { d: "M0,12.623H11.377V24H0Z", fill: "var(--logo-windows-blue)" },
    { d: "M12.623,12.623H24V24H12.623Z", fill: "var(--logo-windows-yellow)" },
  ],
};
