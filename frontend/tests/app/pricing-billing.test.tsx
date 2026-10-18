import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import PricingPage from "@/app/pricing/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => "fake-token"),
  listBillingPlans: vi.fn(),
  startCheckout: vi.fn(),
  activateDevPro: vi.fn(),
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
        scrape_limit: 25,
        channels: ["email"],
        features: ["Email alerts"],
      },
      {
        id: "pro",
        price_label: "$19/mo",
        marketplace: true,
        scrape_limit: 100,
        channels: ["email", "slack"],
        features: ["Marketplaces"],
      },
    ],
  });

  render(<PricingPage />);

  await waitFor(() => {
    expect(screen.getByText(/billing is not configured/i)).toBeInTheDocument();
  });
  expect(screen.queryByRole("button", { name: /activate pro \(dev\)/i })).not.toBeInTheDocument();
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
        scrape_limit: 25,
        channels: ["email"],
        features: ["Email alerts"],
      },
      {
        id: "pro",
        price_label: "$19/mo",
        marketplace: true,
        scrape_limit: 100,
        channels: ["email", "slack"],
        features: ["Marketplaces"],
      },
    ],
  });

  render(<PricingPage />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /activate pro \(dev\)/i })).toBeInTheDocument();
  });
});
