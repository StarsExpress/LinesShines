"""Game of Trenches API + static frontend, single deployable FastAPI service.

Routes (one set per league, {league} is nfl or ncaaf):
  GET  /api/{league}/metadata           → seasons, positions, metric defs, teams
                                           (ncaaf adds each season's conferences)
  GET  /api/{league}/pass_rush?season=[&position=] → records; position omitted →
                                           every position in the category (client
                                           partitions/filters from there)
  GET  /api/{league}/pass_block?season=[&position=] → same shape as pass_rush
  GET  /health                          → readiness probe for Railway
  GET  /, /ncaaf-season                 → the page of each league's season view

Anything else falls through to StaticFiles serving `frontend/`.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from config import (
    ALLOWED_HAVOC_RATE_NOTE,
    HAVOC_RATE_NOTE,
    PASS_COV_PERCENT_NOTE,
    PBE_NOTE,
    PRP_NOTE,
    TPS_NOTE,
    League,
    resolve_default_threshold,
)
from database.db_models import (
    Base,
    NCAAFPassBlockStat,
    NCAAFPassRushStat,
    NCAAFTeam,
    NFLPassBlockStat,
    NFLPassRushStat,
    NFLTeam,
    ncaaf_pass_block_row_to_dict,
    ncaaf_pass_rush_row_to_dict,
    pass_block_row_to_dict,
    pass_rush_row_to_dict,
)
from database.session import SessionLocal, engine
from teams.ncaaf import SCOPED_CONFERENCES

# Railway sets this per-deploy; falls back to "dev" for local runs. Used to
# cache-bust static assets referenced from index.html so iOS Safari (and
# other aggressive mobile caches) pick up new JS/CSS/Plotly after a deployment
# instead of serving a stale bundle against a changed API.
COMMIT_SHA = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:7]


# ---- Database wiring lives in database/session.py. --------------------------


# ---- Static metric/position descriptions (schema-level, not row-level). -----

PASS_RUSH_POSITIONS = {"ED": "Edge", "DI": "Defensive Interior"}
PASS_BLOCK_POSITIONS = {"T": "Offensive Tackle", "G": "Guard", "C": "Center"}

PASS_RUSH_METRICS = {
    "Win Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Pass rush win rate",
    },
    "TPS Win Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Win rate on true pass sets",
    },
    "Pressure Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Pressures / pass rush opportunities",
    },
    "TPS Pressure Rate": {
        "unit": "%",
        "higher_is_better": True,
        "pff_note": "Pressure rate on true pass sets",
    },
    "Havoc Rate": {
        "unit": "%",
        "higher_is_better": True,
        "note": HAVOC_RATE_NOTE,
        "formula_svg": "/images/metric_formulas/havoc_rate.svg",
        "pff_note": "(Sacks + Hits) / pass rush opportunities",
    },
    "TPS Havoc Rate": {
        "unit": "%",
        "higher_is_better": True,
        "note": HAVOC_RATE_NOTE,
        "formula_svg": "/images/metric_formulas/havoc_rate.svg",
        "pff_note": "Havoc rate on true pass sets",
    },
    "PRP": {
        "unit": "",
        "higher_is_better": True,
        "formula_note": PRP_NOTE,
        "formula_svg": "/images/metric_formulas/prp.svg",
        "pff_note": "PFF Pass Rush Productivity",
    },
    "TPS PRP": {
        "unit": "",
        "higher_is_better": True,
        "formula_note": PRP_NOTE,
        "formula_svg": "/images/metric_formulas/prp.svg",
        "pff_note": "Pass rush productivity on true pass sets",
    },
    # `line_summary: False` keeps both out of the Linemate Card's Line Summary
    # (Min/Median/Max/RSWA): a line mixes ED and DI, whose coverage shares sit in
    # very different ranges, so one summary number would compare them unfairly.
    # Bonus, so it comes last (axis pickers and the Comparison and Linemate
    # cards follow this order; the Player Card also puts it in its own section).
    # Neutral: it describes how wide a rusher's job is (how often he drops into
    # coverage rather than rushing), not how well he does it, so the cards show
    # it without the percentile Color Code (`neutral`). Higher is better only sets
    # direction: rank 1 is the highest value, because a lineman who covers on more
    # pass plays carries more of the pass defence.
    "Pass Cov Percent": {
        "unit": "%",
        "higher_is_better": True,
        "neutral": True,
        "bonus": True,
        "line_summary": False,
        "note": PASS_COV_PERCENT_NOTE,
        "pff_note": "Frequency of dropping into coverage on pass plays",
    },
    "TPS Pass Cov Percent": {
        "unit": "%",
        "higher_is_better": True,
        "neutral": True,
        "bonus": True,
        "line_summary": False,
        "note": PASS_COV_PERCENT_NOTE,
        "pff_note": "Pass cov percent on true pass sets",
    },
}

PASS_BLOCK_METRICS = {
    "Allowed Pressure %": {
        "unit": "%",
        "higher_is_better": False,
        "pff_note": "Pressures allowed / non-spike pass block snaps",
    },
    "TPS Allowed Pressure %": {
        "unit": "%",
        "higher_is_better": False,
        "pff_note": "Allowed pressure rate on true pass sets",
    },
    "Allowed Havoc %": {
        "unit": "%",
        "higher_is_better": False,
        "note": ALLOWED_HAVOC_RATE_NOTE,
        "formula_svg": "/images/metric_formulas/allowed_havoc_rate.svg",
        "pff_note": "(Sacks + Hits) allowed / non-spike snaps",
    },
    "TPS Allowed Havoc %": {
        "unit": "%",
        "higher_is_better": False,
        "note": ALLOWED_HAVOC_RATE_NOTE,
        "formula_svg": "/images/metric_formulas/allowed_havoc_rate.svg",
        "pff_note": "Allowed havoc rate on true pass sets",
    },
    "PBE": {
        "unit": "",
        "higher_is_better": True,
        "formula_note": PBE_NOTE,
        "formula_svg": "/images/metric_formulas/pbe.svg",
        "pff_note": "PFF Pass Block Efficiency",
    },
    "TPS PBE": {
        "unit": "",
        "higher_is_better": True,
        "formula_note": PBE_NOTE,
        "formula_svg": "/images/metric_formulas/pbe.svg",
        "pff_note": "Pass block efficiency on true pass sets",
    },
}


# ---- FastAPI app. -----------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if missing.
    # Real schema migrations belong in Alembic once schema starts evolving.
    Base.metadata.create_all(engine)
    yield


# ---- League API: one router factory, used by the NFL and NCAAF. -------------


@dataclass(frozen=True)
class _CategoryApi:
    """One stat category's API wiring for a league."""

    key: str  # Payload key, "category" field, and resolve_default_threshold key.
    model: type
    positions: dict
    metrics: dict
    threshold_field: str
    order_attr: str  # Model attribute to sort records by, descending.
    row_to_dict: object


