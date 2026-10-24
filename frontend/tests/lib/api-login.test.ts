import { beforeEach, expect, test, vi } from "vitest";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  });
});

test("login maps invalid credentials to a clear message", async () => {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    text: async () => JSON.stringify({ detail: "Invalid credentials" }),
  });

  const { login } = await import("@/lib/api");
  await expect(login("missing@example.com", "password123")).rejects.toThrow(
    "Invalid email or password.",
  );
});

test("login maps network failure to a reachable-API message", async () => {
  fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

  const { login } = await import("@/lib/api");
  await expect(login("a@b.com", "password123")).rejects.toThrow(
    "Can't reach the API. Check that the backend is running.",
  );
});

test("request maps network failure to a friendly message", async () => {
  fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

  const { request } = await import("@/lib/api");
  await expect(request("/auth/register", { method: "POST", body: "{}" })).rejects.toThrow(
    "Can't reach the API. Check your connection and try again.",
  );
});

test("request surfaces backend detail strings", async () => {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 409,
    text: async () => JSON.stringify({ detail: "Email already registered" }),
  });

  const { request } = await import("@/lib/api");
  await expect(request("/auth/register", { method: "POST", body: "{}" })).rejects.toThrow(
    "Email already registered",
  );
});
