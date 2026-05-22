"""WebSocket live-play tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.auth import encode_token


def test_h2h_two_clients_play_a_move(client: TestClient) -> None:
    w_token = encode_token({"github_id": 100, "login": "white_user"})
    b_token = encode_token({"github_id": 200, "login": "black_user"})
    with client.websocket_connect(
        f"/api/ws/play/room-1?token={w_token}&color=white"
    ) as ws_white, client.websocket_connect(
        f"/api/ws/play/room-1?token={b_token}&color=black"
    ) as ws_black:
        # Both should see a join + state.
        m = ws_white.receive_json()
        assert m["type"] == "join"
        m = ws_white.receive_json()
        assert m["type"] == "state"
        assert m["fen"].startswith("rnbqkbnr/")
        m = ws_black.receive_json()
        assert m["type"] == "join"
        m = ws_black.receive_json()
        # When black joined, room broadcast a new state to everyone.
        # Drain any extra state messages until we see the latest.
        # White also gets a state broadcast at this point.
        m_white_state = ws_white.receive_json()
        assert m_white_state["type"] == "state"

        # White plays e4.
        ws_white.send_json({"type": "move", "uci": "e2e4"})
        m = ws_white.receive_json()
        assert m["type"] == "state"
        assert m["moves"] == ["e2e4"]
        m_black = ws_black.receive_json()
        assert m_black["type"] == "state"
        assert m_black["moves"] == ["e2e4"]


def test_spectator_cannot_move(client: TestClient) -> None:
    s_token = encode_token({"github_id": 5, "login": "spec"})
    with client.websocket_connect(f"/api/ws/play/specroom?token={s_token}") as ws:
        m = ws.receive_json()
        assert m["type"] == "join"
        assert m["color"] == "spectator"
        # Drain state.
        ws.receive_json()
        ws.send_json({"type": "move", "uci": "e2e4"})
        m = ws.receive_json()
        assert m["type"] == "error"
        assert "spectators" in m["detail"]


def test_illegal_move_rejected(client: TestClient) -> None:
    token = encode_token({"github_id": 7, "login": "lone"})
    with client.websocket_connect(
        f"/api/ws/play/onlywhite?token={token}&color=white"
    ) as ws:
        ws.receive_json()  # join
        ws.receive_json()  # state
        ws.send_json({"type": "move", "uci": "e2e5"})
        m = ws.receive_json()
        assert m["type"] == "error"
        assert "illegal" in m["detail"]


def test_resign_ends_game(client: TestClient) -> None:
    token = encode_token({"github_id": 9, "login": "quitter"})
    with client.websocket_connect(
        f"/api/ws/play/quitroom?token={token}&color=white"
    ) as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "resign"})
        m = ws.receive_json()
        assert m["type"] == "end"
        assert m["result"] == "0-1"  # white resigned
