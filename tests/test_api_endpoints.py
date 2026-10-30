"""API-level tests against a seeded in-memory-equivalent sqlite DB."""

from __future__ import annotations
from datetime import date
from config import DEFAULT_THRESHOLDS, NCAAF_DEFAULT_THRESHOLDS


def test_metadata_shape(client, seeded_db):
    resp = client.get("/api/nfl/metadata")
    assert resp.status_code == 200
    body = resp.json()

    assert 2025 in body["pass_rush"]["seasons"]
    assert 2025 in body["pass_block"]["seasons"]
    assert "BUF" in body["teams"]
    assert body["teams"]["BUF"]["full_name"] == "Buffalo Bills"

    # Exposed so the frontend can classify a season as ongoing vs. historical
    # the same way resolve_default_threshold() does, without a second,
    # potentially-drifting date.today().year call of its own.
    assert body["current_year"] == date.today().year

    # 2025 is a finalized season: safely in the past relative to any plausible "today".
    # Should carry the static default, not a dynamic one. See config.py's resolve_default_threshold.
    assert (
        body["pass_rush"]["default_thresholds"]["2025"]
        == DEFAULT_THRESHOLDS["pass_rush"]
    )

    assert (
        body["pass_block"]["default_thresholds"]["2025"]
        == DEFAULT_THRESHOLDS["pass_block"]
    )


