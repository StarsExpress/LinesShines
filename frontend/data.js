/* Fetch + shared app state + derived data helpers (percentiles, team/logo
 * lookups). Foundation layer every other feature module reads from.
 * Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3 step 2.
 *
 * Mutable state below is owned here and exported both as a raw (read-only
 * for importers) binding and, for the handful of call sites elsewhere that
 * need to reassign it, a thin setter — ES modules don't allow an importing
 * module to assign an imported `let` directly. These setters are a
 * mechanical consequence of the module split, not a behavior change: same
 * assignment, same order, same timing as the original app.js.
 */
import { els } from "./dom.js";

export const LOGO_PATH = (team) => `logos/${team}.png`;

export let metadata = null;                 // /api/metadata payload
export const sliceCache = new Map();        // key = `${category}:${season}:${position}` → records[]
export let currentRecords = [];             // records for the current slice (all threshold values)
export let currentFiltered = [];            // records >= threshold (what the chart shows)

// Which category's schema currentRecords actually matches. Tracked
// separately from els.category.value because a pending (not-yet-Applied)
// category switch changes els.category.value immediately while
// currentRecords still holds the previous category's rows until Apply
// re-runs loadCurrentSlice() — code that reads currentRecords (the Players
// pool, see qualifyingPlayerPool()) needs the category that actually
// matches the data in hand, not the one the dropdown currently shows.
export let currentSliceCategory = null;

// Records for whatever category/season/position the controls are *currently
// set to* (pending, not necessarily Applied yet) — feeds only the Players
// search pool (qualifyingPlayerPool()), kept live by updatePlayerPool() on
// every category/season/position change so switching Position immediately
// changes which players the search box will suggest, rather than waiting
// for Apply the way the chart itself does. Deliberately separate from
// currentRecords/currentSliceCategory above, which stay Apply-gated.
export let playerPoolRecords = [];
export let playerPoolCategory = null;

// Snapshot of {category, season, position, xMetric, yMetric, threshold} the
// chart was last actually rendered with. Every one of those controls can be
// changed freely without touching the chart — render() and openScoutCard()
// read from this snapshot, never live off the controls directly — so the
// Apply button is what commits a batch of changes together, and an
// unrelated render() trigger (the label/logo toggles) can't accidentally
// leak in a half-picked axis or threshold that hasn't been applied yet.
export let appliedFilters = null;

// Decoded Image objects, keyed by team code, filled once at page load so
// filter changes never wait on the browser to re-resolve/decode /logos/*.png
// again — layout.images and the scout card both just point at these.
export const logoCache = {};

export function setMetadata(m) {
  metadata = m;
}

export function setCurrentSlice(records, category) {
  currentRecords = records;
  currentSliceCategory = category;
}

export function setCurrentFiltered(records) {
  currentFiltered = records;
}

export function setPlayerPool(records, category) {
  playerPoolRecords = records;
  playerPoolCategory = category;
}

export function setAppliedFilters(filters) {
  appliedFilters = filters;
}

export async function preloadLogos() {
  if (!metadata || !metadata.teams) return;
  const codes = Object.keys(metadata.teams);
  await Promise.all(
    codes.map(
      (code) =>
        new Promise((resolve) => {
          const img = new Image();
          img.onload = () => {
            logoCache[code] = img;
            resolve();
          };
          img.onerror = () => resolve(); // missing file → falls back to the badge/no source
          img.src = LOGO_PATH(code);
        })
    )
  );
}

// Prefer the preloaded, already-decoded image's resolved URL over the raw
// relative path — same bytes, but guarantees Plotly/the <img> tag hit the
// exact URL the browser already cached.
export function logoSrc(team) {
  return logoCache[team] ? logoCache[team].src : LOGO_PATH(team);
}

// Logos are sized as a fixed pixel target rather than a fraction of plot
// width so a dense mobile chart doesn't inherit same visual scale as a 1100px desktop chart.
// Mobile gets a smaller absolute size to cut overlap.
// Player labels default to on, logos take up less room and collision is smaller.
export function targetLogoPx() {
  return window.innerWidth < 860 ? 16 : 26;
}

export function currentCategoryMeta() {
  return metadata[els.category.value];
}

