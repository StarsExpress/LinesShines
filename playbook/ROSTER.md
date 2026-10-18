# Playbook

Task-specific knowledge for Claude Code, read on demand. `CLAUDE.md` is a short entry point that sends you to `INVARIANTS.md` (working rules and invariants); everything needed for one kind of task lives here.

## Visibility

Only the files marked **public** are tracked in git. Everything else stays on the owner's machine, so the names that appear below exist locally, not in the public repo. The rule is an allow-list in `.gitignore`: `playbook/*` is ignored and each public file or folder is listed as an exception, so a new file stays local-only until someone adds it there.

| Path | Visibility |
|---|---|
| `CLAUDE.md` (repo root) | public |
| `playbook/ROSTER.md` | public |
| `playbook/DECISIONS.md` | public |
| `playbook/INVARIANTS.md` | public |
| `playbook/architecture/` (every file, including `INDEX.md`) | public |
| `playbook/COMMANDS.md` | local only |
| `playbook/next_steps/` | the folder is public (only a `.gitkeep` placeholder); every file inside is local only |
| `playbook/discussions/` | the folder is public (only a `.gitkeep` placeholder); every file inside is local only |
| `playbook/MEMORANDUM.md` | local only |
| `playbook/GUIDE.md` | local only |
| `.claude/` | local only |

## Read this first, by task

| If you are about to... | Read | Visibility |
|---|---|---|
| Change anything that looks odd, or make a design choice | `DECISIONS.md` | public |
| Start any task | `INVARIANTS.md`, section "Working rules" | public |
| Touch filtering, percentiles, caching, cards, thresholds, or exports | `INVARIANTS.md`, section "Invariants" | public |
| Work on a specific area | the matching file in `architecture/` (table below; `architecture/INDEX.md` lists every section) | public |
| Install, run, test, lint, serve, preprocess or ingest | `COMMANDS.md` | local only |
| Do the next piece of work | one file in `next_steps/` (decided work; the owner names which file) | files local only |
| (never act on these) | `discussions/`: one file per open topic still being discussed | files local only |

## Inside `architecture/`: all public

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

These files began as a verbatim split of the old `CLAUDE.md` "Architecture" section. Since then they have gained a few small edits and appended sections marked
"carried over from the retired `BLUEPRINT.md`". Cross-references such as "see X above/below" may point to another file here; `architecture/INDEX.md` maps section titles to files.

## Keeping this folder healthy

- New significant decision: append it to `DECISIONS.md` with a date. Not to `CLAUDE.md`.
- New must-not-break rule: add a row to `INVARIANTS.md` and say what enforces it.
- Changed behavior described in an `architecture/` file: update that file in the same change.
- Keep `CLAUDE.md` short. If a paragraph is only needed for one kind of task, it belongs here.
- Write files for Claude Code in English (`COMMANDS.md`, `DECISIONS.md`, `INVARIANTS.md`, `architecture/`), and write both `next_steps/` and
  `discussions/` items in English too, so a file can move between them unchanged. Only `GUIDE.md` is Chinese, for the owner.
- `next_steps/` and `discussions/` hold one file per item, with no numbering and no implied order; priority changes at any time.
  A topic moves from `discussions/` to `next_steps/` by moving its file; do not rename it.
