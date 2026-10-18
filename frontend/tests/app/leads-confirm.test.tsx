import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import LeadsPage from "@/app/leads/page";
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
  useSearchParams: () => new URLSearchParams(),
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
  Button: ({
    children,
    onClick,
    type = "button",
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    type?: "button" | "submit";
    disabled?: boolean;
  }) => (
    <button type={type} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => "fake-token"),
  getDemoFindings: vi.fn(),
  getAuthFindings: vi.fn(),
  setLeadAction: vi.fn(),
  draftProposal: vi.fn(),
  submitApplication: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("open", vi.fn());
  vi.mocked(api.getToken).mockReturnValue("fake-token");
  vi.mocked(api.getAuthFindings).mockResolvedValue({
    generated_at: "2026-10-05T00:00:00Z",
    total_scanned: 1,
    total_matched: 1,
    total_findings: 1,
    freelance_focus: true,
    action_counts: { draft_bid: 1, watch: 0, skip: 0 },
    keywords: ["python"],
    items: [
      {
        job_id: 42,
        title: "API Engineer",
        company: "Client",
        source_name: "freelancer",
        url: "https://www.freelancer.com/projects/42",
        score: 0.9,
        why: "Strong fit",
        signals: ["API"],
        risks: [],
        action: "draft_bid",
        matched_keywords: ["python"],
        freshness_score: 0.8,
        client_quality_score: 0.7,
        red_flags: [],
      },
    ],
  });
});

test("confirm submit sends confirm=true to apply API", async () => {
  vi.mocked(api.draftProposal).mockResolvedValue({
    job_id: 42,
    title: "API Engineer",
    source_name: "freelancer",
    source_url: "https://www.freelancer.com/projects/42",
    provider: "template",
    draft: "Hello",
    disclaimer: "Review first",
    form_fields: {
      proposal: "Hello I can help",
      bid_amount: 250,
      currency: "USD",
      delivery_days: 7,
      milestone_plan: "Plan",
      milestone_percentage: 100,
      submit_mode: "api_bid",
      project_url: "https://www.freelancer.com/projects/42",
    },
  });
  vi.mocked(api.submitApplication).mockResolvedValue({
    application_id: 1,
    job_id: 42,
    source_name: "freelancer",
    submit_mode: "api_bid",
    status: "submitted",
    detail: "Bid placed",
  });

  render(<LeadsPage />);

  await waitFor(() => {
    expect(screen.getByText("API Engineer")).toBeInTheDocument();
  });

  expect(screen.getByRole("button", { name: /open original/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /draft bid/i }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /confirm & submit/i })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: /confirm & submit/i }));

  await waitFor(() => {
    expect(api.submitApplication).toHaveBeenCalledWith(
      42,
      expect.objectContaining({ proposal: "Hello I can help", submit_mode: "api_bid" }),
      true,
    );
  });
});
