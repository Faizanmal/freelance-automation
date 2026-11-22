import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import PricingPage from "@/app/pricing/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => null),
  listBillingPlans: vi.fn(),
  startCheckout: vi.fn(),
  activateDevPro: vi.fn(),
  getBillingUsage: vi.fn().mockResolvedValue(null),
  getBilling: vi.fn().mockResolvedValue({ plan: "free" }),
  getUnitEconomics: vi.fn().mockResolvedValue({}),
  getProviderEligibility: vi.fn().mockResolvedValue({}),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test("hides Activate Pro (dev) when billing unavailable in production-like mode", async () => {
  vi.mocked(api.listBillingPlans).mockResolvedValue({
    stripe_enabled: false,
    dev_activate_allowed: false,
    plans: [
      {
        id: "free",
        price_label: "$0",
        marketplace: false,
        scrape_limit: 15,
        max_digest: 5,
        daily_scrape_runs: 3,
        channels: ["email"],
        features: ["Email digest up to 5 leads"],
      },
      {
        id: "pro",
        price_label: "$19/mo",
        marketplace: true,
        scrape_limit: 100,
        max_digest: 25,
        daily_scrape_runs: 50,
        channels: ["email", "slack"],
        features: ["Higher hunt density"],
      },
    ],
  });

  render(<PricingPage />);

  await waitFor(() => {
    expect(screen.getByText(/pro checkout opens soon/i)).toBeInTheDocument();
  });
  expect(screen.queryByRole("button", { name: /activate pro \(dev\)/i })).not.toBeInTheDocument();
  expect(
    screen.getAllByRole("link", { name: /(get )?start(ed)? free/i }).length,
  ).toBeGreaterThanOrEqual(1);
});

test("shows Activate Pro (dev) when dev activate is allowed", async () => {
  vi.mocked(api.listBillingPlans).mockResolvedValue({
    stripe_enabled: false,
    dev_activate_allowed: true,
    plans: [
      {
        id: "free",
        price_label: "$0",
        marketplace: false,
        scrape_limit: 15,
        max_digest: 5,
        daily_scrape_runs: 3,
        channels: ["email"],
        features: ["Email digest up to 5 leads"],
      },
      {
        id: "pro",
        price_label: "$19/mo",
        marketplace: true,
        scrape_limit: 100,
        max_digest: 25,
        daily_scrape_runs: 50,
        channels: ["email", "slack"],
        features: ["Higher hunt density"],
      },
    ],
  });

  render(<PricingPage />);

  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: /activate pro \((local sandbox|dev)\)/i }),
    ).toBeInTheDocument();
  });
});
