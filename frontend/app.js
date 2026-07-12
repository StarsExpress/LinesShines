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
};

let metadata = null;                 // /api/metadata payload
const sliceCache = new Map();        // key = `${category}:${season}:${position}` → records[]
let currentRecords = [];             // records for the current slice (all threshold values)
let currentFiltered = [];            // records >= threshold (what the chart shows)

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
// width so a dense mobile chart (77 overlapping dots on a 342px-wide panel)
// doesn't inherit the same visual scale as a 1100px desktop chart. Mobile
// gets a smaller absolute size to cut overlap; desktop's 26px roughly
// matches the visual scale of the matplotlib reference in
// scatter_plots/pass_rush_plot.py.
function targetLogoPx() {
  return window.innerWidth < 860 ? 18 : 26;
}

async function loadMetadata() {
  const res = await fetch("/api/metadata");
  if (!res.ok) throw new Error(`GET /api/metadata → ${res.status}`);
  metadata = await res.json();

  populateCategoryDependentControls();
  attachEvents();
  await loadCurrentSlice();
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
  };
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
    opt.textContent = `${code} — ${label}`;
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

  els.thresholdFieldLabel.textContent =
    cat.threshold_field === "PR Opp" ? "pass rush opportunities" : "non-spike pass block snaps";
}

async function loadCurrentSlice() {
  const category = els.category.value;
  const season = Number(els.season.value);
  const position = els.position.value;
  const key = `${category}:${season}:${position}`;

  if (!sliceCache.has(key)) {
    const url = `/api/${category}?season=${season}&position=${encodeURIComponent(position)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
    const data = await res.json();
    sliceCache.set(key, data.records || []);
  }
  currentRecords = sliceCache.get(key);
  updateThresholdRange();
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

function formatValue(value, meta) {
  if (value == null) return "—";
  const unit = meta && meta.unit ? meta.unit : "";
  return `${value}${unit}`;
}

function teamColor(code) {
  const t = metadata.teams && metadata.teams[code];
  return (t && t.primary_color) || "#6b7a6f";
}

function teamName(code) {
  const t = metadata.teams && metadata.teams[code];
  return (t && t.full_name) || code;
}

// sizex/sizey for layout.images are in DATA units, not pixels, so logo size
// needs recomputing whenever the visible axis range or plot size changes
// (zoom, pan, resize) — otherwise logos balloon, shrink, or drift off their
// intended on-screen scale.
function computeLogoImages(chartDiv, records, xKey, yKey) {
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

  return records.map((r) => ({
    source: logoSrc(r.team),
    xref: "x", yref: "y",
    x: r[xKey], y: r[yKey],
    sizex, sizey,
    xanchor: "center", yanchor: "middle",
    layer: "above",
  }));
}

// Approximates adjustText's declutter effect without the library: process
// labels in descending threshold_field order (so star players get first
// claim), keep a label only if its approximate pixel bounding box doesn't
// overlap one already kept, blank the rest.
function computeKeptLabels(chartDiv, records, xKey, yKey, thresholdField) {
  const fullLayout = chartDiv._fullLayout;
  const xAxis = fullLayout && fullLayout.xaxis;
  const yAxis = fullLayout && fullLayout.yaxis;
  if (!xAxis || !yAxis || typeof xAxis.l2p !== "function") {
    return records.map(() => true);
  }

  const CHAR_WIDTH = 6.5; // approx advance width, IBM Plex Mono @ 10px
  const LABEL_HEIGHT = 12;
  const LABEL_GAP = 10;   // vertical offset from marker center to "bottom center" text

  const boxes = records.map((r) => {
    const label = r.abbr_name || r.player || "";
    const cx = xAxis.l2p(r[xKey]);
    const top = yAxis.l2p(r[yKey]) + LABEL_GAP;
    const halfWidth = (label.length * CHAR_WIDTH) / 2;
    return {
      left: cx - halfWidth, right: cx + halfWidth,
      top, bottom: top + LABEL_HEIGHT,
      priority: r[thresholdField] ?? 0,
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

function render() {
  const cat = appliedCategoryMeta();

  const minThreshold = Number(appliedFilters.threshold);

  currentFiltered = currentRecords.filter(
    (r) => r[cat.threshold_field] >= minThreshold
  );

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
    textfont: { color: "rgba(241,236,221,0.55)", size: 10, family: "IBM Plex Mono, monospace" },
    marker: {
      color: colors,
      size: 13,
      // invisible dots still receive hover/click — only the fill disappears —
      // so the scouting card keeps working with logos drawn on top via
      // layout.images (Plotly has no native "image as marker" option).
      opacity: showLogos ? 0 : 1,
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

  const layout = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter, sans-serif", color: "#f1ecdd" },
    margin: { l: 60, r: 24, t: 20, b: 56 },
    dragmode: false,
    xaxis: {
      title: `${xKey}${xMeta.unit ? " (" + xMeta.unit + ")" : ""}`,
      gridcolor: "rgba(241,236,221,0.08)",
      zerolinecolor: "rgba(241,236,221,0.15)",
      autorange: reversed ? "reversed" : true,
    },
    yaxis: {
      title: `${yKey}${yMeta.unit ? " (" + yMeta.unit + ")" : ""}`,
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
    const images = computeLogoImages(els.chart, currentFiltered, xKey, yKey);
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
    const kept = computeKeptLabels(els.chart, currentFiltered, xKey, yKey, cat.threshold_field);
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
  const addRow = (label, value, highlighted) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    if (highlighted) dd.classList.add("is-highlighted");
    els.scoutStats.appendChild(dt);
    els.scoutStats.appendChild(dd);
  };

  addRow("Games", record.games);
  addRow(cat.threshold_field, record[cat.threshold_field]);
  Object.entries(cat.metrics).forEach(([key, meta]) => {
    addRow(key, formatValue(record[key], meta), key === xKey || key === yKey);
  });
}

function resetScoutCard() {
  els.scoutCard.classList.remove("is-active");
  els.scoutEmpty.hidden = false;
  els.scoutBody.hidden = true;
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

  appliedFilters = currentFilterState();
  closeFiltersDrawer();
  render();
  updatePendingState();
}

function attachEvents() {
  // Category/season/position/axes are all pending-only now: picking a new
  // value just updates the control itself (plus, for category, the option
  // lists that depend on it) and lights up Apply. Nothing fetches or
  // re-renders until applyFilters() runs, so the user can change several of
  // these together and commit them in one shot.
  els.category.addEventListener("change", () => {
    resetThresholdOnNextRange = true;
    populateCategoryDependentControls();
    updatePendingState();
  });

  [els.season, els.position, els.xMetric, els.yMetric].forEach((el) =>
    el.addEventListener("change", updatePendingState)
  );

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

  // Closes the pinned scouting card when clicking anywhere outside both
  // the chart and the card itself.
  //
  // `e.isTrusted` guards both this and the filters-drawer listener below
  // against Plotly.downloadImage()'s internal implementation: it builds a
  // throwaway <a>, appends it to <body>, and calls .click() on it to
  // trigger the browser's save dialog. That programmatic click bubbles to
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
