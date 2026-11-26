// A just-enough browser for the app's ES modules, so their logic runs under `node --test` with no browser.
//
// `frontend/dom.js` looks up its elements while it is imported, so `document` has to exist before the first
// import. Call `installBrowser()` first, then `await import()` the module under test. Node keeps one copy of
// each module per process and `node --test` gives each test file its own process, so a file picks its page
// (Season or Career) once, here.

const NFL_SEASON_LEAGUE = {
  key: "nfl",
  name: "NFL",
  apiPrefix: "/api/nfl",
  logoDir: "nfl",
  teamGroups: "static",
  teamLabel: "code",
};

const CAREER_LEAGUE = {
  key: "ncaaf",
  name: "NCAAF",
  apiPrefix: "/api/ncaaf/career",
  logoDir: "ncaaf",
  teamGroups: "conference",
  teamLabel: "name",
  mode: "career",
};

function makeElement(id) {
  return {
    id,
    hidden: false,
    disabled: false,
    checked: false,
    value: "",
    title: "",
    textContent: "",
    style: {},
    dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener() {},
    removeEventListener() {},
    append() {},
    appendChild() {},
    setAttribute() {},
    removeAttribute() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 800, height: 500, top: 0, left: 0 }),
    // Plotly's graph div API.
    on() {},
    removeAllListeners() {},
  };
}

// Records what the chart hands to Plotly, which is where `render()` leaves its decisions.
function makePlotly() {
  const plotly = {
    reactCalls: [],
    react(...callArguments) {
      plotly.reactCalls.push(callArguments);

      return Promise.resolve();
    },
    purge() {},
    relayout: () => Promise.resolve(),
    restyle: () => Promise.resolve(),
  };

  return plotly;
}

/** Put a fake `document`, `window`, `localStorage` and `Plotly` in place. `career: true` serves the Career page. */
export function installBrowser({ career = false } = {}) {
  const elements = new Map();

  globalThis.document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, makeElement(id));

      return elements.get(id);
    },
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
    createElement: (tag) => makeElement(tag),
    documentElement: { clientWidth: 1280 },
    body: makeElement("body"),
  };
  globalThis.window = globalThis;
  globalThis.LEAGUE = career ? CAREER_LEAGUE : NFL_SEASON_LEAGUE;
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
  globalThis.Plotly = makePlotly();
}

/** The metadata of one category, in the shape `data.js` reads: a threshold field, metrics, positions. */
export function categoryMetadata({ thresholdField = "PR Opp", metricKeys = ["x_metric", "y_metric"] } = {}) {
  return {
    threshold_field: thresholdField,
    metrics: Object.fromEntries(metricKeys.map((key) => [key, { label: key, higher_is_better: true }])),
    positions: { ED: "Edge", DI: "Interior" },
  };
}
