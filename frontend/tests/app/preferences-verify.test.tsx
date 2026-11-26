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

const routerMock = { push: vi.fn(), replace: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams("verify=auto"),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn(), dismissAll: vi.fn() }),
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

vi.mock("@/components/account-settings", () => ({
  AccountSettings: () => <div>Account settings</div>,
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => "fake-token"),
  logout: vi.fn().mockResolvedValue({ message: "logged out" }),
  me: vi.fn(),
  getPreferences: vi.fn(),
  getAuthMatches: vi.fn(),
  getBilling: vi.fn(),
  updatePreferences: vi.fn(),
  activateDevPro: vi.fn(),
  startCheckout: vi.fn(),
  openBillingPortal: vi.fn(),
  resendVerification: vi.fn(),
  sendNotification: vi.fn(),
  sendTestEmailAlert: vi.fn().mockResolvedValue({
    status: "delivered",
    delivered: true,
    message: "Test email sent",
  }),
  sendTestInboxAlert: vi.fn().mockResolvedValue({
    id: 1,
    public_id: "test",
    status: "delivered",
    is_read: false,
    created_at: null,
    message: "Test alert sent",
  }),
  devVerifyEmail: vi.fn(),
  getLearnedAffinities: vi.fn().mockResolvedValue(null),
  getMatchProfile: vi.fn().mockResolvedValue(null),
  listConsents: vi.fn().mockResolvedValue({ items: [] }),
  upsertConsent: vi.fn().mockResolvedValue({}),
  testWebhook: vi.fn().mockResolvedValue({ success: true }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  routerMock.push.mockReset();
  routerMock.replace.mockReset();
  vi.mocked(api.getToken).mockReturnValue("fake-token");
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
    limits: {
      scrape_limit: 15,
      max_digest: 5,
      daily_scrape_runs: 3,
      marketplace: false,
      channels: ["email"],
      sources: [],
    },
    features: [],
  });
});

test("shows auto-verify banner from query param", async () => {
  render(<PreferencesPage />);

  await waitFor(() => {
    expect(screen.getAllByText(/local auto-verify applied/i).length).toBeGreaterThan(0);
  });
});

test("displays consistent match score (95%) once findings settle", async () => {
  vi.mocked(api.getAuthMatches).mockResolvedValue({
    total: 1,
    items: [
      {
        id: 42,
        title: "API Engineer",
        url: "https://www.freelancer.com/projects/42",
        source_name: "freelancer",
        source_id: "42",
        description: "Build FastAPI services",
        company: "Client",
        match_score: 0.95,
        matched_keywords: ["python"],
      },
    ],
  });

  render(<PreferencesPage />);

  await waitFor(() => {
    expect(screen.getByText("API Engineer")).toBeInTheDocument();
    expect(screen.getAllByText("95%")[0]).toBeInTheDocument();
  });
});

test("signed-out visit never paints Hunt Rules form or Sign out", async () => {
  vi.mocked(api.getToken).mockReturnValue(null);

  render(<PreferencesPage />);

  expect(screen.queryByRole("heading", { name: /Hunt Rules/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Sign out/i })).not.toBeInTheDocument();
  await waitFor(() => {
    expect(routerMock.replace).toHaveBeenCalledWith("/auth");
  });
  expect(screen.getByText(/Redirecting to sign in/i)).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: /Hunt Rules/i })).not.toBeInTheDocument();
});

