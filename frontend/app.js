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
  thresholdFieldLabel: document.getElementById("threshold-field-label"),
  labelsToggle: document.getElementById("labels-toggle"),
  logosToggle: document.getElementById("logos-toggle"),
  chart: document.getElementById("chart"),
  chartPanel: document.querySelector(".chart-panel"),
  emptyState: document.getElementById("empty-state"),
  logoPreload: document.getElementById("logo-preload"),
  chartModal: document.getElementById("chart-modal"),
  modalChart: document.getElementById("modal-chart"),
  closeModalBtn: document.getElementById("close-modal"),
  filtersToggle: document.getElementById("toggle-filters"),
  filtersDrawer: document.getElementById("filters-drawer"),
  sampleBanner: document.getElementById("sample-banner"),
  sampleBannerText: document.getElementById("sample-banner-text"),
  scoutCard: document.getElementById("scout-card"),
  scoutEmpty: document.getElementById("scout-card-empty"),
  scoutBody: document.getElementById("scout-card-body"),
  scoutLogo: document.getElementById("scout-logo"),
  scoutBadge: document.getElementById("scout-badge"),
  scoutName: document.getElementById("scout-name"),
  scoutMeta: document.getElementById("scout-meta"),
  scoutStats: document.getElementById("scout-stats"),
};

let metadata = null;                 // /api/metadata payload
const sliceCache = new Map();        // key = `${category}:${season}:${position}` → records[]
let currentRecords = [];             // records for the current slice (all threshold values)
let currentFiltered = [];            // records >= threshold (what the chart shows)
let pinnedIndex = null;
let logoRelayoutGuard = false;       // suppresses our own relayout from re-triggering itself
let unhoverTimeout = null;           // debounces the chart mouseleave hide so grazing the edge doesn't flicker the card
let chartHovered = false;            // tracks pointer-inside-#chart, not "hovering a marker" — far less noisy at the edges

// True right after page load and right after a category switch — both cases
// where the threshold should snap to that category's configured default
// rather than carrying over a value from a different threshold_field scale
// (PR Opp vs Non Spike PB Snaps aren't comparable). Season/position changes
// within the same category leave this false, so the user's value persists.
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

// Logos are sized as a fraction of plot WIDTH in pixels, not a fixed pixel
// target — that way they stay proportionally consistent whether the chart
// shows 20 players or 70, and scale with the container instead of looking
// tiny on a wide monitor / oversized on mobile. ~2.8% roughly matches the
// visual scale of the matplotlib reference in scatter_plots/pass_rush_plot.py.
const LOGO_WIDTH_FRACTION = 0.028;

async function loadMetadata() {
  const res = await fetch("/api/metadata");
  if (!res.ok) throw new Error(`GET /api/metadata → ${res.status}`);
  metadata = await res.json();

  updateSampleBanner();
  populateCategoryDependentControls();
  attachEvents();
  await loadCurrentSlice();

  els.logoPreload.hidden = false;
  await preloadLogos();
  els.logoPreload.hidden = true;

  render();
}

function updateSampleBanner() {
  if (!metadata.is_sample_data) {
    els.sampleBanner.hidden = true;
    return;
  }
  els.sampleBanner.hidden = false;
  els.sampleBannerText.textContent = metadata.sample_data_note ||
    "Showing sample data — replace by running ingest_to_db.py on your PFF export.";
}

