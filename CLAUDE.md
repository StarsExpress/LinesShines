# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LinesShines · 鋒光 — a scatter-plot dashboard of PFF-derived pass-rush (front-7) and pass-block
(offensive-line) metrics for NFL players, 2022–2026. Single deployable FastAPI service (`main.py`)
that serves both the JSON API and the static frontend, backed by SQLite locally / Postgres on Railway.

## Commands

Install, run, test, lint, serve, preprocess, ingest and vendoring commands live in `playbook/COMMANDS.md`.
Read it before running any of them.

## Architecture in one line

Pipeline: raw PFF export → `preprocessing/` → xlsx → `database/db_ingestion.py` → DB → `main.py` API →
vanilla-JS frontend (`frontend/`, ES modules, no build step). Full detail is in `playbook/architecture/`.

## Read this first

Before any task, read `playbook/INVARIANTS.md`. It holds the working rules (git, order of work, definition of done,
PFF data, frontend limits, versioning) and the invariants that must stay true. Then use the table below to find the
detail for your task.

To find a work item or an architecture file, do not open whole folders. First read the top of each file (the title and one-line summary,
or the "Load when" line), then open only the ones that apply. The commands are in `playbook/ROSTER.md`.

## Where to look

Start at `playbook/ROSTER.md`. It maps each kind of task to the file that holds the detail:

| Task | File |
|---|---|
| Install, run, test, lint, serve, preprocess, ingest | `playbook/COMMANDS.md` |
| Add or change a test, or decide which test file to extend | `playbook/tests/INDEX.md` |
| Ingestion, DB models, API, deploy, tests | `playbook/architecture/BACKEND-AND-DEPLOY.md` |
| JS module layout and shared state | `playbook/architecture/FRONTEND-STRUCTURE.md` |
| Service Worker, manifest, caching, new routes | `playbook/architecture/PWA.md` |
| CSS layout, breakpoints, card drag/fold, PNG export | `playbook/architecture/UI-LAYOUT-AND-EXPORT.md` |
| Chart labels, dimming, axis direction | `playbook/architecture/CHART-RENDERING.md` |
| Pinned Players, Merge Cards, Linemate Cards | `playbook/architecture/CARDS.md` |
| Teams/Players filters and search | `playbook/architecture/FILTERS-AND-SEARCH.md` |
| Percentiles and ranks | `playbook/architecture/PERCENTILES.md` |
| Filter changes that remove pinned players | `playbook/architecture/PINNED-INVALIDATION.md` |
| Metrics, info popovers, metric notes | `playbook/architecture/METRICS-AND-NOTES.md` |
| Thresholds and the threshold input | `playbook/architecture/THRESHOLDS.md` |
