import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import HomePage from "@/app/page";

describe("HomePage", () => {
  beforeEach(() => {
    // Mock fetch so SSR-during-test renders the empty state instead of failing.
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "ok",
      json: async () => [],
    }) as unknown as typeof fetch;
  });

  it("renders heading + empty bot leaderboard", async () => {
    const node = await HomePage();
    render(node);
    expect(screen.getByText("chesslab")).toBeTruthy();
    expect(screen.getByTestId("bot-leaderboard")).toBeTruthy();
    expect(screen.getByText(/No bots yet/)).toBeTruthy();
  });
});