def test_pass_rush_returns_seeded_row(client, seeded_db):
    resp = client.get("/api/nfl/pass_rush", params={"season": 2025, "position": "ED"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["season"] == 2025
    assert body["position"] == "ED"

    assert len(body["records"]) == 1
    assert body["records"][0]["team"] == "BUF"
    assert body["records"][0]["PR Opp"] == 300


def test_pass_rush_rejects_unknown_position(client, seeded_db):
    resp = client.get("/api/nfl/pass_rush", params={"season": 2025, "position": "XX"})
    assert resp.status_code == 400


def test_pass_rush_no_position_returns_all_positions(client, seeded_db):
    resp = client.get("/api/nfl/pass_rush", params={"season": 2025})
    assert resp.status_code == 200
    body = resp.json()

    assert body["position"] is None
    positions = {r["position"] for r in body["records"]}
    assert positions == {"ED", "DI"}
    assert len(body["records"]) == 2


def test_pass_rush_requires_query_params(client):
    resp = client.get("/api/nfl/pass_rush")
    assert resp.status_code == 422


def test_pass_block_returns_seeded_row(client, seeded_db):
    resp = client.get("/api/nfl/pass_block", params={"season": 2025, "position": "T"})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["records"]) == 1
    assert body["records"][0]["team"] == "MIA"
    assert body["records"][0]["Non Spike PB Snaps"] == 500


def test_pass_block_rejects_unknown_position(client, seeded_db):
    resp = client.get("/api/nfl/pass_block", params={"season": 2025, "position": "XX"})
    assert resp.status_code == 400


def test_pass_block_no_position_returns_all_positions(client, seeded_db):
    resp = client.get("/api/nfl/pass_block", params={"season": 2025})
    assert resp.status_code == 200
    body = resp.json()

    assert body["position"] is None
    positions = {r["position"] for r in body["records"]}
    assert positions == {"T", "G"}
    assert len(body["records"]) == 2


def test_pass_rush_unknown_season_returns_empty(client, seeded_db):
    resp = client.get("/api/nfl/pass_rush", params={"season": 1999, "position": "ED"})
    assert resp.status_code == 200
    assert resp.json()["records"] == []


def test_pass_cov_percent_metrics_are_higher_is_better_neutral_and_listed_last(
    client, seeded_db
):
    metrics = client.get("/api/nfl/metadata").json()["pass_rush"]["metrics"]
    keys = list(metrics)

    # Axis pickers and the Comparison and Linemate cards follow this order: the
    # bonus metrics come after every required one.
    assert keys[-3:] == ["TPS PRP", "Pass Cov Percent", "TPS Pass Cov Percent"]

    for key in ("Pass Cov Percent", "TPS Pass Cov Percent"):
        assert metrics[key]["higher_is_better"] is True
        assert metrics[key]["neutral"] is True

    # No other metric is neutral: they all keep their Color Code.
    others = [k for k in keys if "Pass Cov Percent" not in k]
    assert not any(metrics[k].get("neutral") for k in others)
    assert not any(
        m.get("neutral")
        for m in client.get("/api/nfl/metadata")
        .json()["pass_block"]["metrics"]
        .values()
    )


def test_only_the_two_pass_cov_metrics_are_bonus(client, seeded_db):
    meta = client.get("/api/nfl/metadata").json()
    bonus = [k for k, m in meta["pass_rush"]["metrics"].items() if m.get("bonus")]

    assert bonus == ["Pass Cov Percent", "TPS Pass Cov Percent"]
    assert not any(m.get("bonus") for m in meta["pass_block"]["metrics"].values())


def test_pass_cov_percent_popup_text_and_no_card_note(client, seeded_db):
    meta = client.get("/api/nfl/metadata").json()
    metrics = meta["pass_rush"]["metrics"]

    assert (
        metrics["Pass Cov Percent"]["pff_note"]
        == "Frequency of dropping into coverage on pass plays"
    )

    for cat in ("pass_rush", "pass_block"):
        assert not any(m.get("card_note") for m in meta[cat]["metrics"].values())


def test_pass_rush_records_carry_player_id_and_pass_cov_percent(client, seeded_db):
    record = client.get(
        "/api/nfl/pass_rush", params={"season": 2025, "position": "ED"}
    ).json()["records"][0]

    assert record["player_id"] == 1001
    assert record["Pass Cov Percent"] == 8.0
    assert record["TPS Pass Cov Percent"] == 5.0


def test_pass_block_records_carry_player_id(client, seeded_db):
    record = client.get(
        "/api/nfl/pass_block", params={"season": 2025, "position": "T"}
    ).json()["records"][0]

    assert record["player_id"] == 2001


def test_the_old_unprefixed_routes_are_gone(client, seeded_db):
    assert client.get("/api/metadata").status_code == 404
    assert client.get("/api/pass_rush", params={"season": 2025}).status_code == 404
    assert client.get("/api/pass_block", params={"season": 2025}).status_code == 404


def test_the_nfl_metadata_has_no_conference_data(client, seeded_db):
    body = client.get("/api/nfl/metadata").json()

    assert "team_conferences" not in body
    assert "conference_order" not in body


def test_ncaaf_metadata_lists_seasons_schools_and_each_seasons_conferences(
    client, seeded_ncaaf_db
):
    body = client.get("/api/ncaaf/metadata").json()

    assert body["pass_rush"]["seasons"] == [2025, 2024]
    assert body["teams"]["102"]["full_name"] == "Akron"
    assert body["teams"]["103"]["primary_color"] is None
    assert body["conference_order"][:2] == ["SEC", "B1G"]
    assert body["team_conferences"]["2025"] == {"102": "MAC", "103": "SEC"}
    assert body["team_conferences"]["2024"] == {"102": "MAC"}


def test_ncaaf_default_thresholds_are_the_college_ones(client, seeded_ncaaf_db):
    body = client.get("/api/ncaaf/metadata").json()

    # 2024 is finalized, so it carries the static college default.
    assert (
        body["pass_rush"]["default_thresholds"]["2024"]
        == NCAAF_DEFAULT_THRESHOLDS["pass_rush"]
        == 230
    )
    assert (
        body["pass_block"]["default_thresholds"]["2025"]
        == NCAAF_DEFAULT_THRESHOLDS["pass_block"]
        == 360
    )


def test_ncaaf_records_carry_the_conference_and_the_franchise_id_as_team(
    client, seeded_ncaaf_db
):
    records = client.get(
        "/api/ncaaf/pass_rush", params={"season": 2025, "position": "ED"}
    ).json()["records"]

    assert {(r["team"], r["conference"]) for r in records} == {
        (102, "MAC"),
        (103, "SEC"),
    }
    assert {r["player_id"] for r in records} == {5001, 5002}


def test_ncaaf_pass_block_and_errors_mirror_the_nfl_routes(client, seeded_ncaaf_db):
    block = client.get("/api/ncaaf/pass_block", params={"season": 2025}).json()
    assert [r["conference"] for r in block["records"]] == ["SEC"]

    assert (
        client.get(
            "/api/ncaaf/pass_rush", params={"season": 2025, "position": "XX"}
        ).status_code
        == 400
    )
    assert client.get("/api/ncaaf/pass_rush").status_code == 422


def test_the_two_leagues_never_mix(client, seeded_db, seeded_ncaaf_db):
    nfl = client.get("/api/nfl/pass_rush", params={"season": 2025}).json()["records"]
    college = client.get("/api/ncaaf/pass_rush", params={"season": 2025}).json()[
        "records"
    ]

    assert {r["player_id"] for r in nfl} == {1001, 1002}
    assert {r["player_id"] for r in college} == {5001, 5002}
