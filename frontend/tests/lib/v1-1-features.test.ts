import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  buildGmailComposeUrl,
  buildSafeMailtoUrl,
  sanitizeEmailAddress,
} from "@/lib/security";
import {
  getPipelineStats,
  getSeoDirectory,
  getSeoSkillDirectory,
  setToken,
} from "@/lib/api";

describe("v1.1 Security & Deep-Link Helpers", () => {
  it("validates and sanitizes email addresses against injection", () => {
    expect(sanitizeEmailAddress("  founder@startup.io ")).toBe("founder@startup.io");
    expect(sanitizeEmailAddress("bad@email\r\nBcc:attacker@evil.com")).toBe("");
    expect(sanitizeEmailAddress("javascript:alert(1)")).toBe("");
    expect(sanitizeEmailAddress(null)).toBe("");
  });

  it("builds a valid HTTPS Gmail compose deep-link", () => {
    const url = buildGmailComposeUrl({
      to: "hiring@acme.dev",
      subject: "Contract inquiry: Python Architect",
      body: "Hi team,\nI can help with your FastAPI backend.",
    });
    const parsed = new URL(url);
    expect(parsed.origin).toBe("https://mail.google.com");
    expect(parsed.searchParams.get("view")).toBe("cm");
    expect(parsed.searchParams.get("to")).toBe("hiring@acme.dev");
    expect(parsed.searchParams.get("su")).toBe("Contract inquiry: Python Architect");
    expect(parsed.searchParams.get("body")).toContain("FastAPI backend");
  });

  it("builds a safe mailto URI", () => {
    const mailto = buildSafeMailtoUrl({
      to: "cto@client.org",
      subject: "FastAPI Role",
      body: "Hello world",
    });
    expect(mailto).toBe("mailto:cto@client.org?subject=FastAPI%20Role&body=Hello%20world");
  });
});

describe("v1.1 API Client Functions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    const store = new Map<string, string>([["signal_desk_token", "test-jwt-token"]]);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      setItem: vi.fn((key: string, val: string) => store.set(key, val)),
      removeItem: vi.fn((key: string) => store.delete(key)),
    });
    setToken("test-jwt-token");
  });

  it("fetches pipeline stats with auth header", async () => {
    const mockStats = {
      saved_count: 3,
      pitched_count: 2,
      won_count: 1,
      skipped_count: 0,
      total_engaged: 6,
      pitch_rate: 0.5,
      win_rate: 0.333,
      saved_value: 3000,
      pitched_value: 4000,
      won_value: 2500,
      active_pipeline_value: 7000,
    };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockStats), { status: 200 }),
    );

    const res = await getPipelineStats();
    expect(res.active_pipeline_value).toBe(7000);
    expect(res.win_rate).toBe(0.333);
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/preferences/pipeline-stats"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-jwt-token",
        }),
      }),
    );
  });

  it("fetches public SEO directory and skill pages", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ total_active: 12, categories: [], recent: [] }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            slug: "python",
            label: "Python",
            headline: "Remote Python Freelance & Contract Jobs",
            description: "Desc",
            total_matched: 4,
            items: [],
            related_skills: [],
          }),
          { status: 200 },
        ),
      );

    const dir = await getSeoDirectory();
    expect(dir.total_active).toBe(12);

    const skillDir = await getSeoSkillDirectory("python", 12);
    expect(skillDir.slug).toBe("python");
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});

