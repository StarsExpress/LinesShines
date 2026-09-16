/* Fuzzy-match engine (prefix/substring/token-prefix/Ratcliff-Obershelp) plus
 * the shared search-pool logic. Hand-rolled on purpose (see CLAUDE.md) — no
 * npm dependency. Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3
 * step 3.
 *
 * Deviates from the brief's literal file listing in one spot: searchPlayers()
 * (the Players-filter-specific wrapper around searchPlayersExcluding(), using
 * the filter's own selectedPlayers Map as its exclusion set) now lives in
 * filters.js instead of here, since it needs selectedPlayers — filters.js
 * state — and search.js must not depend on filters.js (filters.js already
 * depends on search.js). searchPlayersExcluding(), the actual shared engine
 * both the Players filter and the Merge Create/Edit popups call into, stays
 * here exactly as the brief specifies.
 */
import { els } from "./dom.js";
import {
  metadata,
  playerPoolCategory,
  playerPoolRecords,
  positionPool,
  appliedFilters,
} from "./data.js";

export const NAME_SUFFIXES = new Set(["Jr.", "Jr", "II", "III", "IV", "V", "Sr.", "Sr"]);

export function parsePlayerName(fullName) {
  const parts = (fullName || "").split(" ").filter(Boolean);
  let suffix = null;

  if (parts.length >= 3 && NAME_SUFFIXES.has(parts[parts.length - 1])) {
    suffix = parts.pop();
  }

  const first = parts[0] || "";
  const last = parts.length > 1 ? parts.slice(1).join(" ") : "";
  return { first, last, suffix };
}

// Ratcliff/Obershelp ratio — same algorithm as Python's stdlib
// difflib.SequenceMatcher(None, a, b).ratio(), reimplemented here since
// there's no equivalent in the browser and pulling in a fuzzy-match
// dependency (Fuse.js etc.) for a fallback layer that only matters for
// typos is overkill. Only reached for short (name-token-length) strings, so
// O(n*m) cost here is negligible.
export function longestMatchSize(a, b, alo, ahi, blo, bhi) {
  let besti = alo, bestj = blo, bestsize = 0;
  let j2len = {};

  for (let i = alo; i < ahi; i++) {
    const newJ2len = {};

    for (let j = blo; j < bhi; j++) {
      if (a[i] === b[j]) {
        const k = (j2len[j - 1] || 0) + 1;
        newJ2len[j] = k;

        if (k > bestsize) {
          besti = i - k + 1;
          bestj = j - k + 1;
          bestsize = k;
        }
      }
    }

    j2len = newJ2len;
  }

  return [besti, bestj, bestsize];
}

export function matchingCharCount(a, b) {
  const queue = [[0, a.length, 0, b.length]];
  let total = 0;
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = longestMatchSize(a, b, alo, ahi, blo, bhi);
    if (k) {
      total += k;
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  return total;
}

export function sequenceRatio(a, b) {
  if (!a.length && !b.length) return 1;
  return (2 * matchingCharCount(a, b)) / (a.length + b.length);
}

// Layered match strategy (deliberately not Levenshtein — the wrong tool for
// prefix-driven autocomplete): a prefix match beats a substring match beats
// a token-prefix match beats a fuzzy/typo fallback. Returns a [layer, tiebreak]
// tuple (lower sorts first) or null for no match at all. Token split includes
// "-" (not just whitespace) so a query landing after the hyphen in a compound
// last name like "Norman-Lott" still hits Layer 2 as a token-prefix.
export function matchScore(query, candidate) {
  if (!query || !candidate) return null;
  const q = query.toLowerCase();
  const c = candidate.toLowerCase();

  if (c.startsWith(q)) return [0, c.length];

  const idx = c.indexOf(q);
  if (idx !== -1) return [1, idx];

  const tokens = c.split(/[\s-]+/);
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith(q)) return [2, i];
  }

  const ratio = sequenceRatio(q, c);
  if (ratio > 0.75) return [3, -ratio];

  return null;
}

export function compareScores(a, b) {
  return a[0] !== b[0] ? a[0] - b[0] : a[1] - b[1];
}

