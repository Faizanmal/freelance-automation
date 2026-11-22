import React from "react";
import { describe, expect, it, vi } from "vitest";
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
      skills_required: ["Python", "Redis", "FastAPI"],
      acceptance_criteria: ["Latency < 200ms", "Zero message loss on retry"],
      budget_min: 3000,
      budget_max: 7000,
      currency: "USD",
      rate_period: "fixed",
      budget_basis_notes: "Calculated based on standard contract scope.",
      hiring_deadline: "2026-12-15T00:00:00Z",
      payment_verified: false,
      status: "approved_open",
      review_state: "clean",
      is_client_owner: true,
      hiring_intent_evidence: {
        verified_org: true,
        org_name: "Acme Autonomous Corp",
        verified_contact_method: true,
        payment_method_status: "unverified",
        payment_verified: false,
        unverified_payment_notice: "Payment method not verified. Beta listing does not guarantee funding.",
        prior_hires_count: 2,
        response_rate_percent: 95.0,
        decision_deadline: "2026-12-15T00:00:00Z",
        reconfirm_by: "2026-12-10T00:00:00Z",
        freshness_status: "fresh",
        native_application_fee: 0.0,
      },
      shortlisted_candidates: [
        {
          id: "short-1",
          candidate_id: "cand-alice",
          stage: "interviewing",
          notes: "Strong distributed systems background.",
          created_at: "2026-11-21T00:00:00Z",
        },
      ],
      status_history: [
        {
          id: "hist-1",
          from_status: "draft",
          to_status: "approved_open",
          action: "publish",
          actor_id: "user-client-1",
          reason: "Published by client",
          created_at: "2026-11-20T00:00:00Z",
        },
      ],
    },
  }),
  clarifyProjectScope: vi.fn().mockResolvedValue({
    clarification: {
      deliverables: ["Worker pool engine", "FastAPI metrics endpoint"],
      boundaries: ["Frontend UI excluded"],
      acceptance_criteria: ["End-to-end integration test passes"],
      suggested_skills: ["Python", "FastAPI"],
      budget_basis_notes: "Consistent with 50 engineer hours.",
      unknowns: ["Expected worker concurrency limit"],
      summary: "AI Clarification: Distributed async pipeline.",
      content_flag: false,
      content_reason: null,
      duplicate_hash: "mockhash123",
    },
  }),
  createProjectBrief: vi.fn().mockResolvedValue({
    message: "Project brief created in draft",
    project: {
      id: "proj-456",
      org_id: "org-alpha",
      title: "New Agent Pipeline",
      status: "draft",
      ai_clarification_approved: false,
      ai_scope_summary: null,
      budget_min: 2500,
      budget_max: 5000,
      currency: "USD",
      hiring_deadline: "2026-12-20T00:00:00Z",
    },
  }),
  approveProjectAiScope: vi.fn().mockResolvedValue({
    message: "AI scope approved",
    ai_clarification_approved: true,
  }),
  submitProjectBrief: vi.fn().mockResolvedValue({
    message: "Project published and open for candidates.",
    status: "approved_open",
    review_state: "clean",
  }),
  transitionProjectStatus: vi.fn().mockResolvedValue({
    message: "Project transitioned to shortlist",
    status: "shortlist",
  }),
  reconfirmProjectHiringIntent: vi.fn().mockResolvedValue({
    message: "Hiring intent reconfirmed",
    reconfirm_by: "2026-12-25T00:00:00Z",
  }),
  shortlistProjectCandidate: vi.fn().mockResolvedValue({
    message: "Candidate shortlisted",
    shortlist_id: "short-2",
    stage: "shortlisted",
  }),
  updateProjectCandidateStage: vi.fn().mockResolvedValue({
    message: "Candidate stage updated",
    stage: "offered",
  }),
  getProjectClarifications: vi.fn().mockResolvedValue({
    clarifications: [
      {
        id: "clar-1",
        project_id: "proj-123",
        freelancer_id: "user-free-1",
        question: "Is Docker Compose required for local setup?",
        answer: "Yes, Docker Compose is expected for running dependencies locally.",
        is_public: true,
        status: "answered",
        created_at: "2026-11-21T00:00:00Z",
        answered_at: "2026-11-21T02:00:00Z",
      },
    ],
  }),
  answerProjectClarification: vi.fn().mockResolvedValue({
    message: "Clarification answered",
    status: "answered",
  }),
  submitProjectClarification: vi.fn().mockResolvedValue({
    message: "Clarification question submitted",
    clarification_id: "clar-2",
  }),
  appealProjectModeration: vi.fn().mockResolvedValue({
    message: "Appeal submitted",
    queue_id: "queue-1",
  }),
  listFreelancerApplications: vi.fn().mockResolvedValue({
    applications: [],
  }),
  getProjectOffers: vi.fn().mockResolvedValue({
    offers: [],
  }),
  getProjectShortlist: vi.fn().mockResolvedValue({
    project_id: "proj-123",
    shortlist: [],
    count: 0,
    requested_more: false,
  }),
  listProjectApplications: vi.fn().mockResolvedValue({
    applications: [],
  }),
  inviteTalentToProject: vi.fn().mockResolvedValue({
    message: "Invited",
    invitation_id: "inv-1",
    status: "pending",
  }),
  initiateProjectConversation: vi.fn().mockResolvedValue({
    message: "Started",
    conversation_id: "conv-1",
    status: "active",
  }),
  getConversationMessages: vi.fn().mockResolvedValue({
    messages: [],
  }),
  sendConversationMessage: vi.fn().mockResolvedValue({
    message: "Delivered",
    message_id: "msg-1",
    has_masked_contacts: false,
  }),
  draftNegotiationTerms: vi.fn().mockResolvedValue({
    draft_terms: {
      scope_summary: "Terms",
      milestones: [],
      payment_terms: "Terms",
      notes: "",
    },
  }),
  createProjectOffer: vi.fn().mockResolvedValue({
    message: "Created",
    offer_id: "off-1",
    version: 1,
    status: "pending_review",
  }),
  acceptProjectOffer: vi.fn().mockResolvedValue({
    message: "Accepted",
    offer_id: "off-1",
    status: "accepted",
  }),
  counterProposeOffer: vi.fn().mockResolvedValue({
    message: "Countered",
    offer_id: "off-1",
    version: 2,
    status: "counter_proposed",
  }),
  withdrawApplication: vi.fn().mockResolvedValue({
    message: "Withdrawn",
    status: "withdrawn",
  }),
  submitExpressionOfInterest: vi.fn().mockResolvedValue({
    message: "Submitted",
    application_id: "app-1",
    status: "submitted",
  }),
}));

