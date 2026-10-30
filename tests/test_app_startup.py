"""Smoke tests that the FastAPI app builds and mounts what it claims to."""

from __future__ import annotations
from starlette.routing import Mount
import main


def test_app_builds():
    assert main.app.title == "Game of Trenches API"


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_logos_mounted_at_expected_path():
    mounts = {r.path: r for r in main.app.routes if isinstance(r, Mount)}
    assert (
        "/logos" in mounts
    ), "no /logos static mount registered — check the mount candidates in main.py"


def test_logos_served_from_team_logos_dir(client):
    resp = client.get("/logos/nfl/ARZ.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_frontend_mounted_at_root(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_sw_js_served_with_version_substituted(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200

    assert resp.headers["content-type"] == "application/javascript"
    assert resp.headers["cache-control"] == "no-cache"

    assert "{{VERSION}}" not in resp.text
    assert f'"lines-shines-{main.COMMIT_SHA}"' in resp.text


def test_sw_js_never_caches_any_api_route(client):
    text = client.get("/sw.js").text

    # One rule for the whole /api/ prefix, so a route added later is covered automatically.
    assert 'const NEVER_CACHE_PREFIXES = ["/api/", "/health/"];' in text
    assert 'const NEVER_CACHE_PATHS = ["/health"];' in text
    assert "shouldBypassCache(url.pathname)" in text

    # The old per-endpoint list missed every new route, so it must stay gone.
    for old_prefix in ("/api/metadata", "/api/pass_rush", "/api/pass_block"):
        assert old_prefix not in text


def test_root_serves_the_nfl_page_and_pwa_start_url_stays_root(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "<title>LinesShines" in page.text
    assert (
        'value="pass_rush"' in page.text
    )  # The NFL category controls live at the root.

    manifest = client.get("/manifest.json").json()
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"


def test_index_html_registers_service_worker(client):
    resp = client.get("/")
    assert 'navigator.serviceWorker.register("/sw.js")' in resp.text


def test_frontend_files_must_be_revalidated(client):
    # Every file under the root mount, plus the routes that serve "/" and "/sw.js".
    paths = ["/", "/sw.js", "/main.js", "/filters.js", "/style.css", "/manifest.json"]
    for path in paths:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert resp.headers.get("cache-control") == "no-cache", path


def test_logos_mount_is_left_alone(client):
    resp = client.get("/logos/nfl/ARZ.png")
    assert resp.headers.get("cache-control") != "no-cache"


def test_sw_js_is_network_first_with_a_three_second_timeout(client):
    text = client.get("/sw.js").text
    assert "const NETWORK_TIMEOUT_MS = 3000;" in text


def test_each_season_page_is_filled_with_its_own_league(client):
    nfl = client.get("/").text
    ncaaf = client.get("/ncaaf-season").text

    assert '"key": "nfl"' in nfl and '"apiPrefix": "/api/nfl"' in nfl
    assert '"key": "ncaaf"' in ncaaf and '"apiPrefix": "/api/ncaaf"' in ncaaf
    assert '"teamLabel": "name"' in ncaaf

    # The subtitle (eyebrow) and the tab title differ per page.
    assert "NFL OL & DL PFF Premium Stats" in nfl
    assert "NCAAF OL & DL PFF Premium Stats" in ncaaf
    assert "<title>LinesShines · 鋒光</title>" in nfl
    assert "<title>LinesShines · 鋒光 · NCAAF</title>" in ncaaf

    # Only the college page states its data scope.
    assert "Scope:" in ncaaf and "Scope:" not in nfl


def test_no_placeholder_is_left_in_a_served_page(client):
    for path in ("/", "/ncaaf-season"):
        text = client.get(path).text
        assert "{{" not in text, path


def test_every_page_carries_the_navigation_with_its_own_page_marked(client):
    for path, current in (("/", "NFL Season"), ("/ncaaf-season", "NCAAF Season")):
        text = client.get(path).text

        assert 'class="league-nav"' in text
        assert 'href="/"' in text and 'href="/ncaaf-season"' in text
        assert text.count('aria-current="page"') == 1
        assert f'aria-current="page">{current}</a>' in text


def test_the_season_pages_are_not_cached_and_are_not_in_the_api_schema(client):
    assert client.get("/ncaaf-season").headers["cache-control"] == "no-cache"
    assert "/ncaaf-season" not in client.get("/openapi.json").text
