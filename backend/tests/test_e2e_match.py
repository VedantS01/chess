"""End-to-end test: upload two bots, schedule a match via HTTP, verify it runs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.tests.conftest import make_bot_zip


def _upload(client: TestClient, headers: dict[str, str], name: str, seed: int = 1) -> int:
    bot_py = f"from chesslab.bots.random_bot import RandomBot\nBOT = RandomBot(seed={seed})\n"
    files = {"artifact": (f"{name}.zip", make_bot_zip(bot_py), "application/zip")}
    r = client.post("/api/bots", headers=headers, files=files, data={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_schedule_runs_match_and_updates_leaderboard(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pin the runner to short budgets via direct settings monkey-patching so
    # we don't depend on env var refresh / module reloads.
    import backend.app.config as cfg
    import backend.app.match_runner as mr

    monkeypatch.setattr(cfg.settings, "runner_default_movetime_ms", 50, raising=False)
    monkeypatch.setattr(cfg.settings, "runner_max_plies", 40, raising=False)
    # Force in-process sandbox even if docker is installed.
    original = mr.run_bot_vs_bot

    def patched_run(white_bot, black_bot, movetime_ms=1000, max_plies=None, sandbox_cls=None):
        return original(
            white_bot,
            black_bot,
            movetime_ms=50,
            max_plies=40,
            sandbox_cls=mr.InProcessSandbox,
        )

    monkeypatch.setattr(mr, "run_bot_vs_bot", patched_run)
    import backend.app.api.matches as matches_api

    monkeypatch.setattr(matches_api, "execute_pending_match", mr.execute_pending_match)

    white_id = _upload(client, auth_headers, "w-bot", seed=1)
    black_id = _upload(client, auth_headers, "b-bot", seed=2)
    r = client.post(
        "/api/matches/schedule",
        headers=auth_headers,
        json={"white_bot_id": white_id, "black_bot_id": black_id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "finished"
    assert body["result"] in {"1-0", "0-1", "1/2-1/2"}
    assert body["pgn"] is not None and "[Event" in body["pgn"]

    leaderboard = client.get("/api/leaderboard/bots").json()
    names = {b["name"] for b in leaderboard}
    assert {"w-bot", "b-bot"}.issubset(names)
