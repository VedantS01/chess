// Typed client for the chesslab backend.
// The API base URL is configurable via NEXT_PUBLIC_API_BASE; defaults to localhost in dev.

const DEFAULT_BASE = "http://localhost:8000";

export function apiBase(): string {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE;
  }
  return DEFAULT_BASE;
}

export interface BotLeaderboardEntry {
  id: number;
  owner_id: number;
  name: string;
  version: number;
  elo: number;
}

export interface UserLeaderboardEntry {
  id: number;
  login: string;
  elo: number;
}

export interface BotOut {
  id: number;
  owner_id: number;
  name: string;
  version: number;
  description: string | null;
  status: "pending" | "ready" | "failed" | "disabled";
  elo: number;
}

export interface MatchOut {
  id: number;
  white_bot_id: number | null;
  black_bot_id: number | null;
  status: "pending" | "running" | "finished" | "failed";
  result: "1-0" | "0-1" | "1/2-1/2" | "*";
  pgn: string | null;
  termination: string | null;
}

async function call<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${apiBase()}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => call<{ status: string }>("/api/health"),
  botLeaderboard: () => call<BotLeaderboardEntry[]>("/api/leaderboard/bots"),
  userLeaderboard: () => call<UserLeaderboardEntry[]>("/api/leaderboard/users"),
  myBots: (token: string) => call<BotOut[]>("/api/bots/mine", {}, token),
  uploadBot: async (token: string, name: string, file: File, description?: string) => {
    const form = new FormData();
    form.append("name", name);
    if (description) form.append("description", description);
    form.append("artifact", file);
    return call<BotOut>(
      "/api/bots",
      { method: "POST", body: form },
      token,
    );
  },
  scheduleMatch: (token: string, whiteBotId: number, blackBotId: number, runNow = true) =>
    call<MatchOut>(
      `/api/matches/schedule?run_now=${runNow}`,
      {
        method: "POST",
        body: JSON.stringify({ white_bot_id: whiteBotId, black_bot_id: blackBotId }),
      },
      token,
    ),
  getMatch: (id: number) => call<MatchOut>(`/api/matches/${id}`),
  recentMatches: (limit = 20) =>
    call<MatchOut[]>(`/api/matches?limit=${limit}`),
};

export function wsUrl(roomId: string, token: string, color: string): string {
  const base = apiBase().replace(/^http/, "ws");
  const params = new URLSearchParams({ token, color });
  return `${base}/api/ws/play/${roomId}?${params.toString()}`;
}
