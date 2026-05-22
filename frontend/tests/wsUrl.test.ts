import { describe, it, expect } from "vitest";
import { wsUrl } from "@/lib/api";

describe("wsUrl", () => {
  it("converts http base to ws and embeds params", () => {
    process.env.NEXT_PUBLIC_API_BASE = "http://example.com:8000";
    const u = wsUrl("room-1", "tok", "white");
    expect(u).toBe(
      "ws://example.com:8000/api/ws/play/room-1?token=tok&color=white",
    );
  });

  it("converts https to wss", () => {
    process.env.NEXT_PUBLIC_API_BASE = "https://api.example.com";
    const u = wsUrl("r", "t", "spectator");
    expect(u.startsWith("wss://api.example.com")).toBe(true);
  });
});
