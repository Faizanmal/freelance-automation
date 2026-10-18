import { beforeEach, expect, test, vi } from "vitest";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => "token"),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  });
});

test("submitApplication always posts explicit confirm flag", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      application_id: 1,
      job_id: 9,
      source_name: "freelancer",
      submit_mode: "api_bid",
      status: "submitted",
    }),
  });

  const { submitApplication } = await import("@/lib/api");
  await submitApplication(
    9,
    {
      proposal: "Hello",
      bid_amount: 100,
      currency: "USD",
      delivery_days: 7,
      milestone_plan: null,
    },
    true,
  );

  expect(fetchMock).toHaveBeenCalled();
  const [, init] = fetchMock.mock.calls[0];
  const body = JSON.parse(init.body);
  expect(body.confirm).toBe(true);
});
