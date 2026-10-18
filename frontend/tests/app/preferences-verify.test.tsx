import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import PreferencesPage from "@/app/preferences/page";
import * as api from "@/lib/api";

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useTransition: () =>
      [false, (cb: () => void) => { void cb(); }] as const,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("verify=auto"),
}));

vi.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get: () =>
        ({ children }: { children?: React.ReactNode }) =>
          <div>{children}</div>,
    },
  ),
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: { children: React.ReactNode }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/security-settings", () => ({
  SecuritySettings: () => <div>Security settings</div>,
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => "fake-token"),
  me: vi.fn(),
  getPreferences: vi.fn(),
  getAuthMatches: vi.fn(),
  getBilling: vi.fn(),
  updatePreferences: vi.fn(),
  activateDevPro: vi.fn(),
  startCheckout: vi.fn(),
  openBillingPortal: vi.fn(),
  logout: vi.fn(),
  resendVerification: vi.fn(),
  devVerifyEmail: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.me).mockResolvedValue({
    id: "u1",
    email: "dev@example.com",
    is_verified: true,
    plan: "free",
  });
  vi.mocked(api.getPreferences).mockResolvedValue({
    keywords: ["python"],
    exclude_keywords: [],
    min_budget: null,
    max_budget: null,
    sources: [],
    match_threshold: 0.35,
    notification_channels: ["email"],
    digest_mode: true,
    freelance_focus: true,
    notes: null,
  });
  vi.mocked(api.getAuthMatches).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(api.getBilling).mockResolvedValue({
    plan: "free",
    subscription_status: "inactive",
    is_pro: false,
    stripe_enabled: false,
    dev_activate_allowed: true,
    limits: { scrape_limit: 25, marketplace: false, channels: ["email"], sources: [] },
    features: [],
  });
});

test("shows auto-verify banner from query param", async () => {
  render(<PreferencesPage />);

  await waitFor(() => {
    expect(screen.getAllByText(/local auto-verify applied/i).length).toBeGreaterThan(0);
  });
});