describe("Phase 14 Client Workspace & Proof of Hiring Intent UI", () => {
  it("renders Client Projects Dashboard with active listings and status", async () => {
    render(<EmployerProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText("Client Workspace & Projects")).toBeInTheDocument();
      expect(screen.getByText("Distributed Agent Pipeline")).toBeInTheDocument();
      expect(screen.getByText("Open & Active")).toBeInTheDocument();
      expect(screen.getByText("Manage & Shortlist")).toBeInTheDocument();
    });
  });

  it("navigates to creation wizard and runs AI scope clarification", async () => {
    render(<EmployerProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText("Project Creation Wizard")).toBeInTheDocument();
    });

    // Click wizard tab
    fireEvent.click(screen.getByText("Project Creation Wizard"));

    // Check wizard elements
    expect(screen.getByText("Standardized Project Wizard")).toBeInTheDocument();
    expect(screen.getByText("FastAPI Backend & Microservices")).toBeInTheDocument();

    // Select template
    fireEvent.click(screen.getByText("FastAPI Backend & Microservices"));

    // Click Run AI Scope Clarification
    const clarifyBtn = screen.getByText("Run AI Scope Clarification");
    fireEvent.click(clarifyBtn);

    await waitFor(() => {
      expect(screen.getByText("AI Scope Breakdown & Safety Scan")).toBeInTheDocument();
      expect(screen.getByText("Safety Check Passed")).toBeInTheDocument();
      expect(screen.getByText("Worker pool engine")).toBeInTheDocument();
    });
  });

  it("manages project details, candidate shortlist, and intent evidence", async () => {
    render(<EmployerProjectsPage />);

    await waitFor(() => {
      expect(screen.getByText("Manage & Shortlist")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Manage & Shortlist"));

    await waitFor(() => {
      expect(screen.getByText("Hiring Intent Evidence")).toBeInTheDocument();
      expect(screen.getByText("Active Proof")).toBeInTheDocument();
      expect(screen.getByText("Unverified Payment")).toBeInTheDocument();
      expect(screen.getByText("Shortlisted Candidates (1)")).toBeInTheDocument();
      expect(screen.getByText("Candidate ID: cand-alice")).toBeInTheDocument();
    });

    // Reconfirm Intent button
    const reconfirmBtn = screen.getByText("Reconfirm Hiring Intent Now");
    expect(reconfirmBtn).toBeInTheDocument();
    fireEvent.click(reconfirmBtn);

    await waitFor(() => {
      expect(screen.getByText(/Hiring intent reconfirmed!/i)).toBeInTheDocument();
    });
  });

  it("renders Freelancer Native Project Detail with zero-fee guarantee and Q&A", async () => {
    render(<NativeProjectDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Distributed Agent Pipeline")).toBeInTheDocument();
      expect(screen.getByText("Proof of Hiring Intent")).toBeInTheDocument();
      expect(screen.getByText("$0.00 (100% Free)")).toBeInTheDocument();
      expect(screen.getByText("Unverified / Not Funded")).toBeInTheDocument();
      expect(screen.getByText("Public Clarification Q&A")).toBeInTheDocument();
      expect(
        screen.getByText("Q: Is Docker Compose required for local setup?")
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Yes, Docker Compose is expected/i)
      ).toBeInTheDocument();
    });
  });
});
