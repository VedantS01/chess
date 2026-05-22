"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { wsUrl } from "@/lib/api";

type Role = "white" | "black" | "spectator";
type GameState = {
  fen: string;
  moves: string[];
  turn: "white" | "black";
  status: "ongoing" | "ended";
  result: string | null;
};

export default function PlayPage() {
  const [roomId, setRoomId] = useState("room-1");
  const [role, setRole] = useState<Role>("white");
  const [token, setToken] = useState("");
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const chess = useMemo(() => new Chess(), []);

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  function connect() {
    setError(null);
    if (!token) {
      setError(
        "Provide a JWT (sign in via GitHub or use a dev token for testing).",
      );
      return;
    }
    const url = wsUrl(roomId, token, role);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setError("websocket error");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") {
        setState(msg);
        chess.load(msg.fen);
      } else if (msg.type === "error") {
        setError(msg.detail);
      } else if (msg.type === "end") {
        setError(`Game over: ${msg.result}`);
      }
    };
  }

  function onPieceDrop(source: string, target: string): boolean {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return false;
    if (role === "spectator") return false;
    const uci = `${source}${target}${promotionPiece(source, target)}`;
    wsRef.current.send(JSON.stringify({ type: "move", uci }));
    return true;
  }

  function promotionPiece(source: string, target: string): string {
    const piece = chess.get(source as never);
    if (!piece || piece.type !== "p") return "";
    if (piece.color === "w" && target.endsWith("8")) return "q";
    if (piece.color === "b" && target.endsWith("1")) return "q";
    return "";
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Live play</h1>
      <div className="flex gap-3 items-end flex-wrap">
        <label className="flex flex-col text-sm">
          <span className="text-neutral-400">room id</span>
          <input
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1"
            value={roomId}
            onChange={(e) => setRoomId(e.target.value)}
          />
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-neutral-400">role</span>
          <select
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
          >
            <option value="white">white</option>
            <option value="black">black</option>
            <option value="spectator">spectator</option>
          </select>
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-neutral-400">jwt</span>
          <input
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 w-72"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="paste your JWT here"
          />
        </label>
        <button
          onClick={connect}
          disabled={connected}
          className="bg-blue-600 disabled:bg-neutral-700 px-3 py-1 rounded"
        >
          {connected ? "connected" : "connect"}
        </button>
      </div>

      {error && (
        <p data-testid="status" className="text-amber-400 text-sm">
          {error}
        </p>
      )}

      <div className="max-w-md">
        <Chessboard
          position={state?.fen ?? "start"}
          onPieceDrop={onPieceDrop}
          boardOrientation={role === "black" ? "black" : "white"}
          arePiecesDraggable={role !== "spectator" && connected}
        />
      </div>

      {state && (
        <p data-testid="game-state" className="text-sm text-neutral-400">
          turn: {state.turn} · status: {state.status} · moves: {state.moves.length}
        </p>
      )}
    </div>
  );
}