@dataclass(frozen=True)
class _LeagueApi:
    """A league's team table and its two stat categories."""

    league: League
    team_model: type
    team_id_attr: str  # The team table's key: NFL code, NCAAF franchise_id.
    categories: tuple
    has_conferences: bool = False  # NCAAF rows carry a conference per season.


def _conference_payload(sess, league: _LeagueApi) -> dict:
    """Each season's conference of every school with rows, for the Teams checklist.

    `team_conferences` is {season: {team: conference}}, read from the rows
    themselves, so it is exactly the data that was loaded; `conference_order` is
    the column order of the checklist.
    """
    team_conferences = dict()

    for category in league.categories:
        rows = sess.execute(
            select(
                category.model.season,
                category.model.team_code,
                category.model.conference,
            ).distinct()
        )
        for season, team_code, conference in rows:
            team_conferences.setdefault(season, dict())[team_code] = conference

    return {
        "conference_order": list(SCOPED_CONFERENCES),
        "team_conferences": team_conferences,
    }


def build_api_router(league: _LeagueApi) -> APIRouter:
    """Build /metadata, /pass_rush and /pass_block for one league.

    Mounted under a league prefix (/api/nfl, /api/ncaaf) by the caller.
    """
    router = APIRouter()
    categories = {category.key: category for category in league.categories}

    @router.get("/metadata")
    def metadata() -> dict:
        with SessionLocal() as sess:
            category_payload = {}

            for category in league.categories:
                seasons = sorted(
                    {
                        season
                        for (season,) in sess.execute(
                            select(category.model.season).distinct()
                        )
                    },
                    reverse=True,
                )

                category_payload[category.key] = {
                    "positions": category.positions,
                    "metrics": category.metrics,
                    "threshold_field": category.threshold_field,
                    "seasons": seasons,
                    "default_thresholds": {
                        season: resolve_default_threshold(
                            category.key, season, league.league
                        )
                        for season in seasons
                    },
                }

            teams = sess.execute(select(league.team_model)).scalars().all()
            conference_payload = (
                _conference_payload(sess, league) if league.has_conferences else {}
            )

        return {
            # Same Calendar Year comparison resolve_default_threshold() uses to
            # route a season to the static vs. dynamic threshold (see config/thresholds.py) —
            # exposed here so the frontend can classify a season as "ongoing" vs
            # "historical" the same way, without duplicating a date.today().year
            # call client-side (which would drift out of sync with whatever this
            # process actually resolved thresholds against, e.g. across a stale
            # page left open over a year boundary).
            "current_year": date.today().year,
            # Shared across every "TPS "-prefixed metric, not a per-metric
            # formula — exposed once here rather than duplicated into each
            # metric's own note. The frontend appends this to a TPS metric's own
            # formula/note whenever the selected axis metric name starts with
            # "TPS " (see main.js's axisFormulaContent()).
            "tps_note": TPS_NOTE,
            **category_payload,
            **conference_payload,
            "teams": {
                getattr(team, league.team_id_attr): {
                    "full_name": team.full_name,
                    "primary_color": team.primary_color,
                }
                for team in teams
            },
        }

    def category_records(category: _CategoryApi, season: int, position) -> dict:
        if position is not None and position not in category.positions:
            raise HTTPException(
                400,
                f"invalid position: {position!r} — choose from {list(category.positions)}",
            )

        filters = [category.model.season == season]

        # Omitted position means "every supported position", not literally every
        # row for the season — the table can carry positions the category does
        # not expose (e.g. LB), left over from a broader raw ingest.

        filters.append(
            category.model.position == position
            if position is not None
            else category.model.position.in_(category.positions)
        )

        with SessionLocal() as sess:
            rows = (
                sess.execute(
                    select(category.model)
                    .where(*filters)
                    .order_by(getattr(category.model, category.order_attr).desc())
                )
                .scalars()
                .all()
            )

        return {
            "category": category.key,
            "season": season,
            "position": position,
            "records": [category.row_to_dict(row) for row in rows],
        }

    @router.get("/pass_rush")
    def pass_rush(
        season: int = Query(..., ge=1980, le=2100),
        position: str | None = Query(None, min_length=1, max_length=4),
    ) -> dict:
        return category_records(categories["pass_rush"], season, position)

    @router.get("/pass_block")
    def pass_block(
        season: int = Query(..., ge=1980, le=2100),
        position: str | None = Query(None, min_length=1, max_length=4),
    ) -> dict:
        return category_records(categories["pass_block"], season, position)

    return router


