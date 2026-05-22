"""Bot upload / list / delete tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.conftest import make_bot_zip


def _upload(client: TestClient, headers: dict[str, str], name: str = "my-bot") -> dict[str, object]:
    files = {"artifact": (f"{name}.zip", make_bot_zip(), "application/zip")}
    r = client.post("/api/bots", headers=headers, files=files, data={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_and_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    out = _upload(client, auth_headers, "first-bot")
    assert out["name"] == "first-bot"
    assert out["version"] == 1
    assert out["status"] == "ready"

    r = client.get("/api/bots/mine", headers=auth_headers)
    assert r.status_code == 200
    bots = r.json()
    assert len(bots) == 1
    assert bots[0]["name"] == "first-bot"


def test_upload_bumps_version(client: TestClient, auth_headers: dict[str, str]) -> None:
    _upload(client, auth_headers, "iter-bot")
    second = _upload(client, auth_headers, "iter-bot")
    assert second["version"] == 2


def test_zip_must_contain_bot_py(client: TestClient, auth_headers: dict[str, str]) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("not_bot.py", "BOT = None\n")
    files = {"artifact": ("bot.zip", buf.getvalue(), "application/zip")}
    r = client.post("/api/bots", headers=auth_headers, files=files, data={"name": "broken"})
    assert r.status_code == 400


def test_zip_rejects_path_traversal(client: TestClient, auth_headers: dict[str, str]) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.py", "")
        zf.writestr("bot.py", "BOT = None")
    files = {"artifact": ("bot.zip", buf.getvalue(), "application/zip")}
    r = client.post("/api/bots", headers=auth_headers, files=files, data={"name": "evil"})
    assert r.status_code == 400


def test_delete_requires_owner(
    client: TestClient,
    auth_headers: dict[str, str],
    another_user_headers: dict[str, str],
) -> None:
    out = _upload(client, auth_headers, "owned-bot")
    bot_id = out["id"]
    r = client.delete(f"/api/bots/{bot_id}", headers=another_user_headers)
    assert r.status_code == 403


def test_delete_disables_bot(client: TestClient, auth_headers: dict[str, str]) -> None:
    out = _upload(client, auth_headers, "to-delete")
    bot_id = out["id"]
    r = client.delete(f"/api/bots/{bot_id}", headers=auth_headers)
    assert r.status_code == 204
    bots = client.get("/api/bots", params={"owner_id": out["owner_id"]}).json()
    assert any(b["id"] == bot_id and b["status"] == "disabled" for b in bots)


def test_unauthenticated_upload_rejected(client: TestClient) -> None:
    files = {"artifact": ("bot.zip", make_bot_zip(), "application/zip")}
    r = client.post("/api/bots", files=files, data={"name": "noauth"})
    assert r.status_code == 401