// Scores one player against every whitespace-split token of the query — a
// candidate passes if ANY token matches ANY of first/last/suffix (OR, not
// AND), so "will ander" and "ander jr" both hit "Will Anderson Jr." even
// though neither token alone is the full name. Ranking signals, in priority
// order (see searchPlayers' sort): totalHits (how many query tokens matched
// at all) > nameHits (how many matched first/last specifically — a suffix
// hit doesn't count here, which is what makes "jr" alone rank below a token
// that hit an actual name) > bestScore (the best individual matchScore
// across every matched token).
export function scorePlayerAgainstQuery(queryTokens, playerRecord) {
  const { first, last, suffix } = parsePlayerName(playerRecord.player);

  let totalHits = 0;
  let nameHits = 0;
  let bestScore = null;

  for (const token of queryTokens) {
    const firstScore = matchScore(token, first);
    const lastScore = matchScore(token, last);
    const suffixScore = suffix ? matchScore(token, suffix) : null;

    const nameScores = [firstScore, lastScore].filter((s) => s !== null);
    const allScores = [firstScore, lastScore, suffixScore].filter((s) => s !== null);

    if (allScores.length > 0) {
      totalHits++;
      if (nameScores.length > 0) nameHits++;

      const tokenBest = allScores.slice().sort(compareScores)[0];
      if (bestScore === null || compareScores(tokenBest, bestScore) < 0) {
        bestScore = tokenBest;
      }
    }
  }

  if (totalHits === 0) return null;
  return { totalHits, nameHits, bestScore };
}

// playerPoolRecords/playerPoolCategory (rather than currentRecords/
// currentSliceCategory) so this always reflects the pending category —
// updatePlayerPool() keeps both live on every category/season/position
// change, independent of whether that change has been Applied yet.
// playerPoolRecords now holds every position in the category (see
// fetchSlice), so this also scopes to the pending position — otherwise a
// query typed while Position=ED would start suggesting DI players too.
export function qualifyingPlayerPool() {
  if (!playerPoolCategory) return [];
  const cat = metadata[playerPoolCategory];
  const minThreshold = Number(els.thresholdNumber.value);
  return playerPoolRecords.filter(
    (r) => r.position === els.position.value && r[cat.threshold_field] >= minThreshold
  );
}

// Same pool as qualifyingPlayerPool() but without the threshold cut — the
// below-threshold-matches popup fuzzy-matches against this instead, so a
// name that exists but falls under the current threshold can still be told
// apart from a name that doesn't exist at all. Deliberately a separate pool
// rather than threading a "skip the threshold check" flag through
// qualifyingPlayerPool() itself, so the normal dropdown's
// searchPlayers(query, qualifyingPlayerPool()) call site is untouched.
export function fullPlayerPool() {
  if (!playerPoolCategory) return [];
  return playerPoolRecords.filter((r) => r.position === els.position.value);
}

// Top `topK` matches for `query` among `pool`, excluding any player key in
// `excludeKeys`. Search runs against the full "player" field (e.g. "Will
// Anderson Jr."), never "abbr_name" ("W. Anderson Jr.") — abbr_name exists
// purely for chart-label rendering and would make a query like "will" fail
// to match. Shared by the Players filter (searchPlayers below, excluding
// already-selected chips) and the Merge Card Edit popup
// (BLUEPRINT_PinnedPlayers.md §5, same fuzzy-match style, its own
// exclusion set) so both stay on exactly one matching engine.
export function searchPlayersExcluding(query, pool, excludeKeys, topK = 8) {
  const queryTokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (queryTokens.length === 0) return [];

  const scored = pool
    .filter((record) => !excludeKeys.has(record.player))
    .map((record) => ({ record, result: scorePlayerAgainstQuery(queryTokens, record) }))
    .filter((x) => x.result !== null);

  scored.sort((a, b) => {
    if (a.result.totalHits !== b.result.totalHits) return b.result.totalHits - a.result.totalHits;
    if (a.result.nameHits !== b.result.nameHits) return b.result.nameHits - a.result.nameHits;

    const cmp = compareScores(a.result.bestScore, b.result.bestScore);
    if (cmp !== 0) return cmp;

    return a.record.player.localeCompare(b.record.player);
  });

  return scored.slice(0, topK).map((x) => x.record);
}

// Shared pool for every Pinned Players fuzzy-search box — the Single
// Cards add-search, the Create-merge popup, and the Edit-merge popup
// (BLUEPRINT_PinnedPlayers.md v1.2.0 §4: never cross-position, always
// "the same pool the plot is showing"). Just positionPool() locked to
// appliedFilters.position rather than an arbitrary position argument.
export function pcsSearchPool() {
  return positionPool(appliedFilters.position);
}
