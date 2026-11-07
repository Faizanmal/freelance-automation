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

test("Skipped-lead counter matches between Skipped tab and summary Skip badge on skip and restore", async () => {
  let currentStatus: "save" | "skip" | "pitched" | "won" | null = null;

  vi.mocked(api.getAuthFindings).mockImplementation(async () => {
    const isSkipped = currentStatus === "skip";
    return {
      generated_at: "2026-10-05T00:00:00Z",
      total_scanned: 1,
      total_matched: 1,
      total_findings: isSkipped ? 0 : 1,
      skipped_count: isSkipped ? 1 : 0,
      freelance_focus: true,
      action_counts: {
        draft_bid: isSkipped ? 0 : 1,
        watch: 0,
        skip: isSkipped ? 1 : 0,
      },
      keywords: ["python"],
      items: [
        {
          job_id: 42,
          title: "API Engineer",
          company: "Client",
          source_name: "freelancer",
          url: "https://www.freelancer.com/projects/42",
          score: 0.95,
          why: "Strong fit",
          signals: ["API"],
          risks: [],
          action: "draft_bid",
          matched_keywords: ["python"],
          freshness_score: 0.8,
          client_quality_score: 0.7,
          red_flags: [],
          user_status: currentStatus,
        },
      ],
    };
  });
  vi.mocked(api.setLeadAction).mockImplementation(async (jobId, status) => {
    currentStatus = status === "clear" ? null : status;
    return { job_id: jobId, status: currentStatus };
  });

  render(<LeadsPage />);

  await waitFor(() => {
    expect(screen.getByText("API Engineer")).toBeInTheDocument();
  });

  expect(screen.getByText("95%")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Skipped (0)" })).toBeInTheDocument();
  expect(screen.getByText("Skip: 0")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Skip" }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Skipped (1)" })).toBeInTheDocument();
    expect(screen.getByText("Skip: 1")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "Skipped (1)" }));
  await waitFor(() => {
    expect(screen.getByText("API Engineer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restore" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "Restore" }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Skipped (0)" })).toBeInTheDocument();
    expect(screen.getByText("Skip: 0")).toBeInTheDocument();
  });
});

test("Restoring a skipped lead when 25 active leads are loaded keeps All at 25 (never 26)", async () => {
  const activeItems = Array.from({ length: 25 }, (_, i) => ({
    job_id: i + 1,
    title: `Active Contract Role ${i + 1}`,
    company: "Direct Client",
    source_name: "remoteok",
    url: `https://example.com/jobs/${i + 1}`,
    score: 0.9 - i * 0.01,
    why: "Strong fit",
    signals: ["Contract"],
    risks: [],
    action: "draft_bid" as const,
    matched_keywords: ["python"],
    freshness_score: 0.8,
    client_quality_score: 0.7,
    red_flags: [],
    user_status: null,
  }));

  const skippedItem = {
    job_id: 99,
    title: "Restored Contract Role",
    company: "Acme Corp",
    source_name: "remoteok",
    url: "https://example.com/jobs/99",
    score: 0.85,
    why: "Strong fit",
    signals: ["Contract"],
    risks: [],
    action: "draft_bid" as const,
    matched_keywords: ["python"],
    freshness_score: 0.8,
    client_quality_score: 0.7,
    red_flags: [],
    user_status: "skip" as const,
  };

  let restored = false;
  vi.mocked(api.getAuthFindings).mockImplementation(async () => ({
    generated_at: "2026-10-05T00:00:00Z",
    total_scanned: 300,
    total_indexed: 380,
    total_matched: 40,
    total_findings: 25,
    skipped_count: restored ? 0 : 1,
    freelance_focus: true,
    action_counts: {
      draft_bid: 25,
      watch: 0,
      skip: restored ? 0 : 1,
    },
    keywords: ["python"],
    items: restored
      ? [{ ...skippedItem, user_status: null }, ...activeItems.slice(0, 24)]
      : [...activeItems, skippedItem],
  }));

  vi.mocked(api.setLeadAction).mockImplementation(async (jobId) => {
    restored = true;
    return { job_id: jobId, status: null };
  });

  render(<LeadsPage />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "All (25)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skipped (1)" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "Skipped (1)" }));
  await waitFor(() => {
    expect(screen.getByText("Restored Contract Role")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "Restore" }));

  // Must remain All (25) immediately and after reload — never All (26)
  expect(screen.queryByRole("button", { name: "All (26)" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "All (25)" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Skipped (0)" })).toBeInTheDocument();
});

