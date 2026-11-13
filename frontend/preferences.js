/* The last choices a visitor made, remembered per View in this browser's localStorage.
 *
 * A View is one page: NFL Season, NCAAF Season or NCAAF Career. Each has its own key, so what
 * is remembered on one never leaks into another. Two things are remembered:
 *   - the X / Y axes, per category and position (ED and DI keep different pairs, OT, G and C too),
 *     written when the axes are applied, never while they are only pending;
 *   - the Player Names / Team Logos / Include metric notes switches, written as they are flipped.
 * Everything else (season, threshold, Teams, Players, category, position) is deliberately not kept.
 * There is no reset button by decision: a visitor who wants the defaults back picks the default pair
 * and applies it (a pair equal to the default is dropped, not stored) and flips the switches back.
 *
 * The stored text is untrusted: a wrong version, bad JSON or an unavailable storage (private
 * window, blocked site data) all read as "nothing remembered", and a write that fails is ignored.
 */

import { els } from "./dom.js";
import { IS_CAREER, LEAGUE } from "./data.js";

const SCHEMA_VERSION = 1;

// The switches by the name they are stored under.
const SWITCHES = {
  labels: () => els.labelsToggle,
  logos: () => els.logosToggle,
  notes: () => els.metricNotesToggle,
};

export function viewKey() {
  return `${LEAGUE.key}-${IS_CAREER ? "career" : "season"}`;
}

function storageKey() {
  return `linesshines.prefs.v${SCHEMA_VERSION}.${viewKey()}`;
}

function emptyPreferences() {
  return { version: SCHEMA_VERSION, axes: {}, switches: {} };
}

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readPreferences() {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey()));
    if (!isPlainObject(parsed) || parsed.version !== SCHEMA_VERSION) return emptyPreferences();

    return {
      version: SCHEMA_VERSION,
      axes: isPlainObject(parsed.axes) ? parsed.axes : {},
      switches: isPlainObject(parsed.switches) ? parsed.switches : {},
    };
  } catch {
    return emptyPreferences();
  }
}

function writePreferences(preferences) {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(preferences));
  } catch {
    // Storage is full or blocked: the page simply does not remember.
  }
}

// The remembered { x, y } of a category and position, or null.
export function rememberedAxes(category, position) {
  const pair = (readPreferences().axes[category] || {})[position];
  if (!isPlainObject(pair) || typeof pair.x !== "string" || typeof pair.y !== "string") return null;

  return { x: pair.x, y: pair.y };
}

export function rememberAxes(category, position, x, y) {
  const preferences = readPreferences();

  preferences.axes[category] = { ...(isPlainObject(preferences.axes[category]) ? preferences.axes[category] : {}) };
  preferences.axes[category][position] = { x, y };
  writePreferences(preferences);
}

export function forgetAxes(category, position) {
  const preferences = readPreferences();
  const forCategory = preferences.axes[category];
  if (!isPlainObject(forCategory) || !(position in forCategory)) return;

  delete forCategory[position];
  writePreferences(preferences);
}

// Remembers every flip of a switch. The remembered state itself is put back by the inline script
// in index.html, before the first paint; it is set again here so the switches are right even if
// that script did not run.
export function restoreAndWatchSwitches() {
  const remembered = readPreferences().switches;

  Object.entries(SWITCHES).forEach(([name, getElement]) => {
    const element = getElement();
    if (typeof remembered[name] === "boolean") element.checked = remembered[name];

    element.addEventListener("change", () => {
      const preferences = readPreferences();
      preferences.switches[name] = element.checked;
      writePreferences(preferences);
    });
  });
}
