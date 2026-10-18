# Playbook

Task-specific knowledge for Claude Code. `CLAUDE.md` is a short entry point that sends you to `INVARIANTS.md` (working rules and invariants).

Everything that is needed for one kind of task lives here and is read on demand.

> Public in git: this file, `DECISIONS.md`, `INVARIANTS.md` and `architecture/`. The rest of `playbook/` (`COMMANDS.md`, `NEXT_STEPS.md`, `HANDOFF.md`, `DISCUSSIONS.md`, `GUIDE.md`) stays on the owner's machine (see `.gitignore`), so those names below exist locally, not in the public repo.

## Read this first, by task

| If you are about to... | Read |
|---|---|
| Change anything that looks odd, or make a design choice | `DECISIONS.md` |
| Start any task | `INVARIANTS.md`, section "Working rules" |
| Touch filtering, percentiles, caching, cards, thresholds, or exports | `INVARIANTS.md`, section "Invariants" |
| Work on a specific area | the matching file in `architecture/` (table below; `architecture/INDEX.md` lists every section) |
| Install, run, test, lint, serve, preprocess or ingest | `COMMANDS.md` |
| Do the next piece of work | `NEXT_STEPS.md` (decided work only; the owner names which item) |
| Understand current status and background | `HANDOFF.md` (Chinese, for the owner; status only, not code rules) |
| (never act on these) | `DISCUSSIONS.md`: open topics still being discussed |

## architecture/

| File | Load when |
|---|---|
| `BACKEND-AND-DEPLOY.md` | ingestion, DB models, API routes, team codes, deploy, tests |
| `FRONTEND-STRUCTURE.md` | ES-module layout, imports, shared state, client data model |
| `PWA.md` | `sw.js`, manifest, caching, install flow, any new route or API prefix |
| `UI-LAYOUT-AND-EXPORT.md` | control-bar CSS, breakpoints, card drag/resize/fold, fuzzy search, PNG export |
| `CHART-RENDERING.md` | `render.js`, label decluttering/emphasis, axis direction |
| `CARDS.md` | Pinned Players, Merge Cards, Linemate Cards |
| `FILTERS-AND-SEARCH.md` | Teams/Players filters, Players search pool, below-threshold matches, Quick Set |
| `PERCENTILES.md` | any percentile or rank computation |
| `PINNED-INVALIDATION.md` | filter changes that remove Pinned Players, the confirm dialog, Comparison shrink/dissolve |
| `METRICS-AND-NOTES.md` | adding or renaming a metric, info popovers, metric notes, export appendix |
| `THRESHOLDS.md` | `config.py` thresholds, `resolve_default_threshold`, the threshold input clamp |

These files were moved verbatim from the old `CLAUDE.md` "Architecture" section. Cross-references such as
"see X above/below" point to another file here; `architecture/INDEX.md` maps section titles to files.

## Keeping this folder healthy

- New significant decision: append it to `DECISIONS.md` with a date. Not to `CLAUDE.md`.
- New must-not-break rule: add a row to `INVARIANTS.md` and say what enforces it.
- Changed behaviour described in an `architecture/` file: update that file in the same change.
- Keep `CLAUDE.md` short. If a paragraph is only needed for one kind of task, it belongs here.
- Write files for Claude Code in English (`COMMANDS.md`, `NEXT_STEPS.md`, `DECISIONS.md`, `INVARIANTS.md`, `architecture/`).
  `HANDOFF.md`, `DISCUSSIONS.md` and `GUIDE.md` are Chinese, for the owner.
- `NEXT_STEPS.md` and `DISCUSSIONS.md` have no numbering and no implied order; priority changes at any time.
