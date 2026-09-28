/* Plotly trace construction, label declutter/emphasis, logo placement.
 * Extracted from app.js per MODULARIZATION.md v1.3.0 §2/§3 step 8.
 * PNG export/footer-compositing split out separately into chart-export.js
 * (no dependency on trace-building) to keep this file under the project's
 * line-count guideline.
 *
 * render() calls viewFloatingCard() (scout-card.js) from its plotly_click
 * handler — a dependency the brief's module table doesn't list for
 * render.js, but a real one already present in the original code; safe to
 * add since scout-card.js doesn't depend back on render.js.
 */
import { els } from "./dom.js";
import {
  appliedCategoryMeta,
  appliedFilters,
  currentRecords,
  currentFiltered,
  setCurrentFiltered,
  teamColor,
  median,
  logoSrc,
  targetLogoPx,
  thresholdFieldLabel,
  allTeamCodes,
  teamName,
} from "./data.js";
import { DIM_OPACITY, LABEL_ALPHA } from "./config.js";
import { viewFloatingCard } from "./scout-card.js";

export let logoRelayoutGuard = false; // suppresses our own relayout from re-triggering itself

// Point-label font size for the scatter's marker text (player names) only —
// axis ticks/titles, chart title/subtitle, hoverlabel, and the median/note
// annotations below all size independently of this. History: 10px original
// → 12.5px (125%) per Reddit's "extremely hard to read" feedback → 25px
// (200% of that) per a follow-up "even bolder" ask → 15px → 13px → back to
// 10px. Note this is the original pre-emphasis size that prompted the
// "extremely hard to read" feedback in the first place — but it's now
// paired with the bold/halo/glow emphasis (LABEL_EMPHASIS_WEIGHT etc. below)
// that didn't exist back then, so it's not a straight reversion to how it
// used to look. computeKeptLabels()'s collision-box constants, LABEL_GAP
// (marker-to-label offset), and the halo/glow constants below are all
// derived off this same value (see FONT_SCALE there) so a future size
// change can't quietly fall out of sync with however large the trace text
// actually renders — this one constant is the whole change.
export const POINT_LABEL_FONT_SIZE = 10;

// Bold weight + a background-colored halo (outline) + a faint glow, applied
// only to spotlighted (non-dimmed) labels — the "bolder" half of the Reddit
// legibility follow-up (LABEL_ALPHA in config.js handles "brighter", the one
// part Plotly's textfont natively supports). None of the three below are:
// Plotly's textfont schema has no font-weight, stroke, or filter property at
// all, so applyLabelEmphasis() sets these as direct inline SVG styles on the
// rendered <text> nodes post-render instead of through trace config.
// Exported (not just local consts) because chart-export.js's canvas-overlay
// redraw needs these exact same values — Plotly's PNG export regenerates its
// SVG from its own internal model rather than the live, DOM-patched chart,
// so this emphasis has to be manually re-drawn onto the export canvas too;
// sharing these constants is what keeps that redraw pixel-matched to what's
// actually on screen instead of a second hand-tuned copy drifting over time.
export const LABEL_EMPHASIS_WEIGHT = "600"; // matches the Oswald 600 instance index.html already loads
// Halo width and glow blur are both a fraction of the label's own font size
// rather than a flat px value, so they stay proportionate if
// POINT_LABEL_FONT_SIZE ever changes again instead of silently drifting.
export const LABEL_HALO_WIDTH = POINT_LABEL_FONT_SIZE * 0.16; // ~2px at 12.5px — a controlled outline, not a thick outline
export const LABEL_HALO_COLOR = "#16301f"; // matches --turf-800 / EXPORT_FOOTER_BG in chart-export.js — the chart's real background on screen and in the export
export const LABEL_GLOW_BLUR = POINT_LABEL_FONT_SIZE * 0.12; // ~1.5px at 12.5px — deliberately small/subtle, not a neon effect
export const LABEL_GLOW_COLOR = "rgba(241,236,221,0.4)"; // faint bright glow, same off-white as the label text itself
export const LABEL_FILL_RGB = "241,236,221"; // the off-white player-name/label color — shared so chart-export.js's canvas overlay fills with the exact same color

