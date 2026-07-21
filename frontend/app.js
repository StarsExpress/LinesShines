/* LinesShines · 鋒光.
 * Talks to the FastAPI backend for metadata + per-slice records:
 *   GET /api/metadata
 *   GET /api/pass_rush?season=&position=
 *   GET /api/pass_block?season=&position=
 * Filtering (min-snap threshold), axis choice, and label toggle all run
 * client-side against a small in-memory cache of already-fetched slices.
 */

// Team logos live next to LinesShines/logos/ — the FastAPI service exposes
// them under /logos/ (see main.py static mount) once the frontend is
// deployed inside the LinesShines repo.
const LOGO_PATH = (team) => `logos/${team}.png`;

const els = {
  category: document.getElementById("category-select"),
  season: document.getElementById("season-select"),
  position: document.getElementById("position-select"),
  xMetric: document.getElementById("x-metric-select"),
  yMetric: document.getElementById("y-metric-select"),
  threshold: document.getElementById("threshold-slider"),
  thresholdNumber: document.getElementById("threshold-number"),
  applyBtn: document.getElementById("apply-filters"),
  savePngBtn: document.getElementById("save-png-btn"),
  thresholdFieldLabel: document.getElementById("threshold-field-label"),
  labelsToggle: document.getElementById("labels-toggle"),
  logosToggle: document.getElementById("logos-toggle"),
  teamsControl: document.querySelector(".control-teams"),
  teamsBtn: document.getElementById("teams-toggle-btn"),
  teamsSummary: document.getElementById("teams-select-summary"),
  teamsDropdown: document.getElementById("teams-dropdown"),
  teamsChecklist: document.getElementById("teams-checklist"),
  teamsSelectAll: document.getElementById("teams-select-all"),
  teamsSelectNone: document.getElementById("teams-select-none"),
  playersControl: document.getElementById("players-control"),
  playersBtn: document.getElementById("players-toggle-btn"),
  playersSummary: document.getElementById("players-select-summary"),
  playersPanel: document.getElementById("players-panel"),
  playersField: document.getElementById("players-field"),
  playersChips: document.getElementById("players-chips"),
  playersInput: document.getElementById("players-input"),
  playersDropdown: document.getElementById("players-dropdown"),
  chart: document.getElementById("chart"),
  chartPanel: document.querySelector(".chart-panel"),
  emptyState: document.getElementById("empty-state"),
  logoPreload: document.getElementById("logo-preload"),
  filtersToggle: document.getElementById("toggle-filters"),
  filtersDrawer: document.getElementById("filters-drawer"),
  scoutCard: document.getElementById("scout-card"),
  scoutEmpty: document.getElementById("scout-card-empty"),
  scoutBody: document.getElementById("scout-card-body"),
  scoutLogo: document.getElementById("scout-logo"),
  scoutBadge: document.getElementById("scout-badge"),
  scoutName: document.getElementById("scout-name"),
  scoutMeta: document.getElementById("scout-meta"),
  scoutStats: document.getElementById("scout-stats"),
  scoutClose: document.getElementById("scout-close"),
  scoutDragHandle: document.getElementById("scout-drag-handle"),
};

let metadata = null;                 // /api/metadata payload
const sliceCache = new Map();        // key = `${category}:${season}:${position}` → records[]
let currentRecords = [];             // records for the current slice (all threshold values)
let currentFiltered = [];            // records >= threshold (what the chart shows)

// Which category's schema currentRecords actually matches. Tracked
// separately from els.category.value because a pending (not-yet-Applied)
// category switch changes els.category.value immediately while
// currentRecords still holds the previous category's rows until Apply
// re-runs loadCurrentSlice() — code that reads currentRecords (the Players
// pool, see qualifyingPlayerPool()) needs the category that actually
// matches the data in hand, not the one the dropdown currently shows.
let currentSliceCategory = null;

// Records for whatever category/season/position the controls are *currently
// set to* (pending, not necessarily Applied yet) — feeds only the Players
// search pool (qualifyingPlayerPool()), kept live by updatePlayerPool() on
// every category/season/position change so switching Position immediately
// changes which players the search box will suggest, rather than waiting
// for Apply the way the chart itself does. Deliberately separate from
// currentRecords/currentSliceCategory above, which stay Apply-gated.
let playerPoolRecords = [];
let playerPoolCategory = null;

// Players filter: full player name ("player", not the abbreviated display
// name) → record, in selection order. Live/pending like the Teams
// checklist — edited freely via chips, only takes effect on the chart once
// Apply snapshots it into appliedFilters.players (see currentFilterState()).
const selectedPlayers = new Map();

// Snapshot of {category, season, position, xMetric, yMetric, threshold} the
// chart was last actually rendered with. Every one of those controls can be
// changed freely without touching the chart — render() and showScoutCard()
// read from this snapshot, never live off the controls directly — so the
// Apply button is what commits a batch of changes together, and an
// unrelated render() trigger (the label/logo toggles) can't accidentally
// leak in a half-picked axis or threshold that hasn't been applied yet.
let appliedFilters = null;
let pinnedIndex = null;
let logoRelayoutGuard = false;       // suppresses our own relayout from re-triggering itself

// True right after page load and right after a category switch — both cases
// where the threshold should snap to that category's configured default
// rather than carrying over a value from a different threshold_field scale
// (PR Opp vs Non Spike PB Snaps aren't comparable). Season/position changes
// within the same category leave this false, so the user's value persists.
// If the user manually edits the threshold slider/number while a category
// switch is still pending (not yet Applied), that's an explicit override —
// it clears this flag so applyFilters() doesn't clobber it with the new
// category's default.
let resetThresholdOnNextRange = true;

// Decoded Image objects, keyed by team code, filled once at page load so
// filter changes never wait on the browser to re-resolve/decode /logos/*.png
// again — layout.images and the scout card both just point at these.
const logoCache = {};

