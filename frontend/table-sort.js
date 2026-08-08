/* Excel-style click-to-sort table headers — shared by Linemate Card's
 * roster + Line Summary tables (linemate-card.js) and Merge Card's table
 * (merge-card.js). Dependency-free, like info-popover.js, so every card
 * module can import it without adding a cross-card-type dependency —
 * linemate-card.js in particular stays a pure leaf with no dependency on
 * merge-card.js (see that file's header comment).
 */

// Toggles a { key, dir } sort state object in place: clicking the
// already-sorted column flips direction, clicking a different one starts it
// ascending — matches Excel's own first-click convention. Returns the same
// object so callers can chain.
export function toggleSortState(state, key) {
  if (state.key === key) {
    state.dir = state.dir === "asc" ? "desc" : "asc";
  } else {
    state.key = key;
    state.dir = "asc";
  }
  return state;
}

// Returns a new array (never mutates `rows`) ordered per `state` using
// `valueFn(row)` for the current column — a no-op returning `rows` as-is
// until a header's been clicked at least once (state.key is null). Strings
// compare via localeCompare, numbers compare numerically; null/undefined
// always sort last regardless of direction, so missing data (e.g. a metric
// with no qualifying pool) doesn't scatter through the middle of a ranked
// column.
export function sortRows(rows, state, valueFn) {
  if (!state.key) return rows;
  const dir = state.dir === "desc" ? -1 : 1;
  return rows.slice().sort((a, b) => {
    const av = valueFn(a);
    const bv = valueFn(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "string" || typeof bv === "string") {
      return String(av).localeCompare(String(bv)) * dir;
    }
    return (av - bv) * dir;
  });
}

// Builds one sortable <th>: label text + a ▲/▼ indicator that only appears
// on the currently-sorted column. Click (or Enter/Space, for keyboard users)
// toggles `state` via toggleSortState() and re-runs `onSort` — the owning
// render function, which rebuilds the whole table from scratch, so every
// header's indicator reflects the new state without this needing to touch
// sibling headers itself.
export function makeSortableHeader(label, key, state, onSort) {
  const th = document.createElement("th");
  th.classList.add("sortable-th");
  th.tabIndex = 0;
  th.setAttribute("role", "button");
  th.setAttribute("aria-label", `Sort by ${label}`);

  const labelSpan = document.createElement("span");
  labelSpan.textContent = label;
  th.appendChild(labelSpan);

  if (state.key === key) {
    const indicator = document.createElement("span");
    indicator.className = "sort-indicator";
    indicator.textContent = state.dir === "desc" ? "▼" : "▲";
    th.appendChild(indicator);
    th.classList.add("is-sorted");
  }

  const activate = () => {
    toggleSortState(state, key);
    onSort();
  };
  th.addEventListener("click", activate);
  th.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      activate();
    }
  });

  return th;
}
