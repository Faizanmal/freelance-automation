import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PipelinePage from "@/app/pipeline/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const boardMock = vi.fn();
const dashMock = vi.fn();

vi.mock("@/lib/api", () => ({
  getToken: () => "tok",
  getPipelineBoard: (...args: unknown[]) => boardMock(...args),
  getWorkspaceDashboard: (...args: unknown[]) => dashMock(...args),
  listLeadNotes: vi.fn(async () => ({ notes: [] })),
  setPipelineStage: vi.fn(),
  startCopilotRun: vi.fn(),
  updateCopilotDraft: vi.fn(),
  updatePipelineLead: vi.fn(),
  addLeadNote: vi.fn(),
  addLeadReminder: vi.fn(),
  cancelCopilotRun: vi.fn(),
}));

describe("Pipeline page", () => {
  beforeEach(() => {
    boardMock.mockResolvedValue({
      stages: ["saved", "applied", "won"],
      columns: {
        saved: [
          {
            id: 1,
            job_id: 10,
            status: "save",
            pipeline_stage: "saved",
            job: { id: 10, title: "React contract", company: "Acme", url: "https://example.com/10" },
          },
        ],
        applied: [],
        won: [],
      },
    });
    dashMock.mockResolvedValue({
      demo: false,
      follow_ups_due: 1,
      qualified_leads: 2,
      active_opportunities: 2,
      stage_counts: { saved: 1 },
      stage_conversion: {
        saved_to_applied: 0.5,
        applied_to_interview: 0,
        interview_to_won: 0,
      },
      time_spent_seconds: 120,
      won_revenue: 0,
      notes: null,
    });
  });

  it("renders workspace metrics and board lead", async () => {
    render(<PipelinePage />);
    await waitFor(() => {
      expect(screen.getByText("Pipeline")).toBeTruthy();
    });
    expect(screen.getByText("Follow-ups due")).toBeTruthy();
    expect(await screen.findByText("React contract")).toBeTruthy();
    expect(screen.getByText(/never send by themselves/i)).toBeTruthy();
  });
});