async function preloadLogos() {
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
function logoSrc(team) {
  return logoCache[team] ? logoCache[team].src : LOGO_PATH(team);
}

// Logos are sized as a fixed pixel target rather than a fraction of plot
// width so a dense mobile chart doesn't inherit same visual scale as a 1100px desktop chart.
// Mobile gets a smaller absolute size to cut overlap.
// Player labels default to on, logos take up less room and collision is smaller.
function targetLogoPx() {
  return window.innerWidth < 860 ? 16 : 26;
}

async function loadMetadata() {
  const res = await fetch("/api/metadata");
  if (!res.ok) throw new Error(`GET /api/metadata → ${res.status}`);
  metadata = await res.json();

  populateCategoryDependentControls();
  populateTeamsChecklist();
  attachEvents();
  await loadCurrentSlice();
  playerPoolRecords = currentRecords;
  playerPoolCategory = currentSliceCategory;
  appliedFilters = currentFilterState();

  els.logoPreload.hidden = false;
  await preloadLogos();
  els.logoPreload.hidden = true;

  render();
  updatePendingState();
}

function currentCategoryMeta() {
  return metadata[els.category.value];
}

// The category metadata for whatever's actually plotted right now, as
// opposed to currentCategoryMeta() which tracks the (possibly still
// pending, not-yet-applied) category select.
function appliedCategoryMeta() {
  return metadata[appliedFilters.category];
}

function currentFilterState() {
  return {
    category: els.category.value,
    season: els.season.value,
    position: els.position.value,
    xMetric: els.xMetric.value,
    yMetric: els.yMetric.value,
    threshold: els.thresholdNumber.value,
    // Joined into a comparable string (not a bare array) so the `!==`
    // check in filtersArePending() works the same way it does for every
    // other primitive-valued control — two different array references
    // would never compare equal even with identical contents.
    teams: selectedTeamCodes().sort().join(","),
    players: Array.from(selectedPlayers.keys()).sort().join(","),
  };
}

function allTeamCodes() {
  return Array.from(els.teamsChecklist.querySelectorAll("input[type=checkbox]")).map((cb) => cb.value);
}

function selectedTeamCodes() {
  return Array.from(els.teamsChecklist.querySelectorAll("input[type=checkbox]:checked")).map((cb) => cb.value);
}

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
const CONFERENCES = {
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

function teamOptionRow(code) {
  const label = document.createElement("label");
  label.className = "team-option";

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.value = code;
  cb.checked = true;

  const logo = document.createElement("img");
  logo.className = "team-option-logo";
  logo.src = logoSrc(code);
  logo.alt = "";
  logo.loading = "lazy";
  logo.onerror = () => logo.replaceWith(teamSwatch(code));

  const text = document.createElement("span");
  text.textContent = code;

  label.append(cb, logo, text);
  return label;
}

function populateTeamsChecklist() {
  els.teamsChecklist.innerHTML = "";

  Object.entries(CONFERENCES).forEach(([conference, divisions]) => {
    const column = document.createElement("div");
    column.className = "teams-column";

    const columnHeader = document.createElement("div");
    columnHeader.className = "teams-column-header";
    columnHeader.textContent = conference;
    column.appendChild(columnHeader);

    Object.entries(divisions).forEach(([division, codes]) => {
      const group = document.createElement("div");
      group.className = "teams-division";

      const divisionHeader = document.createElement("div");
      divisionHeader.className = "teams-division-header";
      divisionHeader.textContent = division;
      group.appendChild(divisionHeader);

      // Codes are already listed ascending within each division above.
      codes.forEach((code) => group.appendChild(teamOptionRow(code)));
      column.appendChild(group);
    });

    els.teamsChecklist.appendChild(column);
  });

  updateTeamsSummary();
}

function updateTeamsSummary() {
  const selected = selectedTeamCodes();
  const total = allTeamCodes().length;
  if (selected.length === total) els.teamsSummary.textContent = "All Teams";
  else if (selected.length === 0) els.teamsSummary.textContent = "No Teams";
  else if (selected.length === 1) els.teamsSummary.textContent = teamName(selected[0]);
  else els.teamsSummary.textContent = `${selected.length} Teams`;
}

function openTeamsDropdown() {
  els.teamsDropdown.hidden = false;
  els.teamsBtn.setAttribute("aria-expanded", "true");
}

function closeTeamsDropdown() {
  els.teamsDropdown.hidden = true;
  els.teamsBtn.setAttribute("aria-expanded", "false");
}

// --- Players autocomplete -----------------------------------------------
//
// PFF's "Player" column is "{first} {last}" or "{first} {last} {suffix}",
// where either name can itself be multi-word ("Andrew Van Ginkel", "D.J.
// Wonnum"). Splitting on token count is ambiguous — a suffix whitelist is
// the only reliable signal, since a compound last name and a suffix both
// just look like "more tokens after the first".
const NAME_SUFFIXES = new Set(["Jr.", "Jr", "II", "III", "IV", "V", "Sr.", "Sr"]);

function parsePlayerName(fullName) {
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
// the O(n*m) cost here is negligible.
function longestMatchSize(a, b, alo, ahi, blo, bhi) {
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

function matchingCharCount(a, b) {
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

function sequenceRatio(a, b) {
  if (!a.length && !b.length) return 1;
  return (2 * matchingCharCount(a, b)) / (a.length + b.length);
}

// Layered match strategy (deliberately not Levenshtein — the wrong tool for
// prefix-driven autocomplete): a prefix match beats a substring match beats
// a token-prefix match beats a fuzzy/typo fallback. Returns a [layer, tiebreak]
// tuple (lower sorts first) or null for no match at all. Token split includes
// "-" (not just whitespace) so a query landing after the hyphen in a compound
// last name like "Norman-Lott" still hits Layer 2 as a token-prefix.
function matchScore(query, candidate) {
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

function compareScores(a, b) {
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
function scorePlayerAgainstQuery(queryTokens, playerRecord) {
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
function qualifyingPlayerPool() {
  if (!playerPoolCategory) return [];
  const cat = metadata[playerPoolCategory];
  const minThreshold = Number(els.thresholdNumber.value);
  return playerPoolRecords.filter((r) => r[cat.threshold_field] >= minThreshold);
}

// Top `topK` matches for `query` among `pool`, excluding players already
// selected (no point suggesting a chip that already exists). Search runs
// against the full "player" field (e.g. "Will Anderson Jr."), never
// "abbr_name" ("W. Anderson Jr.") — abbr_name exists purely for chart-label
// rendering and would make a query like "will" fail to match.
function searchPlayers(query, pool, topK = 8) {
  const queryTokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (queryTokens.length === 0) return [];

  const scored = pool
    .filter((record) => !selectedPlayers.has(record.player))
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

function renderPlayerChips() {
  els.playersChips.innerHTML = "";
  selectedPlayers.forEach((record, key) => {
    const label = record.abbr_name || record.player;
    const chip = document.createElement("span");
    chip.className = "player-chip";

    const text = document.createElement("span");
    text.textContent = label;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "player-chip-remove";
    removeBtn.setAttribute("aria-label", `Remove ${label}`);
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => {
      selectedPlayers.delete(key);
      renderPlayerChips();
      updatePendingState();
    });

    chip.append(text, removeBtn);
    els.playersChips.appendChild(chip);
  });
  updatePlayersSummary();
}

// Mirrors updateTeamsSummary() — the collapsed button's label, shown while
// .players-panel is closed so the chip list itself never has to fit inside
// the 150px button (see the control-players sizing comment above .control-players).
function updatePlayersSummary() {
  const count = selectedPlayers.size;
  if (count === 0) els.playersSummary.textContent = "No Players";
  else if (count === 1) {
    const [[, record]] = selectedPlayers;
    els.playersSummary.textContent = record.abbr_name || record.player;
  } else els.playersSummary.textContent = `${count} Players`;
}

function openPlayersPanel() {
  els.playersPanel.hidden = false;
  els.playersBtn.setAttribute("aria-expanded", "true");
  els.playersInput.focus();
}

function closePlayersPanel() {
  els.playersPanel.hidden = true;
  els.playersBtn.setAttribute("aria-expanded", "false");
  hidePlayersDropdown();
}

function hidePlayersDropdown() {
  els.playersDropdown.hidden = true;
  els.playersDropdown.innerHTML = "";
}

function renderPlayersDropdown(matches) {
  els.playersDropdown.innerHTML = "";
  if (!matches.length) {
    hidePlayersDropdown();
    return;
  }

  matches.forEach((record) => {
    const opt = document.createElement("button");
    opt.type = "button";
    opt.className = "player-option";

    // Full name here (unlike the abbreviated chip label) — the dropdown is
    // a disambiguation UI where "Anderson" alone could mean several
    // players, so the full name plus team logo carries more identifying
    // context than the compact "W. Anderson Jr." the chip uses once picked.
    const name = document.createElement("span");
    name.className = "player-option-name";
    name.textContent = record.player;

    const team = document.createElement("span");
    team.className = "player-option-team";

    const logo = document.createElement("img");
    logo.className = "player-option-logo";
    logo.src = logoSrc(record.team);
    logo.alt = "";
    logo.loading = "lazy";
    logo.onerror = () => logo.replaceWith(teamSwatch(record.team));

    const code = document.createElement("span");
    code.textContent = record.team;

    team.append(logo, code);
    opt.append(name, team);
    opt.addEventListener("click", () => {
      selectedPlayers.set(record.player, record);
      renderPlayerChips();
      els.playersInput.value = "";
      hidePlayersDropdown();
      updatePendingState();
      els.playersInput.focus();
    });

    els.playersDropdown.appendChild(opt);
  });

  els.playersDropdown.hidden = false;
}

function runPlayersSearch() {
  const query = els.playersInput.value.trim();
  if (!query) {
    hidePlayersDropdown();
    return;
  }
  renderPlayersDropdown(searchPlayers(query, qualifyingPlayerPool()));
}

// Called whenever the qualifying pool can have shrunk — live threshold
// edits, and live category/season/position changes via updatePlayerPool()
// (e.g. switching Position from ED to DI drops any ED-only chip immediately,
// since it's no longer in the new position's pool) — so a selected player
// who no longer clears the bar (or no longer exists in the new slice)
// silently loses their chip instead of lingering as a selection that can't
// actually take effect.
function prunePlayerSelections() {
  const poolKeys = new Set(qualifyingPlayerPool().map((r) => r.player));
  let changed = false;
  selectedPlayers.forEach((_, key) => {
    if (!poolKeys.has(key)) {
      selectedPlayers.delete(key);
      changed = true;
    }
  });
  if (changed) renderPlayerChips();
}

function filtersArePending() {
  if (!appliedFilters) return false;
  const current = currentFilterState();
  return Object.keys(current).some((key) => current[key] !== appliedFilters[key]);
}

// Lights up the Apply button whenever any batched control (category,
// season, position, either axis, or threshold) holds a value the chart
// hasn't been rendered with yet — the only feedback the user gets now that
// none of these re-render on their own.
function updatePendingState() {
  els.applyBtn.classList.toggle("pending", filtersArePending());
}

function populateCategoryDependentControls() {
  const cat = currentCategoryMeta();

  // Positions
  els.position.innerHTML = "";
  Object.entries(cat.positions).forEach(([code, label]) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${label}`;
    els.position.appendChild(opt);
  });

  // Seasons (already sorted desc by the API)
  els.season.innerHTML = "";
  cat.seasons.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    els.season.appendChild(opt);
  });

  // Metrics
  const metricKeys = Object.keys(cat.metrics);
  [els.xMetric, els.yMetric].forEach((select) => {
    select.innerHTML = "";
    metricKeys.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      select.appendChild(opt);
    });
  });
  // Distinct defaults, mirroring the pipeline's canonical query pairs
  // (e.g. TPS Win Rate vs. plain Win Rate). Pass rush gets an explicit
  // Win Rate / Havoc Rate pairing; pass block falls back to the generic
  // TPS-vs-non-TPS heuristic.
  if (els.category.value === "pass_rush" && metricKeys.includes("Win Rate") && metricKeys.includes("Havoc Rate")) {
    els.xMetric.value = "Win Rate";
    els.yMetric.value = "Havoc Rate";
  } else {
    els.xMetric.value = metricKeys.find((m) => m.startsWith("TPS")) || metricKeys[0];
    els.yMetric.value = metricKeys.find((m) => !m.startsWith("TPS")) || metricKeys[1] || metricKeys[0];
  }

  els.thresholdFieldLabel.textContent = thresholdFieldLabel(cat);
}

// Shared by loadCurrentSlice() (Apply-gated, drives the chart) and
// updatePlayerPool() (live, drives only the Players search pool) — both
// just need the records for a given category/season/position, memoized in
// sliceCache so switching back to an already-seen combination is free.
async function fetchSlice(category, season, position) {
  const key = `${category}:${season}:${position}`;
  if (!sliceCache.has(key)) {
    const url = `/api/${category}?season=${season}&position=${encodeURIComponent(position)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
    const data = await res.json();
    sliceCache.set(key, data.records || []);
  }
  return sliceCache.get(key);
}

async function loadCurrentSlice() {
  const category = els.category.value;
  const season = Number(els.season.value);
  const position = els.position.value;
  currentRecords = await fetchSlice(category, season, position);
  currentSliceCategory = category;
  updateThresholdRange();
}

// Mirrors loadCurrentSlice(), but for whatever category/season/position the
// controls are pending on right now, and never touches currentRecords/
// currentSliceCategory/updateThresholdRange — those stay reserved for the
// last Applied slice the chart is actually showing. Fired on every
// category/season/position change (see attachEvents()) so the Players
// dropdown always searches the position currently selected, e.g. switching
// from ED to DI immediately drops ED-only players like Derick Hall from the
// suggestions and starts surfacing DI players like Dexter Lawrence instead,
// without waiting for Apply.
async function updatePlayerPool() {
  const category = els.category.value;
  const season = Number(els.season.value);
  const position = els.position.value;
  playerPoolRecords = await fetchSlice(category, season, position);
  playerPoolCategory = category;
  prunePlayerSelections();
  runPlayersSearch();
}

function updateThresholdRange() {
  const cat = currentCategoryMeta();
  const values = currentRecords.map((r) => r[cat.threshold_field]).filter((v) => v != null);
  const maxVal = values.length ? Math.max(...values) : 100;
  const max = Math.ceil(maxVal / 10) * 10;

  els.threshold.min = 0;
  els.threshold.max = max;
  els.threshold.step = 5;

  if (resetThresholdOnNextRange) {
    const defaultValue = cat.default_threshold ?? 0;
    els.threshold.value = Math.min(Math.max(defaultValue, 0), max);
    resetThresholdOnNextRange = false;
  } else if (Number(els.threshold.value) > max) {
    // Season/position change within the same category — keep the user's
    // value, only clamping if the new slice's max no longer covers it.
    els.threshold.value = max;
  }

  els.thresholdNumber.min = 0;
  els.thresholdNumber.max = max;
  els.thresholdNumber.value = els.threshold.value;
}

// Metric labels can contain "%" or "/" (e.g. "Pressure %"), which aren't
// safe/clean in a downloaded filename — collapse any run of non-alphanumeric
// characters to a single underscore.
function sanitizeForFilename(value) {
  return String(value).trim().replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  if (n === 0) return null;
  if (n % 2 === 1) return sorted[(n - 1) / 2];
  return Math.round(((sorted[n / 2 - 1] + sorted[n / 2]) / 2) * 10) / 10;
}

// Shared by the threshold control's own label and the chart subtitle, so
// the two can't drift out of sync with each other.
function thresholdFieldLabel(cat) {
  return cat.threshold_field === "PR Opp" ? "pass rush opportunities" : "non-spike pass block snaps";
}

function formatValue(value, meta) {
  if (value == null) return "—";
  const unit = meta && meta.unit ? meta.unit : "";
  return `${value}${unit}`;
}

function ordinal(n) {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

// Rank (1 = best) and percentile (100 = best) for `value` on metric `key`
// among `pool`, respecting the metric's higher/lower-is-better direction
// (see PASS_RUSH_METRICS / PASS_BLOCK_METRICS in main.py). Ties share a
// rank — competition ranking, so equal values don't get an arbitrary
// tiebreak order — and the pool is exactly `currentFiltered`, i.e. the
// same season/position/category/threshold population the chart is
// currently plotting, not the unfiltered slice.
function rankAndPercentile(pool, key, higherIsBetter, value) {
  if (value == null) return null;
  const values = pool.map((r) => r[key]).filter((v) => v != null);
  const n = values.length;
  if (n < 2) return null;
  const better = (v) => (higherIsBetter ? v > value : v < value);
  const rank = values.filter(better).length + 1;
  const percentile = Math.round(((n - rank) / (n - 1)) * 100);
  return { rank, n, percentile };
}

function teamColor(code) {
  const t = metadata.teams && metadata.teams[code];
  return (t && t.primary_color) || "#6b7a6f";
}

function teamName(code) {
  const t = metadata.teams && metadata.teams[code];
  return (t && t.full_name) || code;
}

// Fallback swatch for the teams-dropdown checklist when a team's logo file
// 404s — mirrors showScoutCard()'s scoutLogo.onerror treatment.
function teamSwatch(code) {
  const span = document.createElement("span");
  span.className = "team-swatch";
  span.style.background = teamColor(code);
  return span;
}

// sizex/sizey for layout.images are in DATA units, not pixels, so logo size
// needs recomputing whenever the visible axis range or plot size changes
// (zoom, pan, resize) — otherwise logos balloon, shrink, or drift off their
// intended on-screen scale.
// `isDimmed` (aligned index-for-index with `records`) fades logos for
// players whose team isn't in the current Teams selection, rather than
// dropping them from the plot entirely — see DIM_OPACITY.
function computeLogoImages(chartDiv, records, xKey, yKey, isDimmed) {
  const fullLayout = chartDiv._fullLayout;
  const xAxis = fullLayout && fullLayout.xaxis;
  const yAxis = fullLayout && fullLayout.yaxis;
  if (!xAxis || !yAxis || !xAxis._length || !yAxis._length) return [];

  // Target size in pixels (same for x and y so logos render square), then
  // converted back to each axis's data units.
  const targetPx = targetLogoPx();
  const xRangeSpan = Math.abs(xAxis.range[1] - xAxis.range[0]);
  const yRangeSpan = Math.abs(yAxis.range[1] - yAxis.range[0]);
  const sizex = targetPx * (xRangeSpan / xAxis._length);
  const sizey = targetPx * (yRangeSpan / yAxis._length);

  return records.map((r, i) => ({
    source: logoSrc(r.team),
    xref: "x", yref: "y",
    x: r[xKey], y: r[yKey],
    sizex, sizey,
    xanchor: "center", yanchor: "middle",
    layer: "above",
    opacity: isDimmed && isDimmed[i] ? DIM_OPACITY.logo : 1,
  }));
}

// Approximates adjustText's declutter effect without the library: process
// labels in descending threshold_field order (so star players get first
// claim), keep a label only if its approximate pixel bounding box doesn't
// overlap one already kept, blank the rest.
// `isDimmed` (aligned index-for-index with `records`) pushes every
// highlighted (non-dimmed) player's label ahead of every dimmed player's,
// regardless of threshold_field — a Teams selection should never lose its
// own labels to a bigger name outside the selection.
function computeKeptLabels(chartDiv, records, xKey, yKey, thresholdField, isDimmed) {
  const fullLayout = chartDiv._fullLayout;
  const xAxis = fullLayout && fullLayout.xaxis;
  const yAxis = fullLayout && fullLayout.yaxis;
  if (!xAxis || !yAxis || typeof xAxis.l2p !== "function") {
    return records.map(() => true);
  }

  const CHAR_WIDTH = 6.5; // approx advance width, IBM Plex Mono @ 10px
  const LABEL_HEIGHT = 12;
  const LABEL_GAP = 10;   // vertical offset from marker center to "bottom center" text
  // Shrink each box by this fraction on every side before the collision test,
  // so two labels have to genuinely overlap (not just sit close) to bump one
  // another — trades a bit of edge-touching/kerning overlap for showing more
  // names in dense clusters.
  const OVERLAP_TOLERANCE = 0.35;
  // Comfortably larger than any real threshold_field value, so it dominates
  // the sort without needing a second sort key.
  const HIGHLIGHT_BOOST = 1e9;

  const boxes = records.map((r, i) => {
    const label = r.abbr_name || r.player || "";
    const cx = xAxis.l2p(r[xKey]);
    const top = yAxis.l2p(r[yKey]) + LABEL_GAP;
    const halfWidth = (label.length * CHAR_WIDTH) / 2;
    const shrinkX = halfWidth * OVERLAP_TOLERANCE;
    const shrinkY = (LABEL_HEIGHT / 2) * OVERLAP_TOLERANCE;
    return {
      left: cx - halfWidth + shrinkX, right: cx + halfWidth - shrinkX,
      top: top + shrinkY, bottom: top + LABEL_HEIGHT - shrinkY,
      priority: (isDimmed && isDimmed[i] ? 0 : HIGHLIGHT_BOOST) + (r[thresholdField] ?? 0),
    };
  });

  const order = boxes.map((_, i) => i).sort((a, b) => boxes[b].priority - boxes[a].priority);
  const kept = new Array(records.length).fill(false);
  const placed = [];

  order.forEach((i) => {
    const box = boxes[i];
    const overlaps = placed.some(
      (p) => box.left < p.right && box.right > p.left && box.top < p.bottom && box.bottom > p.top
    );
    if (!overlaps) {
      kept[i] = true;
      placed.push(box);
    }
  });

  return kept;
}

// Teams is a highlight, not a filter — a player whose team isn't selected
// stays on the plot (still visible, still clickable, still counted in the
// median) but fades to these opacities instead of disappearing.
const DIM_OPACITY = { marker: 0.15, logo: 0.22, label: 0.12 };
const LABEL_ALPHA = 0.55; // normal (non-dimmed) player-name opacity

// Teams and Players both only dim, never exclude (see the isDimmed comment
// in render()), so unlike the old Teams-only subtitle this can't just count
// currentFiltered — a reader needs to know *why* a non-highlighted-team
// player might still be sitting on the chart. Falls back to the plain
// "N players ≥ threshold" line when nothing is actually being highlighted
// (all teams selected, no players added) so the common case stays terse.
function highlightSubtitle(cat, records, isDimmed, selectedTeams, selectedPlayerKeys, minThreshold) {
  const fieldLabel = thresholdFieldLabel(cat);
  const totalTeams = allTeamCodes().length;
  const allTeamsSelected = selectedTeams.size === totalTeams;

  const parts = [];
  if (allTeamsSelected) {
    // Every team already selected — Players is the only real filter, no
    // point naming "32 Teams".
  } else if (selectedTeams.size === 0) {
    parts.push("no teams");
  } else if (selectedTeams.size <= 2) {
    parts.push(Array.from(selectedTeams).map(teamName).join(" + "));
  } else {
    parts.push(`${selectedTeams.size} teams`);
  }

  const playerRecords = records.filter((r) => selectedPlayerKeys.has(r.player));
  if (playerRecords.length) {
    const names = playerRecords.map((r) => r.abbr_name || r.player);
    parts.push(names.length <= 2 ? names.join(" + ") : `${names.length} players`);
  }

  const highlightedCount = records.length - isDimmed.filter(Boolean).length;
  const clause = parts.length ? parts.join(" + ") : "nothing";
  return `${records.length} players with at least ${minThreshold} ${fieldLabel}.`;
}

function render() {
  const cat = appliedCategoryMeta();

  const minThreshold = Number(appliedFilters.threshold);
  const selectedTeams = new Set(appliedFilters.teams ? appliedFilters.teams.split(",") : []);
  const selectedPlayerKeys = new Set(appliedFilters.players ? appliedFilters.players.split(",") : []);

  currentFiltered = currentRecords.filter((r) => r[cat.threshold_field] >= minThreshold);
  // Players joins Teams via OR — a player is highlighted if their team is
  // selected OR they were explicitly added, so an explicitly-picked player
  // off a dimmed team still stands out. Empty selectedTeams (Teams → None)
  // with no players picked has both .has() calls return false for every
  // record, which dims everyone uniformly — no special-casing needed.
  const isDimmed = currentFiltered.map((r) => !(selectedTeams.has(r.team) || selectedPlayerKeys.has(r.player)));

  if (currentFiltered.length < 2) {
    els.emptyState.hidden = false;
    Plotly.purge(els.chart);
    els.savePngBtn.disabled = true;
    els.savePngBtn.title = "Load some data first";
    return;
  }
  els.emptyState.hidden = true;
  els.savePngBtn.disabled = false;
  els.savePngBtn.title = "Save chart as PNG";

  const xKey = appliedFilters.xMetric;
  const yKey = appliedFilters.yMetric;
  const xMeta = cat.metrics[xKey] || {};
  const yMeta = cat.metrics[yKey] || {};

  const activeNotes = [];
  if (xMeta.note) activeNotes.push(xMeta.note);
  if (yMeta.note && yMeta.note !== xMeta.note) {
    activeNotes.push(yMeta.note); // avoid dup when both axes use the same metric family
  }

  const xVals = currentFiltered.map((r) => r[xKey]);
  const yVals = currentFiltered.map((r) => r[yKey]);
  const colors = currentFiltered.map((r) => teamColor(r.team));

  const showLabels = els.labelsToggle.checked;
  const showLogos = els.logosToggle.checked;

  const trace = {
    x: xVals,
    y: yVals,
    mode: showLabels ? "markers+text" : "markers",
    type: "scatter",
    text: currentFiltered.map((r) => r.abbr_name || r.player),
    // logos sit on the dot itself, so push labels below to avoid clashing
    textposition: showLogos && showLabels ? "bottom center" : "top center",
    textfont: {
      color: isDimmed.map((dim) => `rgba(241,236,221,${dim ? DIM_OPACITY.label : LABEL_ALPHA})`),
      size: 10,
      family: "IBM Plex Mono, monospace",
    },
    marker: {
      color: colors,
      size: 13,
      // invisible dots still receive hover/click — only the fill disappears —
      // so the scouting card keeps working with logos drawn on top via
      // layout.images (Plotly has no native "image as marker" option). When
      // logos are off, dimmed (unselected-team) markers still fade in place
      // rather than being dropped from the trace.
      opacity: showLogos ? 0 : isDimmed.map((dim) => (dim ? DIM_OPACITY.marker : 1)),
      line: { color: "rgba(15,33,25,0.65)", width: 1 },
    },
    // The scouting card is the hover UI — Plotly's own tooltip would just
    // duplicate it right next to the cursor, so suppress it here. hover/click
    // events still fire with hoverinfo:'none', only the built-in popup dies.
    hoverinfo: "none",
  };

  const xMedian = median(xVals);
  const yMedian = median(yVals);

  const shapes = [
    {
      type: "line", xref: "x", yref: "paper", x0: xMedian, x1: xMedian, y0: 0, y1: 1,
      line: { color: "#a9b6a9", width: 1, dash: "dash" },
    },
    {
      type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: yMedian, y1: yMedian,
      line: { color: "#a9b6a9", width: 1, dash: "dash" },
    },
  ];

  const medianAnnotations = [
    {
      x: xMedian, y: 0, yref: "paper", yanchor: "top", yshift: -6,
      text: `Median: ${xMedian}`, showarrow: false,
      font: { color: "#a9b6a9", size: 10, family: "IBM Plex Mono, monospace" },
    },
    {
      x: 0, xref: "paper", xanchor: "right", xshift: -6, y: yMedian,
      text: `Median: ${yMedian}`, showarrow: false, textangle: -90,
      font: { color: "#a9b6a9", size: 10, family: "IBM Plex Mono, monospace" },
    },
  ];

  // Metric definition callouts (e.g. what "Havoc Rate" means) — only shown
  // when a Havoc-family metric is on an axis, see activeNotes above.
  const isMobile = window.innerWidth < 860;
  const noteAnnotations = activeNotes.map((note, i) => ({
    xref: "paper", yref: "paper",
    x: 1, y: 1 - i * 0.05, // stack multiple notes vertically if both axes have notes
    xanchor: "right", yanchor: "top",
    text: `<i>ⓘ ${note}</i>`,
    showarrow: false,
    font: {
      family: "IBM Plex Mono, monospace",
      size: isMobile ? 9 : 11,
      color: "#a9b6a9",
    },
    bgcolor: "rgba(15,33,25,0.85)", // turf-950 with alpha
    bordercolor: "rgba(211,167,61,0.4)", // faint gold border
    borderwidth: 1,
    borderpad: 6,
  }));

  const annotations = [...medianAnnotations, ...noteAnnotations];

  const reversed = appliedFilters.category === "pass_block"; // lower allowed% is better

  // total_selected counts everyone clearing threshold, not just highlighted teams;
  // Teams dims players rather than removing them (see DIM_OPACITY above),
  // so count shouldn't shrink just because some teams are unchecked.
  const positionLabel = (cat.positions && cat.positions[appliedFilters.position]) || appliedFilters.position;
  const titleText = `${appliedFilters.season} NFL ${positionLabel} ${xKey} & ${yKey}`;
  const subtitleText = highlightSubtitle(cat, currentFiltered, isDimmed, selectedTeams, selectedPlayerKeys, minThreshold);

  const layout = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter, sans-serif", color: "#f1ecdd" },
    // Extra headroom above the plot area (beyond what the title/subtitle
    // text itself needs) so the metric-definition note box — pinned to the
    // plot's own y:1 top edge, not the title block — doesn't sit flush
    // against the subtitle.
    margin: { l: 60, r: 24, t: isMobile ? 96 : 88, b: 56 },
    title: {
      text: titleText,
      font: { family: "Anton, Arial Narrow, sans-serif", size: isMobile ? 16 : 22, color: "#f1ecdd" },
      x: 0.5,
      xanchor: "center",
      subtitle: {
        text: subtitleText,
        font: { family: "IBM Plex Mono, monospace", size: isMobile ? 9 : 12, color: "#a9b6a9" },
      },
    },
    dragmode: false,
    xaxis: {
      // Plotly 3.x requires title as {text: ...} — a bare string is
      // silently ignored (renders as an empty <g class="g-xtitle">).
      title: { text: `${xKey}${xMeta.unit ? " (" + xMeta.unit + ")" : ""}` },
      gridcolor: "rgba(241,236,221,0.08)",
      zerolinecolor: "rgba(241,236,221,0.15)",
      autorange: reversed ? "reversed" : true,
    },
    yaxis: {
      title: { text: `${yKey}${yMeta.unit ? " (" + yMeta.unit + ")" : ""}` },
      gridcolor: "rgba(241,236,221,0.08)",
      zerolinecolor: "rgba(241,236,221,0.15)",
      autorange: reversed ? "reversed" : true,
    },
    shapes,
    annotations,
    hoverlabel: {
      bgcolor: "#1e3d28",
      bordercolor: "#2a4d33",
      font: { family: "IBM Plex Mono, monospace", size: 12, color: "#f1ecdd" },
    },
  };

  function applyLogoImages() {
    if (!showLogos) return;
    const images = computeLogoImages(els.chart, currentFiltered, xKey, yKey, isDimmed);
    if (!images.length) return;
    logoRelayoutGuard = true;
    Plotly.relayout(els.chart, { images }).then(() => {
      logoRelayoutGuard = false;
    });
  }

  // Only declutters when logos are on — with plain colored dots the labels
  // sit right above a small marker and collide far less.
  function applyLabelDeclutter() {
    if (!showLabels || !showLogos) return;
    const kept = computeKeptLabels(els.chart, currentFiltered, xKey, yKey, cat.threshold_field, isDimmed);
    const text = currentFiltered.map((r, i) => (kept[i] ? (r.abbr_name || r.player) : ""));
    Plotly.restyle(els.chart, { text: [text] }, [0]);
  }

  // No `images` key here on purpose — Plotly.react fully replaces
  // layout, so leaving it out clears any logos from a previous render when
  // toggle is off. Sizing needs post-draw axis range, so logos are
  // added in a follow-up relayout once this render settles.
  Plotly.react(els.chart, [trace], layout, {
    displayModeBar: false,
    responsive: true,
    scrollZoom: false,
    doubleClick: false,
  })
    .then(() => {
      applyLogoImages();
      applyLabelDeclutter();
    });

  // Clear stale listeners each render — Plotly.react reuses the same graph
  // div, and every call otherwise adds another copy of the click handler.
  ["plotly_click", "plotly_relayout"].forEach((evt) =>
    els.chart.removeAllListeners?.(evt)
  );

  // Zoom/pan/resize change the axis range, so sizex/sizey (data units) need
  // recomputing to keep logos a constant on-screen size, and label overlaps
  // need re-evaluating since pixel spacing between points also changed.
  // Guard against our own relayout call re-triggering this handler.
  els.chart.on("plotly_relayout", () => {
    if (logoRelayoutGuard) return;
    applyLogoImages();
    applyLabelDeclutter();
  });

  els.chart.on("plotly_click", (e) => {
    const idx = e.points[0].pointIndex;
    if (pinnedIndex === idx) {
      pinnedIndex = null;
      resetScoutCard();
    } else {
      pinnedIndex = idx;
      showScoutCard(currentFiltered[idx]);
    }
  });
}

function showScoutCard(record) {
  const cat = appliedCategoryMeta();
  els.scoutCard.classList.add("is-active");
  els.scoutEmpty.hidden = true;
  els.scoutBody.hidden = false;

  const color = teamColor(record.team);
  els.scoutLogo.src = logoSrc(record.team);
  els.scoutLogo.alt = `${record.team} logo`;
  els.scoutLogo.hidden = false;
  els.scoutBadge.hidden = true;
  els.scoutLogo.onerror = () => {
    els.scoutLogo.hidden = true;
    els.scoutBadge.hidden = false;
    els.scoutBadge.textContent = record.team;
    els.scoutBadge.style.background = color;
  };

  els.scoutName.textContent = record.player;
  els.scoutMeta.textContent = `${teamName(record.team)} · ${record.position}`;

  const xKey = appliedFilters.xMetric;
  const yKey = appliedFilters.yMetric;

  els.scoutStats.innerHTML = "";
  // Three grid children per row (dt, value dd, rank dd) so the grid's
  // row-major auto-placement stays aligned — a row that only emitted two
  // children when it has no rank would shift every following row's columns.
  // Games / the threshold field get an empty rank cell for exactly this
  // reason, not because rank text was omitted by accident.
  const addRow = (label, value, highlighted, rankText) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.className = "scout-stat-value";
    dd.textContent = value;
    if (highlighted) dd.classList.add("is-highlighted");
    const rankDd = document.createElement("dd");
    rankDd.className = "scout-stat-rank";
    rankDd.textContent = rankText || "—";
    els.scoutStats.appendChild(dt);
    els.scoutStats.appendChild(dd);
    els.scoutStats.appendChild(rankDd);
  };

  // Games and the threshold field (PR Opp / Non Spike PB Snaps) are volume
  // stats, not rate metrics — rank/percentile against them wouldn't mean
  // "how well this player performed," so only the metrics loop below gets a
  // rank.
  addRow("Games", record.games);
  addRow(cat.threshold_field, record[cat.threshold_field]);
  Object.entries(cat.metrics).forEach(([key, meta]) => {
    const rank = rankAndPercentile(currentFiltered, key, meta.higher_is_better, record[key]);
    const rankText = rank ? `#${rank.rank}/${rank.n} · ${ordinal(rank.percentile)} pct` : "";
    addRow(key, formatValue(record[key], meta), key === xKey || key === yKey, rankText);
  });
}

function resetScoutCard() {
  els.scoutCard.classList.remove("is-active");
  els.scoutEmpty.hidden = false;
  els.scoutBody.hidden = true;
  // Drop any position a drag left behind so the card starts back at its
  // default top-right corner next time it's opened, rather than wherever
  // the user last dragged it.
  clearScoutCardDragPosition();
}

// Below 860px the scouting card is a static block stacked under the chart
// (see the @media (max-width: 860px) rules in style.css), not a floating
// overlay — dragging only makes sense above that breakpoint, same cutoff
// targetLogoPx() already uses for the desktop/mobile split.
function isDesktopScoutLayout() {
  return window.innerWidth >= 860;
}

// Inline left/top (set by dragging) sit at higher specificity than the
// mobile media query's `top: auto; right: auto;` reset, so they'd otherwise
// survive a resize down to mobile and break the stacked layout. Clearing
// them lets the stylesheet's position rules take back over.
function clearScoutCardDragPosition() {
  els.scoutCard.style.left = "";
  els.scoutCard.style.top = "";
  els.scoutCard.style.right = "";
}

// Drag state for the one pointer currently moving the card, or null. Only
// one drag can be in progress at a time — the pointerId lets move/end
// handlers ignore any other pointer that fires while a drag is active
// (e.g. a second touch point).
let scoutDragState = null;

function beginScoutDrag(e) {
  if (!isDesktopScoutLayout()) return;
  const panelRect = els.chartPanel.getBoundingClientRect();
  const cardRect = els.scoutCard.getBoundingClientRect();
  scoutDragState = {
    pointerId: e.pointerId,
    startX: e.clientX,
    startY: e.clientY,
    startLeft: cardRect.left - panelRect.left,
    startTop: cardRect.top - panelRect.top,
    // Clamp targets, computed once at drag start rather than every move —
    // the panel doesn't resize mid-drag.
    maxLeft: Math.max(panelRect.width - cardRect.width, 0),
    maxTop: Math.max(panelRect.height - cardRect.height, 0),
  };
  // Switch from the default top/right anchor to an explicit left/top so
  // the card can move freely; keeps it exactly where it already was.
  els.scoutCard.style.left = `${scoutDragState.startLeft}px`;
  els.scoutCard.style.top = `${scoutDragState.startTop}px`;
  els.scoutCard.style.right = "auto";
  els.scoutCard.classList.add("is-dragging");
  els.scoutDragHandle.setPointerCapture(e.pointerId);
}

function onScoutDragMove(e) {
  if (!scoutDragState || e.pointerId !== scoutDragState.pointerId) return;
  const dx = e.clientX - scoutDragState.startX;
  const dy = e.clientY - scoutDragState.startY;
  const left = Math.min(Math.max(scoutDragState.startLeft + dx, 0), scoutDragState.maxLeft);
  const top = Math.min(Math.max(scoutDragState.startTop + dy, 0), scoutDragState.maxTop);
  els.scoutCard.style.left = `${left}px`;
  els.scoutCard.style.top = `${top}px`;
}

function endScoutDrag(e) {
  if (!scoutDragState || e.pointerId !== scoutDragState.pointerId) return;
  els.scoutDragHandle.releasePointerCapture(e.pointerId);
  els.scoutCard.classList.remove("is-dragging");
  scoutDragState = null;
}

function closeFiltersDrawer() {
  els.filtersDrawer.classList.remove("open");
  els.filtersToggle.setAttribute("aria-expanded", "false");
}

// The one entry point that turns pending control values into what's
// actually plotted — fires on Apply click or Enter in the threshold field,
// batching however many of category/season/position/axes/threshold the
// user changed since the last apply into a single fetch + render.
async function applyFilters() {
  const sliceChanged =
    els.category.value !== appliedFilters.category ||
    els.season.value !== appliedFilters.season ||
    els.position.value !== appliedFilters.position;

  if (sliceChanged) {
    pinnedIndex = null;
    resetScoutCard();
    await loadCurrentSlice(); // may also reset/clamp the threshold controls
  }

  // A season/position/category switch (or a threshold edit that slipped in
  // without a live prune) can leave stale chips pointing at players outside
  // the new qualifying pool — drop them before snapshotting into
  // appliedFilters so the chart never highlights a player who isn't there.
  prunePlayerSelections();
  appliedFilters = currentFilterState();
  closeFiltersDrawer();
  render();
  updatePendingState();
}

function attachEvents() {
  // Category/season/position/axes are all pending-only for the chart: picking
  // a new value just updates the control itself (plus, for category, the
  // option lists that depend on it) and lights up Apply — nothing fetches or
  // re-renders the chart until applyFilters() runs, so the user can change
  // several of these together and commit them in one shot. Category/season/
  // position additionally trigger updatePlayerPool() live (unlike the chart),
  // since the Players search pool is cheap to keep in sync with whatever
  // position is currently selected rather than making it wait for Apply too.
  els.category.addEventListener("change", () => {
    resetThresholdOnNextRange = true;
    populateCategoryDependentControls();
    updatePendingState();
    updatePlayerPool();
  });

  [els.season, els.position].forEach((el) =>
    el.addEventListener("change", () => {
      updatePendingState();
      updatePlayerPool();
    })
  );

  [els.xMetric, els.yMetric].forEach((el) =>
    el.addEventListener("change", updatePendingState)
  );

  // Teams: pending-only like every other filter above — picking teams just
  // updates the summary label and lights up Apply; the chart doesn't
  // refilter until applyFilters() runs.
  els.teamsBtn.addEventListener("click", () => {
    if (els.teamsDropdown.hidden) openTeamsDropdown();
    else closeTeamsDropdown();
  });

  els.teamsSelectAll.addEventListener("click", () => {
    els.teamsChecklist.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = true));
    updateTeamsSummary();
    updatePendingState();
  });

  els.teamsSelectNone.addEventListener("click", () => {
    els.teamsChecklist.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = false));
    updateTeamsSummary();
    updatePendingState();
  });

  els.teamsChecklist.addEventListener("change", () => {
    updateTeamsSummary();
    updatePendingState();
  });

  // Same e.isTrusted guard as the scouting card / filters drawer listeners
  // below — protects against Plotly.downloadImage()'s synthetic anchor
  // click, which bubbles to document as an untrusted "click" outside every
  // container and would otherwise slam this dropdown shut mid-export.
  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (els.teamsDropdown.hidden) return;
    if (!els.teamsControl.contains(e.target)) closeTeamsDropdown();
  });

  // Players: collapsed behind a button + panel, same mechanism as Teams —
  // the chip list stays hidden until opened so it never has to fit inside
  // the collapsed button's width (see the .control-players comment in
  // style.css). Pending-only like Teams otherwise: adding/removing a chip
  // just updates the selection and lights up Apply; the chart doesn't
  // re-highlight until applyFilters() runs. The search itself, though,
  // reacts live (see qualifyingPlayerPool()/prunePlayerSelections()) since
  // it's cheap client-side filtering against already-cached data, not a
  // refetch.
  els.playersBtn.addEventListener("click", () => {
    if (els.playersPanel.hidden) openPlayersPanel();
    else closePlayersPanel();
  });

  els.playersInput.addEventListener("input", runPlayersSearch);

  els.playersInput.addEventListener("focus", () => {
    if (els.playersInput.value.trim()) runPlayersSearch();
  });

  els.playersInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      // Autocomplete convention: Escape backs out one level at a time —
      // first close just the suggestion list, and only close the whole
      // panel if the suggestions were already closed.
      if (!els.playersDropdown.hidden) hidePlayersDropdown();
      else closePlayersPanel();
    } else if (e.key === "Enter") {
      // Autocomplete convention: Enter commits the top suggestion, same as
      // a click on it.
      e.preventDefault();
      const first = els.playersDropdown.querySelector(".player-option");
      if (first) first.click();
    }
  });

  // Same e.isTrusted guard as the Teams/filters-drawer listeners — see the
  // comment above the Teams one for why. Uses composedPath() rather than
  // playersControl.contains(e.target): picking a suggestion calls
  // hidePlayersDropdown(), which clears the suggestion list's innerHTML
  // (removing the very button just clicked) before this bubbled listener
  // runs — contains() on a now-detached node always returns false, which
  // was slamming the whole panel shut on every single pick. composedPath()
  // is captured at dispatch time, before that mutation, so it still
  // includes playersControl.
  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (els.playersPanel.hidden) return;
    if (!e.composedPath().includes(els.playersControl)) closePlayersPanel();
  });

  // Dragging the slider or typing a number only updates these two controls'
  // own displayed values — the chart holds its current state until the user
  // clicks Apply (or presses Enter in the number field). Re-rendering on
  // every pixel of drag / every keystroke was the whole problem on dense
  // positions.
  els.threshold.addEventListener("input", () => {
    els.thresholdNumber.value = els.threshold.value;
    // The user just gave an explicit threshold — don't let a pending
    // category switch stomp it back to that category's default at Apply
    // time (see the resetThresholdOnNextRange comment above its declaration).
    resetThresholdOnNextRange = false;
    // The Players pool is threshold-gated live (not just at Apply) — see
    // qualifyingPlayerPool() — so a chip that no longer clears the new
    // value should disappear the moment the slider moves, not linger until
    // Apply.
    prunePlayerSelections();
    updatePendingState();
  });

  els.thresholdNumber.addEventListener("input", () => {
    const min = Number(els.threshold.min);
    const max = Number(els.threshold.max);
    const step = Number(els.threshold.step) || 1;

    let raw = Number(els.thresholdNumber.value);
    if (Number.isNaN(raw)) raw = min;
    raw = Math.min(Math.max(raw, min), max);
    els.thresholdNumber.value = raw;

    // Slider snaps to the nearest step just to keep the handle in sync
    // visually — filtering below still uses the exact typed number.
    els.threshold.value = min + Math.round((raw - min) / step) * step;
    resetThresholdOnNextRange = false;
    prunePlayerSelections();
    updatePendingState();
  });

  els.thresholdNumber.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    applyFilters();
  });

  els.applyBtn.addEventListener("click", applyFilters);

  // Exports exactly what's on screen — built from appliedFilters (the
  // last-committed state render() actually drew), not the live controls,
  // so a pending-but-not-applied axis/season change can't leak into the
  // downloaded filename or image.
  els.savePngBtn.addEventListener("click", () => {
    if (els.savePngBtn.disabled) return;
    const season = appliedFilters.season;
    const position = sanitizeForFilename(appliedFilters.position);
    const xMetric = sanitizeForFilename(appliedFilters.xMetric);
    const yMetric = sanitizeForFilename(appliedFilters.yMetric);
    const filename = `LinesShines_${season}_${position}_${xMetric}_vs_${yMetric}`;

    // paper/plot bgcolor are "transparent" on screen — the chart relies on
    // .chart-panel's dark CSS behind it (see style.css --turf-800). A raster
    // export has no page behind it, so a transparent export composites onto
    // whatever's behind it when opened (white, on most viewers/socials),
    // which washes out the low-opacity gridlines/labels designed for a dark
    // background. Swap in the panel's actual color just for the export, then
    // restore transparency so on-screen zoom/pan is unaffected. The guard
    // suppresses the logo/label relayout handler from reacting to these two
    // bookkeeping relayouts.
    els.savePngBtn.disabled = true;
    logoRelayoutGuard = true;
    Plotly.relayout(els.chart, { paper_bgcolor: "#16301f", plot_bgcolor: "#16301f" })
      .then(() =>
        // `width`/`height` set Plotly's *logical* layout size — every fixed-px
        // font (marker labels, axis titles, median/note annotations) is sized
        // relative to that, not to the final image resolution. `scale` is a
        // separate post-render pixel-density multiplier that leaves those
        // proportions alone. The on-screen chart renders at ~1100x720, so a
        // straight width:2400/height:1500/scale:1 export (a ~2.2x larger
        // logical canvas) made every label look shrunken relative to the chart
        // even though the file itself was high-res. Keeping the logical size
        // close to the real on-screen size and reaching the same 2400x1500
        // output via scale:2 instead makes exported text match what's on
        // screen while keeping the image just as crisp.
        Plotly.downloadImage(els.chart, {
          format: "png",
          filename,
          width: 1200,
          height: 750,
          scale: 2,
        })
      )
      .then(() =>
        Plotly.relayout(els.chart, { paper_bgcolor: "transparent", plot_bgcolor: "transparent" })
      )
      .finally(() => {
        logoRelayoutGuard = false;
        els.savePngBtn.disabled = false;
      });
  });

  els.labelsToggle.addEventListener("change", render);
  els.logosToggle.addEventListener("change", render);

  els.scoutClose.addEventListener("click", () => {
    pinnedIndex = null;
    resetScoutCard();
  });

  // Pointer capture on the handle itself means move/up keep firing on it
  // even once the pointer strays outside the card during a fast drag — no
  // document-level listeners needed.
  els.scoutDragHandle.addEventListener("pointerdown", beginScoutDrag);
  els.scoutDragHandle.addEventListener("pointermove", onScoutDragMove);
  els.scoutDragHandle.addEventListener("pointerup", endScoutDrag);
  els.scoutDragHandle.addEventListener("pointercancel", endScoutDrag);

  // A drag position is only valid in the desktop overlay layout — resizing
  // past the breakpoint mid-session (or a device rotation) needs the same
  // cleanup resetScoutCard() does on close, see clearScoutCardDragPosition().
  window.addEventListener("resize", () => {
    if (!isDesktopScoutLayout()) clearScoutCardDragPosition();
  });

  // Closes the pinned scouting card when clicking anywhere outside both
  // the chart and the card itself.
  //
  // `e.isTrusted` guards both this and the filters-drawer listener below
  // against Plotly.downloadImage()'s internal implementation: it builds a
  // throwaway <a>, appends it to <body>, and calls .click() on it to
  // trigger browser for saving dialog. That programmatic click bubbles to
  // document as a real "click" event with a target outside every one of
  // our containers, which — without this guard — closed the scouting card
  // and, worse, closed the mobile filters drawer immediately after Save
  // Plot, even though Save Plot is supposed to leave the drawer open for
  // repeated exports. Synthetic (script-dispatched) events always report
  // isTrusted: false, so filtering on it distinguishes Plotly's anchor
  // click from an actual user tap outside the drawer/card.
  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (pinnedIndex == null) return;
    if (!els.chart.contains(e.target) && !els.scoutCard.contains(e.target)) {
      pinnedIndex = null;
      resetScoutCard();
    }
  });

  els.filtersToggle.addEventListener("click", () => {
    const isOpen = els.filtersDrawer.classList.toggle("open");
    els.filtersToggle.setAttribute("aria-expanded", String(isOpen));
  });

  document.addEventListener("click", (e) => {
    if (!e.isTrusted) return;
    if (!els.filtersDrawer.classList.contains("open")) return;
    if (els.filtersDrawer.contains(e.target) || els.filtersToggle.contains(e.target)) return;
    closeFiltersDrawer();
  });
}

loadMetadata().catch((err) => {
  console.error(err);
  els.chart.innerHTML =
    `<p style="color:#f1ecdd;padding:24px;">Could not load /api/metadata — ` +
    `is the FastAPI server running? (${err.message})</p>`;
});
