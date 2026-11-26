import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import AuthPage from "@/app/auth/page";
import * as api from "@/lib/api";

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useTransition: () =>
      [false, (cb: () => void) => { void cb(); }] as const,
  };
});

const searchParams = new URLSearchParams("mode=register");
const routerMock = { push: vi.fn(), replace: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => searchParams,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: { children: React.ReactNode }) => (
    <button type="submit" {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/account-settings", () => ({
  AccountSettings: () => <div>Account settings</div>,
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => null),
  getGitHubAuthUrl: vi.fn(),
  getGoogleAuthUrl: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  setToken: vi.fn(),
  me: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  searchParams.set("mode", "register");
  vi.mocked(api.getToken).mockReturnValue(null);
});

test("mode=register opens Create account with labeled fields", async () => {
  render(<AuthPage />);

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: /Create account/i })).toBeInTheDocument();
  });
  expect(screen.getByLabelText(/^Full name$/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/^Email$/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/^Password$/i)).toBeInTheDocument();
});
