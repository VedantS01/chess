"""Leaderboard route tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.conftest import make_bot_zip


def test_leaderboard_bots_empty(client: TestClient) -> None:
    r = client.get("/api/leaderboard/bots")
    assert r.status_code == 200
    assert r.json() == []


def test_leaderboard_bots_lists_ready_bots(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    files = {"artifact": ("b.zip", make_bot_zip(), "application/zip")}
    client.post("/api/bots", headers=auth_headers, files=files, data={"name": "alpha"})
    r = client.get("/api/leaderboard/bots")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "alpha"


def test_leaderboard_users(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Hit /me to lazy-create the user record.
    client.get("/api/auth/me", headers=auth_headers)
    r = client.get("/api/leaderboard/users")
    assert r.status_code == 200
    assert len(r.json()) >= 1
