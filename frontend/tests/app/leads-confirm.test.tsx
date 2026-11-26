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

const dismissAll = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn(), dismissAll }),
}));

vi.mock("@/lib/api", () => ({
  getToken: vi.fn(() => "fake-token"),
  getApiBase: vi.fn(() => "https://api.example.test"),
  getDemoFindings: vi.fn(),
  getAuthFindings: vi.fn(),
  getPipelineStats: vi.fn(),
  setLeadAction: vi.fn(),
  postMatchFeedback: vi.fn(),
  draftProposal: vi.fn(),
  submitApplication: vi.fn(),
  recordProductEvent: vi.fn(),
  reportJobExpired: vi.fn(),
  reportListingTrust: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  dismissAll.mockClear();
  vi.stubGlobal("open", vi.fn());
  vi.mocked(api.getToken).mockReturnValue("fake-token");
  vi.mocked(api.getPipelineStats).mockResolvedValue({
    saved_count: 0,
    pitched_count: 0,
    won_count: 0,
    skipped_count: 0,
    total_engaged: 0,
    pitch_rate: 0,
    win_rate: 0,
    saved_value: 0,
    pitched_value: 0,
    won_value: 0,
    active_pipeline_value: 0,
  });
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
  vi.mocked(api.postMatchFeedback).mockImplementation(async (payload) => {
    currentStatus = payload.kind === "clear"
      ? null
      : payload.kind === "save" || payload.kind === "skip"
        ? payload.kind
        : null;
    return { job_id: payload.job_id, status: currentStatus, feedback_kind: payload.kind };
  });
  vi.mocked(api.getPipelineStats).mockImplementation(async () => ({
    saved_count: currentStatus === "save" ? 1 : 0,
    pitched_count: currentStatus === "pitched" ? 1 : 0,
    won_count: currentStatus === "won" ? 1 : 0,
    skipped_count: currentStatus === "skip" ? 1 : 0,
    total_engaged: currentStatus && currentStatus !== "skip" ? 1 : 0,
    pitch_rate: 0,
    win_rate: 0,
    saved_value: 0,
    pitched_value: 0,
    won_value: 0,
    active_pipeline_value: 0,
  }));

  render(<LeadsPage />);

  await waitFor(() => {
    expect(screen.getByText("API Engineer")).toBeInTheDocument();
  });

  expect(screen.getAllByText("95%")[0]).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Skipped \(0\)$/ })).toBeInTheDocument();
  expect(screen.getByText("Skip: 0")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /^Skip$/ }));

  await waitFor(() => {
    expect(api.postMatchFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ job_id: 42, kind: "skip" }),
    );
  });

  // Click the Skipped tab once the durable write has landed (count stays at 1).
  await waitFor(() => {
    expect(screen.getByText("Skip: 1")).toBeInTheDocument();
    const tab = screen.getByRole("button", { name: /Skipped\s*\(\s*1\s*\)/ });
    fireEvent.click(tab);
    expect(screen.getByRole("button", { name: /^Restore$/ })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: /^Restore$/ }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /Skipped\s*\(\s*0\s*\)/ })).toBeInTheDocument();
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

  // Await-before-UI: counts update only after the durable clear write resolves.
  await waitFor(() => {
    expect(screen.queryByRole("button", { name: "All (26)" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All (25)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skipped (0)" })).toBeInTheDocument();
  });
});

function filterLead(id: number, status: "save" | null = null) {
  return {
    job_id: id,
    title: `Lead ${id}`,
    company: "Client",
    source_name: "remoteok",
    url: `https://example.com/jobs/${id}`,
    score: 0.9,
    why: "Fit",
    signals: [],
    risks: [],
    action: "draft_bid" as const,
    matched_keywords: ["python"],
    freshness_score: 0.8,
    client_quality_score: 0.7,
    red_flags: [],
    user_status: status,
  };
}

test("Saved filter summary reports saved count, not ranking exclusions", async () => {
  vi.mocked(api.getPipelineStats).mockResolvedValue({
    saved_count: 1,
    pitched_count: 0,
    won_count: 0,
    skipped_count: 0,
    total_engaged: 1,
    pitch_rate: 0,
    win_rate: 0,
    saved_value: 0,
    pitched_value: 0,
    won_value: 0,
    active_pipeline_value: 0,
  });
  vi.mocked(api.getAuthFindings).mockResolvedValue({
    generated_at: "2026-10-05T00:00:00Z",
    total_scanned: 10,
    total_matched: 4,
    total_findings: 4,
    freelance_focus: true,
    action_counts: { draft_bid: 4, watch: 0, skip: 0 },
    keywords: ["python"],
    items: [filterLead(1, "save"), filterLead(2), filterLead(3), filterLead(4)],
  });

  render(<LeadsPage />);
  await waitFor(() => expect(screen.getByText("Lead 1")).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: /Saved\s*\(\s*1\s*\)/ }));
  await waitFor(() => {
    expect(screen.getByText(/Saved filter · 1 saved/i)).toBeInTheDocument();
  });
  expect(screen.queryByText(/dropped after match/i)).not.toBeInTheDocument();
  expect(screen.getByText("Lead 1")).toBeInTheDocument();
  expect(screen.queryByText("Lead 2")).not.toBeInTheDocument();
});

