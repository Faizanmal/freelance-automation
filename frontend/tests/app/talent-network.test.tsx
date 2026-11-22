import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import TalentProfileEditorPage from "@/app/talent/profile/page";
import TalentDirectoryPage from "@/app/talent/page";
import EmployerSettingsPage from "@/app/employer/settings/page";

// Mock API module
vi.mock("@/lib/api", () => ({
  getNetworkProfile: vi.fn().mockResolvedValue({
    profile: {
      id: "prof-alice",
      headline: "Senior AI Automation Architect",
      bio: "Building autonomous agent pipelines and FastAPI microservices.",
      primary_segment: "ai_software_automation",
      years_experience: 7.5,
      location_display: "Remote (UTC+1)",
      is_published: false,
      status: "private",
      is_sample: false,
      contact_allowed: false,
      availability: {
        status: "available",
        hours_per_week: 40,
        expires_at: "2026-12-31T00:00:00Z",
      },
      rate_preference: {
        min_rate: 90,
        max_rate: 150,
        currency: "USD",
        rate_type: "hourly",
      },
      listing_consent: {
        opt_in_directory: false,
        allow_platform_contact: false,
        search_indexing_consent: false,
      },
      skills: [
        {
          id: "sk-1",
          skill_name: "Python",
          category: "backend",
          years_of_experience: 6,
          verification_status: "verified",
        },
      ],
      portfolio_artifacts: [
        {
          id: "art-1",
          title: "Agent Orchestration Core",
          url: "https://github.com/alice/agent-core",
          artifact_type: "github_repo",
          contribution_role: "owner",
          verification_status: "verified",
        },
      ],
    },
  }),
  updateNetworkProfile: vi.fn().mockResolvedValue({ message: "Profile updated" }),
  addNetworkSkill: vi.fn().mockResolvedValue({ message: "Skill saved" }),
  deleteNetworkSkill: vi.fn().mockResolvedValue({ message: "Skill removed" }),
  addNetworkArtifact: vi.fn().mockResolvedValue({ message: "Artifact saved" }),
  deleteNetworkArtifact: vi.fn().mockResolvedValue({ message: "Artifact removed" }),
  updateNetworkAvailability: vi.fn().mockResolvedValue({ message: "Availability updated" }),
  updateNetworkRates: vi.fn().mockResolvedValue({ message: "Rates updated" }),
  updateNetworkConsent: vi.fn().mockResolvedValue({ message: "Consent updated" }),
  publishNetworkProfile: vi.fn().mockResolvedValue({ message: "Profile published" }),
  unpublishNetworkProfile: vi.fn().mockResolvedValue({ message: "Profile unpublished" }),
  getNetworkPreview: vi.fn().mockResolvedValue({
    preview: {
      headline: "Senior AI Automation Architect",
      primary_segment: "ai_software_automation",
      years_experience: 7.5,
      contact_allowed: false,
      skills: [],
    },
  }),
  searchTalentDirectory: vi.fn().mockResolvedValue({
    total: 1,
    limit: 50,
    offset: 0,
    items: [
      {
        id: "prof-alice",
        headline: "Senior AI Automation Architect",
        bio: "Specializing in distributed crawling and agent workflows.",
        primary_segment: "ai_software_automation",
        years_experience: 7.5,
        location_display: "Remote (UTC+1)",
        verification_level: 3,
        is_newcomer: false,
        contact_allowed: true,
        rates: {
          min_rate: 90,
          rate_type: "hourly",
          currency: "USD",
        },
        availability: {
          status: "available",
        },
        top_skills: [{ name: "Python", verified: true }],
      },
    ],
  }),
  getNetworkReputation: vi.fn().mockResolvedValue({
    reputation: {
      has_sufficient_data: true,
      status_label: "Verified history",
      sample_size: 5,
      components: {
        confirmed_deliveries_count: 3,
        response_rate_pct: 98,
        repeat_hire_rate_pct: 40,
        paid_transactions_volume_usd: 4200,
      },
    },
  }),
  getEmployerOrgs: vi.fn().mockResolvedValue({
    organizations: [
      {
        org_id: "org-1",
        name: "Acme AI Corp",
        slug: "acme-ai-corp",
        role: "owner",
        domain_verified: true,
      },
    ],
  }),
  getEmployerOrgDetails: vi.fn().mockResolvedValue({
    organization: {
      id: "org-1",
      name: "Acme AI Corp",
      slug: "acme-ai-corp",
      industry: "technology",
      org_domain: "acmeai.com",
      domain_verified: true,
      my_role: "owner",
      members: [
        {
          id: "mem-1",
          email: "owner@acmeai.com",
          role: "owner",
          seat_status: "active",
        },
        {
          id: "mem-2",
          email: "lead@acmeai.com",
          role: "hiring_manager",
          seat_status: "active",
        },
      ],
    },
  }),
  createEmployerOrg: vi.fn().mockResolvedValue({
    organization: { id: "org-2", name: "New Corp" },
  }),
  inviteEmployerOrgMember: vi.fn().mockResolvedValue({
    invitation: { invitation_token: "inv_123" },
  }),
  updateEmployerOrgMemberRole: vi.fn().mockResolvedValue({ message: "Updated" }),
  revokeEmployerOrgSeat: vi.fn().mockResolvedValue({ message: "Revoked" }),
  getEmployerOrgAuditLogs: vi.fn().mockResolvedValue({
    audit_logs: [
      {
        id: "log-1",
        action: "invite_sent",
        actor_id: "user-1",
        created_at: "2026-11-20T10:00:00Z",
      },
    ],
  }),
  runSandboxVerification: vi.fn().mockResolvedValue({
    success: true,
    result: { verified_role: "owner", commit_count: 50 },
  }),
}));

describe("Phase 13 Talent & Employer Network UX", () => {
  it("renders Freelancer Profile Editor with privacy consent and skills", async () => {
    render(<TalentProfileEditorPage />);
    await waitFor(() => {
      expect(screen.getByText("Freelancer Talent Profile")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Senior AI Automation Architect")).toBeInTheDocument();
      expect(screen.getByText("Opt-in to Public Talent Directory")).toBeInTheDocument();
      expect(screen.getByText("Python")).toBeInTheDocument();
      expect(screen.getByText("Agent Orchestration Core")).toBeInTheDocument();
    });
  });

  it("renders Verified Talent Directory with filterable cards and verified badges", async () => {
    render(<TalentDirectoryPage />);
    await waitFor(() => {
      expect(screen.getByText("Verified Talent Directory")).toBeInTheDocument();
      expect(screen.getByText("Senior AI Automation Architect")).toBeInTheDocument();
      expect(screen.getByText("Level 3 Verified")).toBeInTheDocument();
      expect(screen.getByText("View Evidence")).toBeInTheDocument();
    });
  });

  it("renders Employer Organization settings with team seats and domain verification", async () => {
    render(<EmployerSettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("Employer Organization Workspace")).toBeInTheDocument();
      expect(screen.getByText("Acme AI Corp (owner)")).toBeInTheDocument();
      expect(screen.getByText("Domain Verified")).toBeInTheDocument();
      expect(screen.getByText("owner@acmeai.com")).toBeInTheDocument();
      expect(screen.getByText("lead@acmeai.com")).toBeInTheDocument();
    });
  });
});
