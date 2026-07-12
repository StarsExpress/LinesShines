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
    resp = client.get("/logos/ARZ.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_frontend_mounted_at_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