test("single Unsave dismisses Why chips, clears save, and survives Saved filter + reload", async () => {
  let saved = true;
  vi.mocked(api.setLeadAction).mockImplementation(async (jobId, status, opts) => {
    if (opts?.reason_only) {
      return { job_id: jobId, status: saved ? "save" : null };
    }
    if (status === "clear") {
      saved = false;
      return { job_id: jobId, status: null };
    }
    saved = status === "save";
    return { job_id: jobId, status };
  });
  vi.mocked(api.getPipelineStats).mockImplementation(async () => ({
    saved_count: saved ? 1 : 0,
    pitched_count: 0,
    won_count: 0,
    skipped_count: 0,
    total_engaged: saved ? 1 : 0,
    pitch_rate: 0,
    win_rate: 0,
    saved_value: 0,
    pitched_value: 0,
    won_value: 0,
    active_pipeline_value: 0,
  }));
  vi.mocked(api.getAuthFindings).mockImplementation(async () => ({
    generated_at: "2026-10-05T00:00:00Z",
    total_scanned: 10,
    total_matched: 4,
    total_findings: 4,
    freelance_focus: true,
    action_counts: { draft_bid: 4, watch: 0, skip: 0 },
    keywords: ["python"],
    items: [filterLead(1, saved ? "save" : null), filterLead(2), filterLead(3), filterLead(4)],
  }));

  render(<LeadsPage />);
  await waitFor(() => expect(screen.getByText("Lead 1")).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: /^Unsave$/ }));
  await waitFor(() => {
    expect(api.setLeadAction).toHaveBeenCalledWith(
      1,
      "clear",
      expect.objectContaining({ reason_only: false }),
    );
  });
  expect(dismissAll).toHaveBeenCalled();

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /Saved\s*\(\s*0\s*\)/ })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: /Saved\s*\(\s*0\s*\)/ }));
  await waitFor(() => {
    expect(screen.getByText(/Saved filter · 0 saved/i)).toBeInTheDocument();
  });
  expect(screen.queryByText("Lead 1")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Refresh leads/i }));
  await waitFor(() => {
    expect(screen.getByRole("button", { name: /Saved\s*\(\s*0\s*\)/ })).toBeInTheDocument();
  });
  fireEvent.click(screen.getByRole("button", { name: /All\s*\(/ }));
  await waitFor(() => {
    expect(screen.getAllByRole("button", { name: /^Save$/ }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /^Unsave$/ })).not.toBeInTheDocument();
  });
});

