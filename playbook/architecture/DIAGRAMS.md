# Diagrams

> **Load when:** you need the shape of the system at a glance (data flow, routes, threshold routing, Career membership, pinned-impact outcomes, the Claude Code gate), or you add, change or remove a diagram.
> Every diagram here restates text that lives in another `architecture/` file, named under it. The text and the code win: if a diagram disagrees with them, fix the diagram in the same change.
> GitHub renders the Mermaid blocks. Keep node labels in double quotes and free of `<`, `>` and `|`, so every renderer accepts them.

## Data pipeline

Detail: `BACKEND-AND-DEPLOY.md`. Raw PFF files stay on the owner's machine (INVARIANT 13).

```mermaid
flowchart LR
    csv["Raw PFF CSV<br/>data/league/category/season.csv"]
    pre["preprocessing/preprocess.py<br/>front_7.py, offensive_line.py"]
    xlsx["xlsx per season and position"]
    ing["database/db_ingestion.py<br/>delete and reinsert one slice"]
    db[("SQLite locally<br/>Postgres on Railway")]
    api["main.py<br/>FastAPI JSON API"]
    web["frontend/<br/>vanilla JS, ES modules"]

    csv --> pre --> xlsx --> ing --> db --> api --> web
```

## Ingestion order

Detail: `BACKEND-AND-DEPLOY.md`, "Career members". The college run rebuilds the Career members by comparing with the NFL tables, so the NFL run goes first when both run.

```mermaid
flowchart TD
    nfl["1. Ingest NFL seasons"]
    ncaaf["2. Ingest NCAAF seasons"]
    members["3. Rebuild Career members<br/>whole, never incrementally"]
    stale["An NFL-only run leaves Joined NFL stale<br/>until the next college run"]

    nfl --> ncaaf --> members
    nfl -.-> stale
```

## Pages and routes

Detail: `PWA.md`, `BACKEND-AND-DEPLOY.md`. `/` is always the NFL Season page and the PWA `start_url` stays `/` (INVARIANT 8).

```mermaid
flowchart LR
    subgraph pages ["Pages (same index.html, rendered per page)"]
        p1["/ NFL Season"]
        p2["/ncaaf-season"]
        p3["/ncaaf-career"]
    end

    subgraph apis ["JSON API (never cached by the Service Worker)"]
        a1["/api/nfl"]
        a2["/api/ncaaf"]
        a3["/api/ncaaf/career"]
        h["/health"]
    end

    sw["/sw.js<br/>network-first with a timeout"]

    p1 --> a1
    p2 --> a2
    p3 --> a3
    pages -.-> sw
```

## Threshold routing

Detail: `THRESHOLDS.md`. Routing compares calendar years, not the schedule. The threshold only gates the display (INVARIANT 5).

```mermaid
flowchart TD
    start["resolve_default_threshold<br/>category, season, league"]
    current{"season equals<br/>the current calendar year?"}
    entry{"the league has a dynamic entry<br/>for that season and category?"}
    dynamic["Use the hand-set dynamic value<br/>edited each week"]
    static["Use the static default<br/>of that league"]

    start --> current
    current -- yes --> entry
    current -- no --> static
    entry -- yes --> dynamic
    entry -- no --> static
```

## Career membership

Detail: `BACKEND-AND-DEPLOY.md`, `database/career.py`. The two statuses never overlap. On the Career page each player must clear the bar of his own status.

```mermaid
flowchart TD
    player["A college player"]
    joined{"player_id also in the NFL table<br/>of the same category?"}
    latest{"has a row in the latest<br/>college season in the table?"}
    jn["Joined NFL"]
    pr["Prospects"]
    out["Not a Career member"]

    player --> joined
    joined -- yes --> jn
    joined -- no --> latest
    latest -- yes --> pr
    latest -- no --> out
```

## Pinned-impact outcomes

Detail: `PINNED-INVALIDATION.md`, `pinned-impact.js` (INVARIANTS 9 and 17). Judged once, on the final filter combination, when Apply is pressed.

```mermaid
flowchart TD
    apply["Apply with pending filters"]
    reset_cp{"Category or Position<br/>changed?"}
    looser{"Same season with an equal<br/>or looser bar?"}
    check["Check each pinned player<br/>in the pending pool, same exact position,<br/>meets the bar"]
    fits{"How many fail?"}

    reset["reset<br/>confirm, then clear everything"]
    unaffected["unaffected<br/>apply silently"]
    refresh["refresh<br/>toast, re-point cards to the new season"]
    partial["partial<br/>confirm, remove only the failures"]

    apply --> reset_cp
    reset_cp -- yes --> reset
    reset_cp -- no --> looser
    looser -- yes --> unaffected
    looser -- no --> check --> fits
    fits -- none --> refresh
    fits -- some --> partial
    fits -- all --> reset
```

A `partial` outcome also decides each Comparison: two or more members left means it shrinks, fewer than two means it dissolves.

## Claude Code Stop gate

Detail: `CLAUDE-HOOKS.md`. The gate is for local Claude Code sessions; GitHub Actions runs the full set on every push either way.

```mermaid
flowchart TD
    stop["Claude tries to stop"]
    marker{"Session marker exists?<br/>a write under the repo was seen"}
    run["Run in parallel:<br/>black -S --check, lint:js,<br/>format:js:check, test:js, pytest not browser,<br/>and, if a browser-relevant file was written,<br/>the browser tests in Novita sandboxes"]
    ok{"Every check passed?<br/>(sandbox unavailable = warning, not failure)"}
    again{"stop_hook_active already set<br/>this turn?"}
    done["Delete the marker and let Claude stop"]
    block["Block: report each failed step<br/>and the output tail"]
    warn["Only warn, and let Claude stop<br/>so a check that cannot pass cannot loop"]
    skip["Run nothing and let Claude stop"]

    stop --> marker
    marker -- no --> skip
    marker -- yes --> run --> ok
    ok -- yes --> done
    ok -- no --> again
    again -- no --> block
    again -- yes --> warn
```
