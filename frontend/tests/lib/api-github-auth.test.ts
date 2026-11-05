import { beforeEach, expect, test, vi } from "vitest";

const fetchMock = vi.fn();
const localStorageSetItem = vi.fn();

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => null),
    setItem: localStorageSetItem,
    removeItem: vi.fn(),
  });
});

test("getGitHubAuthUrl requests authorization url with optional redirect_uri", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => ({
      url: "https://github.com/login/oauth/authorize?client_id=123",
      state: "state-gh-123",
    }),
  });

  const { getGitHubAuthUrl } = await import("@/lib/api");
  const res = await getGitHubAuthUrl("http://localhost:3000/auth/callback/github");
  expect(res.url).toContain("https://github.com/login/oauth/authorize");
  expect(res.state).toBe("state-gh-123");

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/auth/github/url?redirect_uri="),
    expect.any(Object),
  );
});

test("loginWithGitHub saves token and returns access token on success", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      access_token: "mock-jwt-token-gh",
      token_type: "bearer",
    }),
  });

  const { loginWithGitHub } = await import("@/lib/api");
  const data = await loginWithGitHub({ code: "gh-auth-code", state: "state-token" });

  expect(data.access_token).toBe("mock-jwt-token-gh");
  expect(localStorageSetItem).toHaveBeenCalledWith("signal_desk_token", "mock-jwt-token-gh");
});

test("loginWithGitHub passes through TOTP_REQUIRED", async () => {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    text: async () => JSON.stringify({ detail: "TOTP_REQUIRED" }),
  });

  const { loginWithGitHub } = await import("@/lib/api");
  await expect(loginWithGitHub({ code: "gh-code" })).rejects.toThrow("TOTP_REQUIRED");
});
