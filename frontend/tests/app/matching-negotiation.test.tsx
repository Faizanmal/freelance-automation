import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import EmployerProjectsPage from "@/app/employer/projects/page";
import NativeProjectDetailPage from "@/app/projects/[id]/page";

// Mock useParams from next/navigation
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-123" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// Mock API module
vi.mock("@/lib/api", () => ({
  getEmployerOrgs: vi.fn().mockResolvedValue({
    organizations: [
      {
        org_id: "org-alpha",
        name: "Acme Autonomous Corp",
        role: "owner",
        domain_verified: true,
      },
    ],
  }),
  getProjectTemplates: vi.fn().mockResolvedValue({
    templates: {
      fastapi_backend: {
        title: "FastAPI Backend & Microservices",
        scope_level: "medium",
        primary_segment: "ai_software_automation",
        suggested_budget_range: [2000, 6000],
        suggested_timeline_days: 21,
        skills_required: ["FastAPI", "Python", "PostgreSQL"],
        deliverables: ["Async REST API", "Pydantic Schemas", "Alembic Migrations"],
        acceptance_criteria: ["80%+ coverage", "OpenAPI docs", "Docker container"],
        boundaries: ["Mobile clients out of scope"],
        budget_basis_notes: "Mid-tier backend scope based on 40-60 engineer hours.",
      },
    },
  }),
  clarifyProjectScope: vi.fn().mockResolvedValue({
    clarification: {
      deliverables: ["Worker pool engine", "FastAPI metrics endpoint"],
      boundaries: ["Frontend UI excluded"],
      acceptance_criteria: ["End-to-end integration test passes"],
      suggested_skills: ["Python", "FastAPI"],
      budget_basis_notes: "Consistent with 50 engineer hours.",
      suggested_timeline_days: 18,
      clarification_notes: "Scope is unambiguous and well structured.",
      safety_check_passed: true,
      safety_warnings: [],
      risk_flags: [],
    },
  }),
  listProjects: vi.fn().mockResolvedValue({
    projects: [
      {
        id: "proj-123",
        org_id: "org-alpha",
        title: "Distributed Agent Pipeline",
        status: "approved_open",
        review_state: "clean",
        scope_level: "medium",
        budget_min: 3000,
        budget_max: 7000,
        currency: "USD",
        rate_period: "fixed",
        hiring_deadline: "2026-12-15T00:00:00Z",
        reconfirm_by: "2026-12-10T00:00:00Z",
        created_at: "2026-11-20T00:00:00Z",
      },
    ],
    count: 1,
  }),
  getProjectDetails: vi.fn().mockResolvedValue({
    project: {
      id: "proj-123",
      org_id: "org-alpha",
      org_name: "Acme Autonomous Corp",
      title: "Distributed Agent Pipeline",
      raw_description: "Build an event-driven agent worker pool with Redis and FastAPI.",
      ai_scope_summary: "Deliverable includes Celery/Redis pipeline and FastAPI dashboard.",
      ai_clarification_approved: true,
      primary_segment: "ai_software_automation",
      scope_level: "medium",
      work_type: "remote",
      commitment_type: "contract",
      required_hours_per_week: 25,
      budget_min: 3000,
      budget_max: 7000,
      currency: "USD",
      rate_period: "fixed",
      hiring_deadline: "2026-12-15T00:00:00Z",
      reconfirm_by: "2026-12-10T00:00:00Z",
      status: "approved_open",
      review_state: "approved",
      skills_required: ["FastAPI", "Python", "Redis"],
      acceptance_criteria: ["REST API endpoints", "Celery async worker"],
      payment_verified: false,
      shortlisted_candidates: [
        {
          id: "short-1",
          candidate_id: "cand-alice",
          stage: "interviewing",
          notes: "Strong distributed systems background.",
          created_at: "2026-11-21T00:00:00Z",
        },
      ],
      status_history: [],
      hiring_intent_evidence: {
        verified_org: true,
        org_domain: "acme.io",
        payment_verified: false,
        payment_method_status: "unverified",
        clear_budget: true,
        budget_basis: "25 hrs/week for 4 weeks",
        decision_deadline: "2026-12-15T00:00:00Z",
        freshness_status: "fresh",
        prior_hires_count: 3,
        native_application_fee: 0.0,
      },
      created_at: "2026-11-20T00:00:00Z",
    },
  }),
  getProjectClarifications: vi.fn().mockResolvedValue({
    clarifications: [
      {
        id: "c1",
        project_id: "proj-123",
        question: "Is Docker Compose required for local setup?",
        answer: "Yes, Docker Compose is expected for local development setup.",
        is_public: true,
        status: "answered",
        created_at: "2026-11-20T00:00:00Z",
      },
    ],
  }),
  reconfirmProjectHiringIntent: vi.fn().mockResolvedValue({
    message: "Hiring intent reconfirmed! Active through: 12/10/2026",
    reconfirm_by: "2026-12-10T00:00:00Z",
  }),
  getProjectShortlist: vi.fn().mockResolvedValue({
    project_id: "proj-123",
    shortlist: [
      {
        freelancer_id: "user-bob-dev",
        headline: "Senior Python & FastAPI Specialist",
        overall_score: 0.92,
        skill_score: 1.0,
        budget_score: 0.9,
        availability_score: 0.85,
        work_pref_score: 1.0,
        newcomer_boost: 0.0,
        reasons: ["Verified skills: Python, FastAPI", "Budget within stated range"],
        missing_information: [],
        is_newcomer: false,
        verification_level: 3,
      },
      {
        freelancer_id: "user-charlie-dev",
        headline: "Fullstack Python & Redis Developer",
        overall_score: 0.86,
        skill_score: 0.85,
        budget_score: 0.95,
        availability_score: 0.9,
        work_pref_score: 1.0,
        newcomer_boost: 0.06,
        reasons: ["Verified skills: Python, Redis", "Equitable rotation boost applied"],
        missing_information: ["FastAPI verification pending"],
        is_newcomer: true,
        verification_level: 2,
      },
    ],
    count: 2,
    requested_more: false,
  }),
  listProjectApplications: vi.fn().mockResolvedValue({
    applications: [
      {
        id: "app-bob-1",
        project_id: "proj-123",
        freelancer_id: "user-bob-dev",
        structured_pitch: "I have 6 years building async FastAPI microservices with Redis queues.",
        relevant_artifacts: ["https://github.com/bob/fastapi-redis"],
        proposed_rate: 3200,
        proposed_rate_period: "fixed",
        estimated_days: 14,
        status: "submitted",
        created_at: "2026-11-21T00:00:00Z",
      },
    ],
  }),
  listFreelancerApplications: vi.fn().mockResolvedValue({
    applications: [
      {
        id: "app-bob-1",
        project_id: "proj-123",
        freelancer_id: "user-bob-dev",
        structured_pitch: "I have 6 years building async FastAPI microservices with Redis queues.",
        relevant_artifacts: ["https://github.com/bob/fastapi-redis"],
        proposed_rate: 3200,
        proposed_rate_period: "fixed",
        estimated_days: 14,
        status: "submitted",
        created_at: "2026-11-21T00:00:00Z",
      },
    ],
  }),
  getProjectOffers: vi.fn().mockResolvedValue({
    offers: [
      {
        id: "off-123",
        project_id: "proj-123",
        org_id: "org-alpha",
        freelancer_id: "user-bob-dev",
        application_id: "app-bob-1",
        agreed_amount: 3200,
        currency: "USD",
        contract_type: "fixed_price",
        milestones: [
          { title: "Core Architecture & Endpoints", amount: 1600, due_days: 7 },
          { title: "Integration & Testing", amount: 1600, due_days: 14 },
        ],
        scope_summary: "Distributed async worker core with 2 milestones.",
        version: 1,
        status: "pending_review",
        creator_role: "client",
        decision_deadline: "2026-12-05T00:00:00Z",
        accepted_at: null,
        declined_at: null,
        created_at: "2026-11-21T00:00:00Z",
      },
    ],
  }),
  inviteTalentToProject: vi.fn().mockResolvedValue({
    message: "Invitation extended to candidate!",
    invitation_id: "inv-999",
    status: "pending",
  }),
  initiateProjectConversation: vi.fn().mockResolvedValue({
    message: "Discussion opened",
    conversation_id: "conv-123",
    status: "active",
  }),
  getConversationMessages: vi.fn().mockResolvedValue({
    messages: [
      {
        id: "msg-1",
        conversation_id: "conv-123",
        sender_id: "user-alice-client",
        sender_role: "client",
        content: "Hi Bob, we loved your async architecture portfolio.",
        attachments: [],
        read_at: null,
        created_at: "2026-11-21T01:00:00Z",
      },
    ],
  }),
  sendConversationMessage: vi.fn().mockResolvedValue({
    message: "Delivered",
    message_id: "msg-2",
    has_masked_contacts: false,
  }),
  draftNegotiationTerms: vi.fn().mockResolvedValue({
    draft_terms: {
      scope_summary: "AI drafted 2-milestone distributed async core delivery.",
      milestones: [
        { title: "MVP Core Setup", amount: 1600, due_days: 7 },
        { title: "Testing & Signoff", amount: 1600, due_days: 14 },
      ],
      payment_terms: "Bilateral milestones escrow upon acceptance.",
      notes: "Balanced milestones schedule.",
    },
  }),
  createProjectOffer: vi.fn().mockResolvedValue({
    message: "Formal offer created",
    offer_id: "off-new",
    version: 1,
    status: "pending_review",
  }),
  acceptProjectOffer: vi.fn().mockResolvedValue({
    message: "Offer accepted",
    offer_id: "off-123",
    status: "accepted",
  }),
  counterProposeOffer: vi.fn().mockResolvedValue({
    message: "Counter-proposal submitted",
    offer_id: "off-123",
    version: 2,
    status: "counter_proposed",
  }),
  withdrawApplication: vi.fn().mockResolvedValue({
    message: "Withdrawn gracefully",
    status: "withdrawn",
  }),
  submitExpressionOfInterest: vi.fn().mockResolvedValue({
    message: "Submitted",
    application_id: "app-new",
    status: "submitted",
  }),
}));