NFL_API = _LeagueApi(
    league=League.NFL,
    team_model=NFLTeam,
    team_id_attr="code",
    categories=(
        _CategoryApi(
            key="pass_rush",
            model=NFLPassRushStat,
            positions=PASS_RUSH_POSITIONS,
            metrics=PASS_RUSH_METRICS,
            threshold_field="PR Opp",
            order_attr="pr_opp",
            row_to_dict=pass_rush_row_to_dict,
        ),
        _CategoryApi(
            key="pass_block",
            model=NFLPassBlockStat,
            positions=PASS_BLOCK_POSITIONS,
            metrics=PASS_BLOCK_METRICS,
            threshold_field="Non Spike PB Snaps",
            order_attr="non_spike_pb_snaps",
            row_to_dict=pass_block_row_to_dict,
        ),
    ),
)

NCAAF_API = _LeagueApi(
    league=League.NCAAF,
    team_model=NCAAFTeam,
    team_id_attr="franchise_id",
    has_conferences=True,
    categories=(
        _CategoryApi(
            key="pass_rush",
            model=NCAAFPassRushStat,
            positions=PASS_RUSH_POSITIONS,
            metrics=PASS_RUSH_METRICS,
            threshold_field="PR Opp",
            order_attr="pr_opp",
            row_to_dict=ncaaf_pass_rush_row_to_dict,
        ),
        _CategoryApi(
            key="pass_block",
            model=NCAAFPassBlockStat,
            positions=PASS_BLOCK_POSITIONS,
            metrics=PASS_BLOCK_METRICS,
            threshold_field="Non Spike PB Snaps",
            order_attr="non_spike_pb_snaps",
            row_to_dict=ncaaf_pass_block_row_to_dict,
        ),
    ),
)


