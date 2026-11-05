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

test("getGoogleAuthUrl requests authorization url with optional redirect_uri", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => ({
      url: "https://accounts.google.com/o/oauth2/v2/auth?client_id=123",
      state: "state-token",
    }),
  });

  const { getGoogleAuthUrl } = await import("@/lib/api");
  const res = await getGoogleAuthUrl("http://localhost:3000/auth/callback/google");
  expect(res.url).toContain("https://accounts.google.com");
  expect(res.state).toBe("state-token");

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/auth/google/url?redirect_uri="),
    expect.any(Object),
  );
});

test("loginWithGoogle saves token and returns access token on success", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      access_token: "mock-jwt-token",
      token_type: "bearer",
    }),
  });

  const { loginWithGoogle } = await import("@/lib/api");
  const data = await loginWithGoogle({ code: "google-auth-code", state: "state-token" });

  expect(data.access_token).toBe("mock-jwt-token");
  expect(localStorageSetItem).toHaveBeenCalledWith("signal_desk_token", "mock-jwt-token");
});

test("loginWithGoogle passes through TOTP_REQUIRED", async () => {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    text: async () => JSON.stringify({ detail: "TOTP_REQUIRED" }),
  });

  const { loginWithGoogle } = await import("@/lib/api");
  await expect(loginWithGoogle({ id_token: "google-id-token" })).rejects.toThrow("TOTP_REQUIRED");
});

test("loginWithGoogle maps network errors to friendly message", async () => {
  fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

  const { loginWithGoogle } = await import("@/lib/api");
  await expect(loginWithGoogle({ code: "abc" })).rejects.toThrow(
    "Can't reach the API. Check that the backend is running.",
  );
});

test("loginWithGoogle maps backend error message", async () => {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 400,
    text: async () => JSON.stringify({ detail: "Google email address is not verified." }),
  });

  const { loginWithGoogle } = await import("@/lib/api");
  await expect(loginWithGoogle({ code: "abc" })).rejects.toThrow(
    "Google email address is not verified.",
  );
});

