"""Health, auth, and /me tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_me_requires_token(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["login"] == "alice"
    assert body["github_id"] == 4242
    assert body["elo"] == pytest.approx(1500.0)


def test_invalid_token_rejected(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_dev_token_issuance(client: TestClient) -> None:
    r = client.post(
        "/api/auth/dev-token",
        json={"github_id": 1, "login": "carol"},
    )
    assert r.status_code == 200
    token = r.json()["token"]
    r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["login"] == "carol"
