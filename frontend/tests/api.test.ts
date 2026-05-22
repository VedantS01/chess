import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { api } from "@/lib/api";

describe("api client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    process.env.NEXT_PUBLIC_API_BASE = "http://test";
  });
  afterEach(() => {
    fetchMock.mockReset();
  });

  it("health returns json", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "ok",
      json: async () => ({ status: "ok" }),
    });
    const r = await api.health();
    expect(r).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://test/api/health",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
  });

  it("bot leaderboard parses array", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "ok",
      json: async () => [
        { id: 1, owner_id: 1, name: "alpha", version: 1, elo: 1500 },
      ],
    });
    const r = await api.botLeaderboard();
    expect(r).toHaveLength(1);
    expect(r[0].name).toBe("alpha");
  });

  it("throws on non-2xx", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: "unauthorized",
      text: async () => "no",
    });
    await expect(api.myBots("token")).rejects.toThrow(/401/);
  });

  it("schedule match sends json body and bearer", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 201,
      statusText: "created",
      json: async () => ({
        id: 1,
        white_bot_id: 1,
        black_bot_id: 2,
        status: "finished",
        result: "1-0",
        pgn: "[Event ...]",
        termination: null,
      }),
    });
    const r = await api.scheduleMatch("abc", 1, 2, true);
    expect(r.status).toBe("finished");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/matches/schedule");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer abc");
    expect((init.headers as Headers).get("Content-Type")).toBe("application/json");
  });
});