app = FastAPI(
    title="Game of Trenches API",
    description="PFF-derived front-7 & O-line metrics for the LinesShines dashboard.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# One router per league from the same factory, each under its own prefix.
app.include_router(build_api_router(NFL_API), prefix="/api/nfl")
app.include_router(build_api_router(NCAAF_API), prefix="/api/ncaaf")


# ---- Pages: one per league view, all served from frontend/index.html. -------


@dataclass(frozen=True)
class _Page:
    """One page of the site: its URL, the league it shows and its own texts."""

    path: str
    league: League
    nav_label: str
    eyebrow: str  # The line under the title; differs per league and mode.
    tab_title: str
    description: str
    scope_segment: str  # Extra item of the meta band, "" for none.
    team_groups: str  # "static" (frontend list) or "by_season" (from metadata).
    team_label: str  # "code" shows the team key, "name" shows the full name.


NCAAF_SCOPE_SEGMENT = "&nbsp;&nbsp;·&nbsp;&nbsp;Scope: SEC · B1G · ACC · Big 12 · Pac-12 · MAC · Notre Dame"

# The order is the order of the navigation buttons.
PAGES = (
    _Page(
        path="/",
        league=League.NFL,
        nav_label="NFL Season",
        eyebrow="🏈NFL OL & DL PFF Premium Stats Interactive Exploration",
        tab_title="LinesShines · 鋒光",
        description="Interactive exploration platform: NFL OL & DL PFF metrics.",
        scope_segment="",
        team_groups="static",
        team_label="code",
    ),
    _Page(
        path="/ncaaf-season",
        league=League.NCAAF,
        nav_label="NCAAF Season",
        eyebrow="🏈NCAAF OL & DL PFF Premium Stats Interactive Exploration",
        tab_title="LinesShines · 鋒光 · NCAAF",
        description="Interactive exploration platform: NCAAF OL & DL PFF metrics.",
        scope_segment=NCAAF_SCOPE_SEGMENT,
        team_groups="by_season",
        team_label="name",
    ),
)


def _league_config_json(page: _Page) -> str:
    """The `LEAGUE` object the frontend reads, as JSON safe inside a script tag."""
    config = {
        "key": page.league.value,
        "name": page.league.value.upper(),
        "apiPrefix": f"/api/{page.league.value}",
        "logoDir": page.league.value,
        "teamGroups": page.team_groups,
        "teamLabel": page.team_label,
    }

    return json.dumps(config).replace("</", "<\\/")


def _navigation_html(current: _Page) -> str:
    """The page switch: inline links on wide screens, a hamburger list on narrow ones."""
    items = []
    for page in PAGES:
        is_current = page.path == current.path
        current_attribute = ' aria-current="page"' if is_current else ""
        current_class = " is-current" if is_current else ""
        items.append(
            f'<li><a class="league-nav-link{current_class}" href="{page.path}"'
            f"{current_attribute}>{page.nav_label}</a></li>"
        )

    return (
        '<nav class="league-nav" aria-label="Pages">'
        '<button type="button" class="league-nav-toggle" id="league-nav-toggle" '
        'aria-expanded="false" aria-controls="league-nav-list">'
        '<span class="league-nav-bars" aria-hidden="true"></span>'
        f"<span>{current.nav_label}</span></button>"
        f'<ul class="league-nav-list" id="league-nav-list">{"".join(items)}</ul>'
        "</nav>"
    )


def render_page(template: str, page: _Page) -> str:
    """Fill a page's own texts, navigation and league config into index.html."""
    replacements = {
        "{{VERSION}}": COMMIT_SHA,
        "{{PAGE_TITLE}}": page.tab_title,
        "{{PAGE_DESCRIPTION}}": page.description,
        "{{EYEBROW}}": page.eyebrow,
        "{{SCOPE_SEGMENT}}": (
            f'<span class="meta-segment">{page.scope_segment}</span>'
            if page.scope_segment
            else ""
        ),
        "{{LEAGUE_NAV}}": _navigation_html(page),
        "{{LEAGUE_JSON}}": _league_config_json(page),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template


# ---- Static frontend (mounted LAST so /api/* routes above win). -------------


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that makes the browser revalidate before reusing a file.

    Plain StaticFiles sends only etag and last-modified, so a browser may
    reuse a cached module for a "heuristic" time after a deploy and pair a new
    main.js with an old module. "no-cache" means "ask the server first", not
    "do not cache": an unchanged file costs one conditional request (304).
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


_here = Path(__file__).parent

# Team logos live in frontend/images/team_logos/.

_logo_candidates = [
    _here / "frontend" / "images" / "team_logos",
]

for _logos_dir in _logo_candidates:
    if _logos_dir.exists() and _logos_dir.is_dir():
        app.mount("/logos", StaticFiles(directory=str(_logos_dir)), name="logos")
        break

_frontend_dir = _here / "frontend"
if _frontend_dir.exists():
    _index_path = _frontend_dir / "index.html"

    def _page_route(page: _Page):
        def serve_page() -> HTMLResponse:
            return HTMLResponse(
                render_page(_index_path.read_text(), page),
                headers={"Cache-Control": "no-cache"},
            )

        return serve_page

    for _page in PAGES:
        app.add_api_route(
            _page.path,
            _page_route(_page),
            methods=["GET"],
            response_class=HTMLResponse,
            include_in_schema=False,
        )

    _sw_path = _frontend_dir / "sw.js"

    @app.get("/sw.js")
    def serve_sw() -> Response:
        # sw.js carries {{VERSION}} placeholder just as index.html (both
        # its cache name and its precache URLs' ?v= query strings), so it
        # needs identical substitution — without this route it would
        # fall through to plain StaticFiles mount below, which serves
        # files byte-for-byte with no templating, leaving literal string
        # "{{VERSION}}" in installed worker forever. Browsers already
        # re-check a service worker script at most every 24h regardless of
        # HTTP caching headers, but Cache-Control: no-cache is set anyway so
        # an intermediate/CDN cache can't extend that window further.
        return Response(
            content=_sw_path.read_text().replace("{{VERSION}}", COMMIT_SHA),
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    app.mount(
        "/",
        NoCacheStaticFiles(directory=str(_frontend_dir), html=True),
        name="frontend",
    )

else:

    @app.get("/")
    def _no_frontend() -> JSONResponse:
        return JSONResponse(
            {"message": "frontend/ folder not found; API endpoints under /api/*."},
            status_code=200,
        )
