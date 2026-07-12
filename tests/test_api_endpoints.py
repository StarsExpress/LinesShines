"""API-level tests against a seeded in-memory-equivalent sqlite DB."""
from __future__ import annotations


def test_metadata_shape(client, seeded_db):
    resp = client.get("/api/metadata")
    assert resp.status_code == 200
    body = resp.json()

    assert 2025 in body["pass_rush"]["seasons"]
    assert 2025 in body["pass_block"]["seasons"]
    assert "BUF" in body["teams"]
    assert body["teams"]["BUF"]["full_name"] == "Buffalo Bills"


def test_pass_rush_returns_seeded_row(client, seeded_db):
    resp = client.get("/api/pass_rush", params={"season": 2025, "position": "ED"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["season"] == 2025
    assert body["position"] == "ED"
    assert len(body["records"]) == 1
    assert body["records"][0]["team"] == "BUF"
    assert body["records"][0]["PR Opp"] == 300


def test_pass_rush_rejects_unknown_position(client, seeded_db):
    resp = client.get("/api/pass_rush", params={"season": 2025, "position": "XX"})
    assert resp.status_code == 400


def test_pass_rush_requires_query_params(client):
    resp = client.get("/api/pass_rush")
    assert resp.status_code == 422


def test_pass_block_returns_seeded_row(client, seeded_db):
    resp = client.get("/api/pass_block", params={"season": 2025, "position": "T"})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["records"]) == 1
    assert body["records"][0]["team"] == "MIA"
    assert body["records"][0]["Non Spike PB Snaps"] == 500


def test_pass_block_rejects_unknown_position(client, seeded_db):
    resp = client.get("/api/pass_block", params={"season": 2025, "position": "XX"})
    assert resp.status_code == 400


def test_pass_rush_unknown_season_returns_empty(client, seeded_db):
    resp = client.get("/api/pass_rush", params={"season": 1999, "position": "ED"})
    assert resp.status_code == 200
    assert resp.json()["records"] == []
