"""Match scheduling tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.conftest import make_bot_zip


def _upload_bot(client: TestClient, headers: dict[str, str], name: str) -> int:
    files = {"artifact": (f"{name}.zip", make_bot_zip(), "application/zip")}
    r = client.post("/api/bots", headers=headers, files=files, data={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def test_schedule_match_creates_pending(client: TestClient, auth_headers: dict[str, str]) -> None:
    a = _upload_bot(client, auth_headers, "bot-a")
    b = _upload_bot(client, auth_headers, "bot-b")
    r = client.post(
        "/api/matches/schedule",
        headers=auth_headers,
        params={"run_now": False},
        json={"white_bot_id": a, "black_bot_id": b},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["white_bot_id"] == a
    assert body["black_bot_id"] == b
    assert body["result"] == "*"

    r2 = client.get(f"/api/matches/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


def test_schedule_match_rejects_self_play(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    a = _upload_bot(client, auth_headers, "duplicated")
    r = client.post(
        "/api/matches/schedule",
        headers=auth_headers,
        params={"run_now": False},
        json={"white_bot_id": a, "black_bot_id": a},
    )
    assert r.status_code == 400


def test_schedule_match_rejects_unknown_bot(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    a = _upload_bot(client, auth_headers, "only-one")
    r = client.post(
        "/api/matches/schedule",
        headers=auth_headers,
        params={"run_now": False},
        json={"white_bot_id": a, "black_bot_id": 9999},
    )
    assert r.status_code == 404


def test_list_matches_returns_recent_first(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    a = _upload_bot(client, auth_headers, "list-a")
    b = _upload_bot(client, auth_headers, "list-b")
    for _ in range(3):
        client.post(
            "/api/matches/schedule",
            headers=auth_headers,
            params={"run_now": False},
            json={"white_bot_id": a, "black_bot_id": b},
        )
    r = client.get("/api/matches")
    assert r.status_code == 200
    matches = r.json()
    assert len(matches) == 3