// Moved here (not filters.js, where every other Teams-checklist helper
// lives) because render.js's highlightSubtitle() needs it too and can't
// import from filters.js without a circular import — see filters.js's
// header comment.
export function allTeamCodes() {
  return Array.from(els.teamsChecklist.querySelectorAll("input[type=checkbox]")).map((cb) => cb.value);
}

// The category metadata for whatever's actually plotted right now, as
// opposed to currentCategoryMeta() which tracks the (possibly still
// pending, not-yet-applied) category select.
export function appliedCategoryMeta() {
  return metadata[appliedFilters.category];
}

// Shared by loadCurrentSlice() (Apply-gated, drives the chart) and
// updatePlayerPool() (live, drives only the Players search pool) — both
// just need every position's records for a given category/season, memoized
// in sliceCache so switching back to an already-seen combination is free.
// No position param: the API returns every position in the category (see
// main.py), and the client partitions by position from here on — required
// so Linemate Cards can pull cross-position rosters (T/G/C, ED/DI) out of
// the same in-memory slice instead of a second fetch. Percentile pools must
// still be computed per exact position (see positionPool() below) — never
// over this combined array — per the "first philosophy" comment in
// BLUEPRINT.md §3.
export async function fetchSlice(category, season) {
  const key = `${category}:${season}`;
  if (!sliceCache.has(key)) {
    const url = `/api/${category}?season=${season}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
    const data = await res.json();
    sliceCache.set(key, data.records || []);
  }
  return sliceCache.get(key);
}

// Every position pool now lives in currentRecords (see fetchSlice above), so
// percentiles/ranks for Merge and Linemate cards must filter down to one
// exact position — never the combined multi-position array — before ranking.
// Mirrors currentFiltered's own filter in render(), just parameterized over
// position instead of being locked to appliedFilters.position.
export function positionPool(position) {
  const cat = appliedCategoryMeta();
  const minThreshold = Number(appliedFilters.threshold);
  return currentRecords.filter((r) => r.position === position && r[cat.threshold_field] >= minThreshold);
}

export function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  if (n === 0) return null;
  if (n % 2 === 1) return sorted[(n - 1) / 2];
  return Math.round(((sorted[n / 2 - 1] + sorted[n / 2]) / 2) * 10) / 10;
}

// Shared by the threshold control's own label and the chart subtitle, so
// the two can't drift out of sync with each other.
export function thresholdFieldLabel(cat) {
  return cat.threshold_field === "PR Opp" ? "pass rush opportunities" : "non-spike pass block snaps";
}

// Rank (1 = best) and percentile (100 = best) for `value` on metric `key`
// among `pool`, respecting the metric's higher/lower-is-better direction
// (see PASS_RUSH_METRICS / PASS_BLOCK_METRICS in main.py). Ties share a
// rank — competition ranking, so equal values don't get an arbitrary
// tiebreak order — and the pool is exactly `currentFiltered`, i.e. the
// same season/position/category/threshold population the chart is
// currently plotting, not the unfiltered slice.
export function rankAndPercentile(pool, key, higherIsBetter, value) {
  if (value == null) return null;
  const values = pool.map((r) => r[key]).filter((v) => v != null);
  const n = values.length;
  if (n < 2) return null;
  const better = (v) => (higherIsBetter ? v > value : v < value);
  const rank = values.filter(better).length + 1;
  const percentile = Math.round(((n - rank) / (n - 1)) * 100);
  return { rank, n, percentile };
}

export function teamColor(code) {
  const t = metadata.teams && metadata.teams[code];
  return (t && t.primary_color) || "#6b7a6f";
}

export function teamName(code) {
  const t = metadata.teams && metadata.teams[code];
  return (t && t.full_name) || code;
}

// Fallback swatch for the teams-dropdown checklist when a team's logo file
// 404s — mirrors openScoutCard()'s logoImg.onerror treatment.
export function teamSwatch(code) {
  const span = document.createElement("span");
  span.className = "team-swatch";
  span.style.background = teamColor(code);
  return span;
}

// A merged member can outlive his Single Cards row (Remove only touches
// Single Cards, never merged instances — §4/§6), so his full record has to
// come from the applied slice itself rather than from workspaceSingles.
export function findRecordByPlayer(key) {
  return currentRecords.find((r) => r.player === key) || null;
}