// main.js's Save-PNG handler (attachEvents()) sets this directly around its
// own paper_bgcolor/plot_bgcolor relayout calls — same reason every other
// cross-module write in this split goes through a setter, see data.js's
// header comment.
export function setLogoRelayoutGuard(v) {
  logoRelayoutGuard = v;
}

// Some metric display names (OL's "Allowed Pressure %", "TPS Allowed Havoc %")
// already end in the unit symbol, since PFF's naming bakes it in — appending
// " (%)" on top of that would duplicate it. DL names ("Win Rate", "Havoc Rate")
// don't carry the unit, so they still need the suffix appended.
export function axisTitle(metricName, meta) {
  const unit = meta && meta.unit ? meta.unit : "";
  if (!unit) return metricName;
  if (metricName.trimEnd().endsWith(unit)) return metricName;
  return `${metricName} (${unit})`;
}

// sizex/sizey for layout.images are in DATA units, not pixels, so logo size
// needs recomputing whenever the visible axis range or plot size changes
// (zoom, pan, resize) — otherwise logos balloon, shrink, or drift off their
// intended on-screen scale.
// `isDimmed` (aligned index-for-index with `records`) fades logos for
// players whose team isn't in the current Teams selection, rather than
// dropping them from the plot entirely — see DIM_OPACITY.
export function computeLogoImages(chartDiv, records, xKey, yKey, isDimmed) {
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
// regardless of threshold_field, so a Teams/Players selection never loses
// its own labels to a bigger name outside the selection.
export function computeKeptLabels(chartDiv, records, xKey, yKey, thresholdField, isDimmed) {
  const fullLayout = chartDiv._fullLayout;
  const xAxis = fullLayout && fullLayout.xaxis;
  const yAxis = fullLayout && fullLayout.yaxis;
  if (!xAxis || !yAxis || typeof xAxis.l2p !== "function") {
    return records.map(() => true);
  }

  // Box constants below were tuned by eye at the original 10px label size;
  // FONT_SCALE keeps them proportional to whatever POINT_LABEL_FONT_SIZE
  // actually is now, so a future font-size tweak can't silently desync the
  // declutter math from the text it's supposed to be measuring.
  const FONT_SCALE = POINT_LABEL_FONT_SIZE / 10;
  const CHAR_WIDTH = 6.5 * FONT_SCALE; // Approx advance width @ 10px baseline.
  const LABEL_HEIGHT = 12 * FONT_SCALE;
  const LABEL_GAP = 10 * FONT_SCALE;   // vertical offset from marker center to "bottom center" text
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

// Applies the bold + halo + glow emphasis (see the LABEL_EMPHASIS_WEIGHT
// comment above) to every spotlighted label's rendered <text> node, and
// explicitly clears those same styles from every non-spotlighted node.
// Plotly stamps a `data-unformatted` attribute on each scatter-trace text
// node holding its exact current text value, so matching against
// `spotlightNames` here is robust to Plotly reusing or recreating those DOM
// nodes across renders — it doesn't depend on array-index alignment or any
// particular DOM structure beyond that one attribute. Always clearing the
// non-matching nodes (not just skipping them) matters because a Teams/
// Players change can reassign which players are spotlighted between
// renders; without the clear, a label that's no longer spotlighted could
// keep a stale halo from an earlier render where it was.
//
// Caveat: two different players sharing the exact same rendered label text
// (an identical "First Last" abbreviation) would both match — extremely
// rare within one filtered view, and harmless even if it happens (worst
// case a dimmed duplicate gets an emphasis it didn't need).
export function applyLabelEmphasis(chartDiv, spotlightNames) {
  const nodes = chartDiv.querySelectorAll(".scatterlayer text");
  nodes.forEach((node) => {
    const name = node.getAttribute("data-unformatted");
    const spotlighted = !!name && spotlightNames.has(name);
    node.style.fontWeight = spotlighted ? LABEL_EMPHASIS_WEIGHT : "";
    node.style.paintOrder = spotlighted ? "stroke" : "";
    node.style.stroke = spotlighted ? LABEL_HALO_COLOR : "";
    node.style.strokeWidth = spotlighted ? `${LABEL_HALO_WIDTH}px` : "";
    node.style.strokeLinejoin = spotlighted ? "round" : "";
    node.style.filter = spotlighted ? `drop-shadow(0 0 ${LABEL_GLOW_BLUR}px ${LABEL_GLOW_COLOR})` : "";
  });
}

// Teams and Players both only dim, never exclude (see the isDimmed comment
// in render()), so unlike the old Teams-only subtitle this can't just count
// currentFiltered — a reader needs to know *why* a non-highlighted-team
// player might still be sitting on the chart. Falls back to the plain
// "N players ≥ threshold" line when nothing is actually being highlighted
// (all teams selected, no players added) so the common case stays terse.
export function highlightSubtitle(cat, records, isDimmed, selectedTeams, selectedPlayerKeys, minThreshold) {
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

export function render() {
  const cat = appliedCategoryMeta();

  const minThreshold = Number(appliedFilters.threshold);
  const selectedTeams = new Set(appliedFilters.teams ? appliedFilters.teams.split(",") : []);
  const selectedPlayerKeys = new Set(appliedFilters.players ? appliedFilters.players.split(",") : []);

  // currentRecords holds every position in the category (see fetchSlice) —
  // scope to the applied position here, same as positionPool() does for
  // Merge/Linemate cards, so the chart's own percentile pool never mixes
  // positions.
  // setCurrentFiltered() replaces the original's direct `currentFiltered =`
  // assignment — data.js owns that state now (read by scout-card.js's
  // renderScoutCardStats too), and ES modules don't let an importer
  // reassign an imported `let`. Every `currentFiltered` read below this
  // point sees the update immediately — imported bindings are live.
  setCurrentFiltered(
    currentRecords.filter((r) => r.position === appliedFilters.position && r[cat.threshold_field] >= minThreshold)
  );
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
      color: isDimmed.map((dim) => `rgba(${LABEL_FILL_RGB},${dim ? DIM_OPACITY.label : LABEL_ALPHA})`),
      size: POINT_LABEL_FONT_SIZE,
      // Plotly's textfont has no weight field. index.html's Google Fonts
      // link now loads two Oswald instances (wght@450;600 — 600 is for the
      // Pinned/Manage bar, see style.css .pcs-quota/.pcs-inspect-btn). This
      // text sets no font-weight, so it resolves to CSS "normal" (400); per
      // the CSS font-matching algorithm that picks 450 over 600 (nearest
      // weight above 400, capped at 500), so these labels still render at
      // 450 without needing an explicit weight here.
      family: "Oswald, sans-serif",
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
        font: { family: "IBM Plex Mono, monospace", size: isMobile ? 9 : 12, color: "#f1ecdd" },
      },
    },
    dragmode: false,
    xaxis: {
      // Plotly 3.x requires title as {text: ...} — a bare string is
      // silently ignored (renders as an empty <g class="g-xtitle">).
      title: { text: axisTitle(xKey, xMeta) },
      gridcolor: "rgba(241,236,221,0.08)",
      zerolinecolor: "rgba(241,236,221,0.15)",
      autorange: reversed ? "reversed" : true,
    },
    yaxis: {
      title: { text: axisTitle(yKey, yMeta) },
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
  // sit right above a small marker and collide far less. Either way, every
  // spotlighted (non-dimmed) label that's actually showing gets the bold/
  // halo/glow emphasis from applyLabelEmphasis() — declutter can only ever
  // blank labels, never add ones back, so the two branches below just differ
  // in how they arrive at "which spotlighted labels are currently visible".
  function applyLabelDeclutter() {
    if (!showLabels) return;
    const labelName = (r) => r.abbr_name || r.player;
    if (!showLogos) {
      const spotlightNames = new Set(
        currentFiltered.filter((r, i) => !isDimmed[i]).map(labelName)
      );
      applyLabelEmphasis(els.chart, spotlightNames);
      return;
    }
    const kept = computeKeptLabels(els.chart, currentFiltered, xKey, yKey, cat.threshold_field, isDimmed);
    const text = currentFiltered.map((r, i) => (kept[i] ? labelName(r) : ""));
    const spotlightNames = new Set(
      currentFiltered.filter((r, i) => kept[i] && !isDimmed[i]).map(labelName)
    );
    Plotly.restyle(els.chart, { text: [text] }, [0]).then(() => {
      applyLabelEmphasis(els.chart, spotlightNames);
    });
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
    viewFloatingCard(currentFiltered[idx]);
  });
}