function currentCategoryMeta() {
  return metadata[els.category.value];
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
  // (e.g. TPS Win Rate vs. plain Win Rate).
  els.xMetric.value = metricKeys.find((m) => m.startsWith("TPS")) || metricKeys[0];
  els.yMetric.value = metricKeys.find((m) => !m.startsWith("TPS")) || metricKeys[1] || metricKeys[0];

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

  // Target size in pixels is a fraction of plot WIDTH (kept for both x and y
  // so logos render square), then converted back to each axis's data units.
  const targetPx = xAxis._length * LOGO_WIDTH_FRACTION;
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
  const cat = currentCategoryMeta();

  const minThreshold = Number(els.thresholdNumber.value);
  currentFiltered = currentRecords.filter(
    (r) => r[cat.threshold_field] >= minThreshold
  );

  if (currentFiltered.length < 2) {
    els.emptyState.hidden = false;
    Plotly.purge(els.chart);
    return;
  }
  els.emptyState.hidden = true;

  const xKey = els.xMetric.value;
  const yKey = els.yMetric.value;
  const xMeta = cat.metrics[xKey] || {};
  const yMeta = cat.metrics[yKey] || {};

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

  const annotations = [
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

  const reversed = els.category.value === "pass_block"; // lower allowed% is better

  const layout = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter, sans-serif", color: "#f1ecdd" },
    margin: { l: 60, r: 24, t: 20, b: 56 },
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

  // No `images` key here on purpose — Plotly.react fully replaces the
  // layout, so leaving it out clears any logos from a previous render when
  // the toggle is off. Sizing needs the post-draw axis range, so logos are
  // added in a follow-up relayout once this render settles.
  Plotly.react(els.chart, [trace], layout, { displayModeBar: false, responsive: true })
    .then(() => {
      applyLogoImages();
      applyLabelDeclutter();
    });

  // Clear stale listeners each render — Plotly.react reuses the same graph
  // div, and every call otherwise adds another copy of the hover handler.
  // No plotly_unhover here — it fires/unfires too readily near label text;
  // the chart's mouseenter/mouseleave listeners (bound once in attachEvents)
  // decide hiding instead, since "is the pointer still inside the chart box"
  // has none of that per-marker noise.
  ["plotly_hover", "plotly_click", "plotly_relayout"].forEach((evt) =>
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

  els.chart.on("plotly_hover", (e) => {
    if (pinnedIndex != null) return;
    if (unhoverTimeout) clearTimeout(unhoverTimeout);
    const idx = e.points[0].pointIndex;
    showScoutCard(currentFiltered[idx]);
  });
  els.chart.on("plotly_click", (e) => {
    const idx = e.points[0].pointIndex;
    pinnedIndex = pinnedIndex === idx ? null : idx;
    if (pinnedIndex != null) showScoutCard(currentFiltered[idx]);
    else resetScoutCard();
  });
}

function showScoutCard(record) {
  const cat = currentCategoryMeta();
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
  els.scoutMeta.textContent = `${teamName(record.team)} · ${record.position} · ${record.season}`;

  const xKey = els.xMetric.value;
  const yKey = els.yMetric.value;

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

// Below the desktop/mobile CSS breakpoint (see style.css), tapping the
// chart opens the fullscreen modal instead of just pinning the scout card —
// desktop clicks are left alone so mouse users keep the plain click-to-pin
// behavior untouched.
function isMobileViewport() {
  return window.matchMedia("(max-width: 860px)").matches;
}

// Physically moves the live #chart node into the dialog rather than
// cloning/re-rendering it — same Plotly instance, so hover/click listeners
// and the current pinned point survive the trip with no extra bookkeeping.
function openChartModal() {
  if (els.chartModal.open) return;
  els.modalChart.appendChild(els.chart);
  els.chart.style.height = "100%";
  els.chartModal.showModal();
  requestAnimationFrame(() => Plotly.Plots.resize(els.chart));
}

function closeFiltersDrawer() {
  els.filtersDrawer.classList.remove("open");
  els.filtersToggle.setAttribute("aria-expanded", "false");
}

function attachEvents() {
  els.category.addEventListener("change", async () => {
    pinnedIndex = null;
    resetScoutCard();
    resetThresholdOnNextRange = true;
    populateCategoryDependentControls();
    await loadCurrentSlice();
    render();
  });

  [els.season, els.position].forEach((el) =>
    el.addEventListener("change", async () => {
      pinnedIndex = null;
      resetScoutCard();
      await loadCurrentSlice();
      render();
    })
  );

  [els.xMetric, els.yMetric].forEach((el) => el.addEventListener("change", render));

  els.threshold.addEventListener("input", () => {
    els.thresholdNumber.value = els.threshold.value;
    render();
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
    render();
  });

  els.labelsToggle.addEventListener("change", render);
  els.logosToggle.addEventListener("change", render);

  els.chart.addEventListener("click", () => {
    if (isMobileViewport()) openChartModal();
  });

  // Bound once (not in render()) since plain addEventListener isn't cleaned
  // up by Plotly's removeAllListeners — rebinding on every render would
  // stack duplicate handlers, each closing over its own stale timeout.
  els.chart.addEventListener("mouseenter", () => {
    chartHovered = true;
    if (unhoverTimeout) clearTimeout(unhoverTimeout);
  });
  els.chart.addEventListener("mouseleave", () => {
    chartHovered = false;
    if (pinnedIndex != null) return;
    unhoverTimeout = setTimeout(() => {
      if (!chartHovered) resetScoutCard();
    }, 150);
  });

  els.closeModalBtn.addEventListener("click", () => els.chartModal.close());

  // Fires on every close path (button, Esc, backdrop) — single place to
  // undo the reparent so #chart always ends up back in .chart-panel first.
  els.chartModal.addEventListener("close", () => {
    els.chart.style.height = "";
    els.chartPanel.insertBefore(els.chart, els.chartPanel.firstChild);
    requestAnimationFrame(() => Plotly.Plots.resize(els.chart));
  });

  els.filtersToggle.addEventListener("click", () => {
    const isOpen = els.filtersDrawer.classList.toggle("open");
    els.filtersToggle.setAttribute("aria-expanded", String(isOpen));
  });

  // Picking a value closes the drawer so the chart underneath is visible
  // right away; the slider/number/checkboxes are left alone since users
  // typically want to keep adjusting those without the drawer snapping shut.
  [els.category, els.season, els.position, els.xMetric, els.yMetric].forEach((el) =>
    el.addEventListener("change", closeFiltersDrawer)
  );

  document.addEventListener("click", (e) => {
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