describe("Phase 15: Fair Marketplace Matching, Applications & Direct Negotiation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders organic match shortlist with score breakdowns and firewall guarantee", async () => {
    render(<EmployerProjectsPage />);

    // Wait for project listing to load
    await waitFor(() => {
      expect(screen.getByText("Distributed Agent Pipeline")).toBeInTheDocument();
    });

    // Click "Manage & Shortlist"
    fireEvent.click(screen.getByText("Manage & Shortlist"));

    // Switch to "AI Matches & Negotiation" tab
    await waitFor(() => {
      expect(screen.getByText(/AI Matches & Negotiation/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/AI Matches & Negotiation/i));

    // Verify firewall guarantee banner is displayed
    await waitFor(() => {
      expect(screen.getByText(/Fair Marketplace Matching Firewall Active/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Paid subscription tiers and advertising credits are strictly excluded/i)
      ).toBeInTheDocument();
    });

    // Verify Bob (Expert) and Charlie (Newcomer with boost) are rendered
    expect(screen.getByText("Senior Python & FastAPI Specialist")).toBeInTheDocument();
    expect(screen.getByText("Fullstack Python & Redis Developer")).toBeInTheDocument();
    expect(screen.getByText("Newcomer Boost")).toBeInTheDocument();

    // Verify match score and reasons
    expect(screen.getByText("92% Match")).toBeInTheDocument();
    expect(screen.getByText("Verified skills: Python, FastAPI")).toBeInTheDocument();
    expect(screen.getByText("FastAPI verification pending")).toBeInTheDocument();
  });

  it("supports client inviting talent and opening direct discussion", async () => {
    render(<EmployerProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText("Distributed Agent Pipeline")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Manage & Shortlist"));

    await waitFor(() => {
      expect(screen.getByText(/AI Matches & Negotiation/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/AI Matches & Negotiation/i));

    // Click Invite on candidate card
    await waitFor(() => {
      const inviteButtons = screen.getAllByRole("button", { name: "Invite" });
      fireEvent.click(inviteButtons[0]);
    });

    await waitFor(() => {
      expect(screen.getByText("Invitation extended to candidate!")).toBeInTheDocument();
    });
  });

  it("displays freelancer $0.00 expression of interest and bilateral offer acceptance", async () => {
    render(<NativeProjectDetailPage />);

    // Verify zero application fee guarantee
    await waitFor(() => {
      expect(screen.getByText("$0.00 (100% Free)")).toBeInTheDocument();
      expect(screen.getByText("Your Expression of Interest")).toBeInTheDocument();
    });

    // Verify bilateral offer card is rendered with Accept Offer button
    await waitFor(() => {
      expect(screen.getByText("Offer v1")).toBeInTheDocument();
      expect(screen.getByText("$3,200 USD")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Accept Offer" })).toBeInTheDocument();
    });

    // Accept offer
    fireEvent.click(screen.getByRole("button", { name: "Accept Offer" }));
    await waitFor(() => {
      expect(screen.getByText("Offer accepted! Contract established.")).toBeInTheDocument();
    });
  });

  it("handles 409 concurrency conflict when position is already filled", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.acceptProjectOffer).mockRejectedValueOnce(
      new Error("Conflict (409): Project position has already been filled by another accepted offer.")
    );

    render(<NativeProjectDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Accept Offer" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Accept Offer" }));

    await waitFor(() => {
      expect(screen.getByText(/Concurrency Conflict \(409\)/i)).toBeInTheDocument();
      expect(screen.getByText(/already been filled/i)).toBeInTheDocument();
    });
  });
});
