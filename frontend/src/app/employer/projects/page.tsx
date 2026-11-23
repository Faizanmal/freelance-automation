"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getErrorMessage } from "@/lib/errors";
import {
  AlertCircle,
  AlertTriangle,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  DollarSign,
  FileText,
  Filter,
  HelpCircle,
  Layers,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
} from "lucide-react";
import {
  acceptProjectOffer,
  answerProjectClarification,
  appealProjectModeration,
  approveProjectAiScope,
  clarifyProjectScope,
  counterProposeOffer,
  createProjectBrief,
  createProjectOffer,
  declineApplication,
  draftNegotiationTerms,
  getConversationMessages,
  getEmployerOrgs,
  getProjectClarifications,
  getProjectDetails,
  getProjectOffers,
  getProjectShortlist,
  getProjectTemplates,
  initiateProjectConversation,
  inviteTalentToProject,
  listProjectApplications,
  listProjects,
  reconfirmProjectHiringIntent,
  reportProjectConversation,
  sendConversationMessage,
  shortlistProjectCandidate,
  submitProjectBrief,
  transitionProjectStatus,
  updateProjectCandidateStage,
  type CandidateMatchItem,
  type CandidateShortlistEntry,
  type NativeProjectItem,
  type ProjectApplicationItem,
  type ProjectClarificationItem,
  type ProjectMessageItem,
  type ProjectOfferItem,
  type ProjectTemplate,
  type ScopeClarificationResult,
} from "@/lib/api";

export default function EmployerProjectsPage() {
  const [orgs, setOrgs] = useState<Awaited<ReturnType<typeof getEmployerOrgs>>["organizations"]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>("");
  const [projects, setProjects] = useState<NativeProjectItem[]>([]);
  const [selectedProject, setSelectedProject] = useState<Awaited<ReturnType<typeof getProjectDetails>>["project"] | null>(null);
  const [templates, setTemplates] = useState<Record<string, ProjectTemplate>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"projects" | "wizard" | "details" | "clarifications" | "matching">("projects");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Wizard State
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string>("");
  const [projectTitle, setProjectTitle] = useState("");
  const [rawDescription, setRawDescription] = useState("");
  const [budgetMin, setBudgetMin] = useState<number>(2000);
  const [budgetMax, setBudgetMax] = useState<number>(5000);
  const [currency, setCurrency] = useState("USD");
  const [ratePeriod, setRatePeriod] = useState<"hourly" | "fixed" | "monthly_retainer">("fixed");
  const [scopeLevel, setScopeLevel] = useState<"small" | "medium" | "large" | "enterprise">("medium");
  const [workType, setWorkType] = useState<"remote" | "hybrid" | "onsite">("remote");
  const [commitmentType, setCommitmentType] = useState<"contract" | "full_time" | "part_time">("contract");
  const [requiredHours, setRequiredHours] = useState(20);
  const [hiringDeadlineDays, setHiringDeadlineDays] = useState(14);
  const [clarificationResult, setClarificationResult] = useState<ScopeClarificationResult | null>(null);
  const [clarifyingScope, setClarifyingScope] = useState(false);
  const [aiApproved, setAiApproved] = useState(false);
  const [createdProjectId, setCreatedProjectId] = useState<string | null>(null);

  // Clarifications state
  const [clarifications, setClarifications] = useState<ProjectClarificationItem[]>([]);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});

  // Appeal state
  const [showAppealModal, setShowAppealModal] = useState(false);
  const [appealDetails, setAppealDetails] = useState("");

  // Candidate Shortlist modal state
  const [showShortlistModal, setShowShortlistModal] = useState(false);
  const [candidateIdToAdd, setCandidateIdToAdd] = useState("");
  const [candidateNotesToAdd, setCandidateNotesToAdd] = useState("");

  // Phase 15: Matching, Applications, Messaging & Negotiation State
  const [matches, setMatches] = useState<CandidateMatchItem[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [moreCandidatesReason, setMoreCandidatesReason] = useState("");
  const [applications, setApplications] = useState<ProjectApplicationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ProjectMessageItem[]>([]);
  const [messageContent, setMessageContent] = useState("");
  const [offers, setOffers] = useState<ProjectOfferItem[]>([]);
  const [draftedTerms, setDraftedTerms] = useState<Awaited<ReturnType<typeof draftNegotiationTerms>>["draft_terms"] | null>(null);
  const [draftingTerms, setDraftingTerms] = useState(false);
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [offerTargetAppId, setOfferTargetAppId] = useState("");
  const [offerAmountInput, setOfferAmountInput] = useState<number>(3000);
  const [offerScopeInput, setOfferScopeInput] = useState("");
  const [conflictWarning, setConflictWarning] = useState<string | null>(null);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedOrgId) {
      loadProjects(selectedOrgId);
    }
  }, [selectedOrgId]);

  async function loadInitialData() {
    try {
      setLoading(true);
      setError(null);
      const [orgRes, tplRes] = await Promise.all([
        getEmployerOrgs().catch(() => ({ organizations: [] })),
        getProjectTemplates().catch(() => ({ templates: {} })),
      ]);

      setOrgs(orgRes.organizations || []);
      setTemplates(tplRes.templates || {});

      if (orgRes.organizations?.length > 0) {
        setSelectedOrgId(orgRes.organizations[0].org_id);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load initial project workspace data");
    } finally {
      setLoading(false);
    }
  }

  async function loadProjects(orgId: string) {
    try {
      setLoading(true);
      const res = await listProjects({ org_id: orgId, view: "client" });
      setProjects(res.projects || []);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load client projects");
    } finally {
      setLoading(false);
    }
  }

  async function viewProjectDetails(projectId: string) {
    try {
      setSaving(true);
      setError(null);
      const res = await getProjectDetails(projectId);
      setSelectedProject(res.project);
      setActiveTab("details");
      loadClarifications(projectId);
      loadMatchingAndNegotiation(projectId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load project details");
    } finally {
      setSaving(false);
    }
  }

  async function loadClarifications(projectId: string) {
    try {
      const res = await getProjectClarifications(projectId, true);
      setClarifications(res.clarifications || []);
    } catch (err: unknown) {
      // Non-fatal
    }
  }

  async function loadMatchingAndNegotiation(projectId: string, requestMore?: boolean, moreReason?: string) {
    try {
      setLoadingMatches(true);
      const [shortlistRes, appRes, offersRes] = await Promise.all([
        getProjectShortlist(projectId, {
          limit: 5,
          request_more: requestMore,
          more_reason: moreReason,
        }).catch(() => ({ shortlist: [] })),
        listProjectApplications(projectId).catch(() => ({ applications: [] })),
        getProjectOffers(projectId).catch(() => ({ offers: [] })),
      ]);
      setMatches(shortlistRes.shortlist || []);
      setApplications(appRes.applications || []);
      setOffers(offersRes.offers || []);
    } catch (err: unknown) {
      // Non-fatal
    } finally {
      setLoadingMatches(false);
    }
  }

  async function handleInviteTalent(freelancerId: string) {
    if (!selectedProject) return;
    try {
      setSaving(true);
      setError(null);
      await inviteTalentToProject(selectedProject.id, {
        freelancer_id: freelancerId,
        invitation_note: "We reviewed your portfolio and match profile and invite you to express interest.",
      });
      setSuccess("Invitation extended to candidate!");
      await loadMatchingAndNegotiation(selectedProject.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to invite talent");
    } finally {
      setSaving(false);
    }
  }

  async function handleRequestMoreCandidates() {
    if (!selectedProject || !moreCandidatesReason.trim()) {
      setError("Please provide a reason code or explanation for requesting more candidates.");
      return;
    }
    await loadMatchingAndNegotiation(selectedProject.id, true, moreCandidatesReason.trim());
    setSuccess("Additional candidate shortlist requested.");
    setMoreCandidatesReason("");
  }

  async function handleStartDiscussion(freelancerId: string, applicationId?: string) {
    if (!selectedProject) return;
    try {
      setSaving(true);
      setError(null);
      const res = await initiateProjectConversation(selectedProject.id, freelancerId, applicationId);
      setActiveConvId(res.conversation_id);
      const msgRes = await getConversationMessages(res.conversation_id);
      setMessages(msgRes.messages || []);
      setSuccess("Discussion opened with candidate.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to open discussion");
    } finally {
      setSaving(false);
    }
  }

  async function handleSendMessage() {
    if (!activeConvId || !messageContent.trim()) return;
    try {
      setSaving(true);
      setError(null);
      await sendConversationMessage(activeConvId, {
        content: messageContent.trim(),
      });
      setMessageContent("");
      const msgRes = await getConversationMessages(activeConvId);
      setMessages(msgRes.messages || []);
      setSuccess("Message delivered.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to send message");
    } finally {
      setSaving(false);
    }
  }

  async function handleDraftNegotiation() {
    if (!selectedProject) return;
    try {
      setDraftingTerms(true);
      setError(null);
      const res = await draftNegotiationTerms({
        project_summary: selectedProject.ai_scope_summary || selectedProject.raw_description,
        agreed_amount: selectedProject.budget_min || 3000,
        duration_weeks: 3,
        milestone_count: 2,
      });
      setDraftedTerms(res.draft_terms);
      setOfferScopeInput(res.draft_terms.scope_summary);
      setOfferAmountInput(selectedProject.budget_min || 3000);
      setSuccess("Negotiation assistant drafted milestone outline and scope terms.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to draft negotiation terms");
    } finally {
      setDraftingTerms(false);
    }
  }

  async function handleCreateOfferSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProject || !offerTargetAppId) {
      setError("Select an application to extend an offer.");
      return;
    }
    try {
      setSaving(true);
      setError(null);
      await createProjectOffer(selectedProject.id, {
        application_id: offerTargetAppId,
        agreed_amount: offerAmountInput,
        contract_type: selectedProject.rate_period === "hourly" ? "hourly" : "fixed_price",
        milestones: draftedTerms?.milestones || [
          { title: "Core MVP Implementation", amount: Math.round(offerAmountInput * 0.5), due_days: 10 },
          { title: "Testing & Final Acceptance", amount: Math.round(offerAmountInput * 0.5), due_days: 20 },
        ],
        scope_summary: offerScopeInput || selectedProject.title,
        decision_deadline_days: 7,
      });
      setShowOfferModal(false);
      setSuccess("Formal offer created in pending review!");
      await loadMatchingAndNegotiation(selectedProject.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to create offer");
    } finally {
      setSaving(false);
    }
  }

  async function handleAcceptOfferClient(offerId: string) {
    if (!selectedProject) return;
    try {
      setSaving(true);
      setError(null);
      setConflictWarning(null);
      await acceptProjectOffer(offerId);
      setSuccess("Offer accepted! Project position is now filled.");
      await loadMatchingAndNegotiation(selectedProject.id);
      await viewProjectDetails(selectedProject.id);
    } catch (err: unknown) {
      if (getErrorMessage(err, "")?.includes("Conflict") || getErrorMessage(err, "")?.includes("409") || getErrorMessage(err, "")?.includes("superseded")) {
        setConflictWarning("Concurrency Conflict (409): This project position has already been filled by another accepted offer, or this offer has been superseded.");
      } else {
        setError(getErrorMessage(err, "") || "Failed to accept offer");
      }
    } finally {
      setSaving(false);
    }
  }

  function handleSelectTemplate(key: string) {
    setSelectedTemplateKey(key);
    const tpl = templates[key];
    if (tpl) {
      setProjectTitle(tpl.title);
      setScopeLevel(tpl.scope_level);
      setBudgetMin(tpl.suggested_budget_range[0]);
      setBudgetMax(tpl.suggested_budget_range[1]);
      setHiringDeadlineDays(tpl.suggested_timeline_days);
      const sampleText = `Deliverables needed:\n- ${tpl.deliverables.join("\n- ")}\n\nAcceptance Criteria:\n- ${tpl.acceptance_criteria.join("\n- ")}`;
      setRawDescription(sampleText);
    }
  }

  async function handleClarifyScope() {
    if (!rawDescription.trim() || rawDescription.length < 10) {
      setError("Please enter a project description of at least 10 characters before requesting AI scope clarification.");
      return;
    }
    try {
      setClarifyingScope(true);
      setError(null);
      const res = await clarifyProjectScope({
        raw_description: rawDescription,
        template_key: selectedTemplateKey || undefined,
      });
      setClarificationResult(res.clarification);
      setAiApproved(false);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to clarify project scope");
    } finally {
      setClarifyingScope(false);
    }
  }

  async function handleCreateDraft(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedOrgId) {
      setError("Please select or create an employer organization first.");
      return;
    }
    if (!projectTitle.trim() || !rawDescription.trim()) {
      setError("Title and description are required.");
      return;
    }
    if (budgetMin <= 0 || budgetMax <= 0 || budgetMax < budgetMin) {
      setError("Please provide a valid budget range where minimum is positive and maximum is >= minimum.");
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const deadline = new Date();
      deadline.setDate(deadline.getDate() + hiringDeadlineDays);

      const res = await createProjectBrief({
        org_id: selectedOrgId,
        title: projectTitle,
        raw_description: rawDescription,
        budget_min: budgetMin,
        budget_max: budgetMax,
        hiring_deadline: deadline.toISOString(),
        currency,
        rate_period: ratePeriod,
        scope_level: scopeLevel,
        work_type: workType,
        commitment_type: commitmentType,
        required_hours_per_week: requiredHours,
        skills_required: clarificationResult?.suggested_skills || [],
        acceptance_criteria: clarificationResult?.acceptance_criteria || [],
        template_key: selectedTemplateKey || undefined,
      });

      setCreatedProjectId(res.project.id);
      setSuccess("Project brief created as draft! Next: approve the AI scope summary and publish.");
      await loadProjects(selectedOrgId);
      await viewProjectDetails(res.project.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to create project brief");
    } finally {
      setSaving(false);
    }
  }

  async function handleApproveScope(projectId: string) {
    try {
      setSaving(true);
      setError(null);
      await approveProjectAiScope(projectId);
      setAiApproved(true);
      setSuccess("AI Scope Clarification approved! You can now submit your project for review or publishing.");
      await viewProjectDetails(projectId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to approve scope");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmitProject(projectId: string) {
    try {
      setSaving(true);
      setError(null);
      const res = await submitProjectBrief(projectId);
      setSuccess(res.message);
      await loadProjects(selectedOrgId);
      await viewProjectDetails(projectId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to submit project");
    } finally {
      setSaving(false);
    }
  }

  async function handleTransition(projectId: string, targetStatus: string, reason?: string) {
    try {
      setSaving(true);
      setError(null);
      const res = await transitionProjectStatus(projectId, {
        target_status: targetStatus,
        reason: reason || `Transitioned to ${targetStatus} via client dashboard`,
      });
      setSuccess(res.message);
      await loadProjects(selectedOrgId);
      await viewProjectDetails(projectId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to transition project status");
    } finally {
      setSaving(false);
    }
  }

  async function handleReconfirm(projectId: string) {
    try {
      setSaving(true);
      setError(null);
      const res = await reconfirmProjectHiringIntent(projectId);
      setSuccess(`Hiring intent reconfirmed! Active through: ${new Date(res.reconfirm_by).toLocaleDateString()}`);
      await loadProjects(selectedOrgId);
      await viewProjectDetails(projectId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to reconfirm hiring intent");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddCandidate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProject || !candidateIdToAdd.trim()) return;
    try {
      setSaving(true);
      setError(null);
      await shortlistProjectCandidate(selectedProject.id, {
        candidate_id: candidateIdToAdd.trim(),
        notes: candidateNotesToAdd.trim() || undefined,
      });
      setShowShortlistModal(false);
      setCandidateIdToAdd("");
      setCandidateNotesToAdd("");
      setSuccess("Candidate shortlisted!");
      await viewProjectDetails(selectedProject.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to shortlist candidate");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdateCandidateStage(
    candidateId: string,
    stage: CandidateShortlistEntry["stage"]
  ) {
    if (!selectedProject) return;
    try {
      setSaving(true);
      setError(null);
      await updateProjectCandidateStage(selectedProject.id, candidateId, { stage });
      setSuccess(`Candidate stage updated to ${stage}`);
      await viewProjectDetails(selectedProject.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to update candidate stage");
    } finally {
      setSaving(false);
    }
  }

  async function handleAnswerClarification(clarificationId: string) {
    const answer = answerDrafts[clarificationId];
    if (!answer?.trim()) return;
    try {
      setSaving(true);
      setError(null);
      await answerProjectClarification(clarificationId, {
        answer: answer.trim(),
        is_public: true,
      });
      setSuccess("Clarification question answered publicly!");
      if (selectedProject) {
        await loadClarifications(selectedProject.id);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to answer question");
    } finally {
      setSaving(false);
    }
  }

  async function handleAppealSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProject || !appealDetails.trim()) return;
    try {
      setSaving(true);
      setError(null);
      await appealProjectModeration(selectedProject.id, {
        appeal_details: appealDetails.trim(),
      });
      setShowAppealModal(false);
      setAppealDetails("");
      setSuccess("Appeal submitted for human moderation review.");
      await viewProjectDetails(selectedProject.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to submit appeal");
    } finally {
      setSaving(false);
    }
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "approved_open":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">Open & Active</span>;
      case "draft":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">Draft</span>;
      case "needs_clarification":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">Needs Clarification</span>;
      case "shortlist":
      case "interviewing":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">Interviewing</span>;
      case "offered_hired":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300">Hired</span>;
      case "expired":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">Expired</span>;
      case "closed":
      case "canceled":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400">{status}</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800">{status}</span>;
    }
  }

  return (
    <div className="container max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-3">
            <Building2 className="w-8 h-8 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Client Workspace & Projects</h1>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            High-intent project listings with structured AI clarification, observable hiring proof, and candidate lifecycle management.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {orgs.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Org:</span>
              <select
                aria-label="Employer Organization"
                value={selectedOrgId}
                onChange={(e) => setSelectedOrgId(e.target.value)}
                className="px-3 py-1.5 text-sm bg-card border border-border rounded-md font-medium"
              >
                {orgs.map((o) => (
                  <option key={o.org_id} value={o.org_id}>
                    {o.name} ({o.role})
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={() => {
              setActiveTab("wizard");
              setClarificationResult(null);
              setAiApproved(false);
              setCreatedProjectId(null);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm font-semibold rounded-md hover:bg-primary/90 transition"
          >
            <Plus className="w-4 h-4" />
            New Project Brief
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {success && (
        <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm font-medium">{success}</span>
          </div>
          <button onClick={() => setSuccess(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab("projects")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
            activeTab === "projects"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          My Project Listings ({projects.length})
        </button>
        <button
          onClick={() => setActiveTab("wizard")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
            activeTab === "wizard"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Project Creation Wizard
        </button>
        {selectedProject && (
          <>
            <button
              onClick={() => setActiveTab("details")}
              className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
                activeTab === "details"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Project Details & Intent
            </button>
            <button
              onClick={() => setActiveTab("clarifications")}
              className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
                activeTab === "clarifications"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Q&A Clarifications ({clarifications.length})
            </button>
            <button
              onClick={() => {
                setActiveTab("matching");
                if (selectedProject) loadMatchingAndNegotiation(selectedProject.id);
              }}
              className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
                activeTab === "matching"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              AI Matches & Negotiation ({matches.length})
            </button>
          </>
        )}
      </div>

      {conflictWarning && (
        <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm font-medium">{conflictWarning}</span>
          </div>
          <button onClick={() => setConflictWarning(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {/* TAB 1: Projects List */}
      {activeTab === "projects" && (
        <div className="space-y-4">
          {loading ? (
            <div className="p-12 text-center text-muted-foreground flex items-center justify-center gap-2">
              <RefreshCw className="w-5 h-5 animate-spin" />
              Loading projects...
            </div>
          ) : projects.length === 0 ? (
            <div className="p-12 text-center bg-card border border-border rounded-xl space-y-4">
              <FileText className="w-12 h-12 text-muted-foreground mx-auto" />
              <h3 className="text-lg font-semibold">No native projects found</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Create your first structured project brief to attract top talent with clear deliverables and verified hiring intent.
              </p>
              <button
                onClick={() => setActiveTab("wizard")}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md"
              >
                <Plus className="w-4 h-4" /> Start Creation Wizard
              </button>
            </div>
          ) : (
            <div className="grid gap-4">
              {projects.map((proj) => (
                <div
                  key={proj.id}
                  className="p-5 bg-card border border-border rounded-xl hover:border-primary/50 transition space-y-3"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold">{proj.title}</h2>
                        {getStatusBadge(proj.status)}
                        {proj.review_state === "flagged_for_human_review" && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                            Flagged for Review
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        <span>Created {new Date(proj.created_at).toLocaleDateString()}</span>
                        <span>•</span>
                        <span>Deadline: {new Date(proj.hiring_deadline).toLocaleDateString()}</span>
                        <span>•</span>
                        <span className="font-semibold text-foreground">
                          ${proj.budget_min.toLocaleString()} - ${proj.budget_max.toLocaleString()} {proj.currency} ({proj.rate_period})
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => viewProjectDetails(proj.id)}
                        className="px-3 py-1.5 text-xs font-medium bg-secondary text-secondary-foreground rounded hover:bg-secondary/80 transition"
                      >
                        Manage & Shortlist
                      </button>
                      {proj.status === "approved_open" && (
                        <button
                          onClick={() => handleReconfirm(proj.id)}
                          className="px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded hover:bg-emerald-700 transition"
                        >
                          Reconfirm Intent
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Project Creation Wizard */}
      {activeTab === "wizard" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="p-6 bg-card border border-border rounded-xl space-y-6">
              <div className="flex items-center gap-2 border-b border-border pb-4">
                <Sparkles className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-bold">Standardized Project Wizard</h2>
              </div>

              {/* Template Picker */}
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  1. Choose a Standardized Template (Optional)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {Object.entries(templates).map(([key, tpl]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleSelectTemplate(key)}
                      className={`p-3 text-left border rounded-lg transition ${
                        selectedTemplateKey === key
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-border/80"
                      }`}
                    >
                      <div className="font-semibold text-xs text-foreground">{tpl.title}</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        ${tpl.suggested_budget_range[0]} - ${tpl.suggested_budget_range[1]} • {tpl.suggested_timeline_days}d
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Project Title & Description */}
              <form onSubmit={handleCreateDraft} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-foreground">Project Title</label>
                  <input
                    type="text"
                    required
                    value={projectTitle}
                    onChange={(e) => setProjectTitle(e.target.value)}
                    placeholder="e.g. Distributed Crawling & ETL Pipeline with FastAPI"
                    className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-foreground">
                      Plain-Language Description / Requirements
                    </label>
                    <button
                      type="button"
                      disabled={clarifyingScope}
                      onClick={handleClarifyScope}
                      className="inline-flex items-center gap-1.5 text-xs text-primary font-semibold hover:underline"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      {clarifyingScope ? "Analyzing Scope..." : "Run AI Scope Clarification"}
                    </button>
                  </div>
                  <textarea
                    rows={6}
                    required
                    value={rawDescription}
                    onChange={(e) => setRawDescription(e.target.value)}
                    placeholder="Describe what you need built, key requirements, desired milestones, and constraints..."
                    className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md font-mono text-xs"
                  />
                </div>

                {/* AI Clarification Review Panel */}
                {clarificationResult && (
                  <div className="p-4 rounded-lg bg-primary/5 border border-primary/20 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-primary" />
                        <span className="text-xs font-bold text-foreground">AI Scope Breakdown & Safety Scan</span>
                      </div>
                      {clarificationResult.content_flag ? (
                        <span className="text-xs font-semibold text-destructive flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" /> Flagged: {clarificationResult.content_reason}
                        </span>
                      ) : (
                        <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Safety Check Passed
                        </span>
                      )}
                    </div>

                    <div className="text-xs text-muted-foreground space-y-2">
                      <p className="font-medium text-foreground">{clarificationResult.summary}</p>
                      <div>
                        <span className="font-semibold text-foreground">Key Deliverables:</span>
                        <ul className="list-disc pl-4 mt-1 space-y-0.5">
                          {clarificationResult.deliverables.map((d, i) => (
                            <li key={i}>{d}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <span className="font-semibold text-foreground">Boundaries & Out of Scope:</span>
                        <ul className="list-disc pl-4 mt-1 space-y-0.5">
                          {clarificationResult.boundaries.map((b, i) => (
                            <li key={i}>{b}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {/* Budget & Timeline */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-foreground">Min Budget ($)</label>
                    <input
                      type="number"
                      required
                      min={100}
                      value={budgetMin}
                      onChange={(e) => setBudgetMin(Number(e.target.value))}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-foreground">Max Budget ($)</label>
                    <input
                      type="number"
                      required
                      min={100}
                      value={budgetMax}
                      onChange={(e) => setBudgetMax(Number(e.target.value))}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-foreground">Hiring Deadline (Days)</label>
                    <input
                      type="number"
                      required
                      min={1}
                      max={90}
                      value={hiringDeadlineDays}
                      onChange={(e) => setHiringDeadlineDays(Number(e.target.value))}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-foreground">Rate Structure</label>
                    <select
                      value={ratePeriod}
                      onChange={(e) => setRatePeriod(e.target.value as "hourly" | "fixed" | "monthly_retainer")}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                    >
                      <option value="fixed">Fixed Price Milestone</option>
                      <option value="hourly">Hourly Rate</option>
                      <option value="monthly_retainer">Monthly Retainer</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-foreground">Scope Level</label>
                    <select
                      value={scopeLevel}
                      onChange={(e) => setScopeLevel(e.target.value as "small" | "medium" | "large" | "enterprise")}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                    >
                      <option value="small">Small (1-2 weeks)</option>
                      <option value="medium">Medium (1-2 months)</option>
                      <option value="large">Large (3-6 months)</option>
                      <option value="enterprise">Enterprise</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-foreground">Work Arrangement</label>
                    <select
                      value={workType}
                      onChange={(e) => setWorkType(e.target.value as "remote" | "hybrid" | "onsite")}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-md"
                    >
                      <option value="remote">Fully Remote</option>
                      <option value="hybrid">Hybrid</option>
                      <option value="onsite">On-Site</option>
                    </select>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={saving}
                  className="w-full py-2.5 bg-primary text-primary-foreground font-semibold rounded-md text-sm hover:bg-primary/90 transition flex items-center justify-center gap-2"
                >
                  {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Create Draft Project Brief
                </button>
              </form>
            </div>
          </div>

          {/* Right Sidebar: Policy & Intent Principles */}
          <div className="space-y-4">
            <div className="p-5 bg-card border border-border rounded-xl space-y-3">
              <div className="flex items-center gap-2 text-primary font-semibold text-sm">
                <ShieldCheck className="w-4 h-4" />
                Proof of Hiring Intent Rules
              </div>
              <ul className="text-xs text-muted-foreground space-y-2">
                <li>
                  <strong className="text-foreground">Zero Guesswork:</strong> State clear deliverables and budget basis. Ambiguous listings result in candidate drop-off.
                </li>
                <li>
                  <strong className="text-foreground">No Upfront Fees:</strong> Demanding candidate payments or unpaid speculative work is strictly prohibited and results in immediate delisting.
                </li>
                <li>
                  <strong className="text-foreground">Unverified Payment Status:</strong> Without payment provider verification, projects are labeled unfunded. Native freelancer applications are always free ($0.00).
                </li>
                <li>
                  <strong className="text-foreground">Reconfirmation Requirement:</strong> Briefs require reconfirmation every 14 days to prevent stale jobs.
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Selected Project Details & Intent Management */}
      {activeTab === "details" && selectedProject && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="p-6 bg-card border border-border rounded-xl space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold">{selectedProject.title}</h2>
                    {getStatusBadge(selectedProject.status)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Org: <strong className="text-foreground">{selectedProject.org_name}</strong> • Created{" "}
                    {new Date(selectedProject.created_at).toLocaleDateString()}
                  </p>
                </div>

                {/* Status Transition Actions */}
                <div className="flex flex-wrap items-center gap-2">
                  {selectedProject.status === "draft" && !selectedProject.ai_clarification_approved && (
                    <button
                      onClick={() => handleApproveScope(selectedProject.id)}
                      disabled={saving}
                      className="px-3 py-1.5 text-xs font-semibold bg-primary text-primary-foreground rounded hover:bg-primary/90 transition"
                    >
                      Approve AI Scope
                    </button>
                  )}

                  {selectedProject.status === "draft" && selectedProject.ai_clarification_approved && (
                    <button
                      onClick={() => handleSubmitProject(selectedProject.id)}
                      disabled={saving}
                      className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition"
                    >
                      Publish Project Brief
                    </button>
                  )}

                  {selectedProject.status === "approved_open" && (
                    <>
                      <button
                        onClick={() => handleTransition(selectedProject.id, "shortlist")}
                        className="px-2.5 py-1 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 rounded"
                      >
                        Start Shortlisting
                      </button>
                      <button
                        onClick={() => handleTransition(selectedProject.id, "closed")}
                        className="px-2.5 py-1 text-xs font-medium bg-secondary text-secondary-foreground rounded"
                      >
                        Close Listing
                      </button>
                    </>
                  )}

                  {selectedProject.status === "shortlist" && (
                    <button
                      onClick={() => handleTransition(selectedProject.id, "interviewing")}
                      className="px-2.5 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded"
                    >
                      Move to Interviewing
                    </button>
                  )}

                  {selectedProject.status === "interviewing" && (
                    <button
                      onClick={() => handleTransition(selectedProject.id, "offered_hired")}
                      className="px-2.5 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded"
                    >
                      Mark Hired
                    </button>
                  )}

                  {["closed", "canceled", "expired"].includes(selectedProject.status) && (
                    <button
                      onClick={() => handleTransition(selectedProject.id, "approved_open", "Reopened by client")}
                      className="px-2.5 py-1 text-xs font-medium bg-emerald-100 text-emerald-800 rounded"
                    >
                      Reopen Listing
                    </button>
                  )}
                </div>
              </div>

              {/* Moderation Flag Notice */}
              {selectedProject.review_state === "flagged_for_human_review" && (
                <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 dark:bg-rose-950/40 dark:border-rose-900/40 text-rose-800 dark:text-rose-200 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold">
                    <ShieldAlert className="w-4 h-4 text-rose-600" />
                    Flagged for Human Review
                  </div>
                  <p className="text-xs">
                    Reason: {selectedProject.flagged_reason || "Content policy safety trigger"}. You can submit an appeal with clarification for platform moderators.
                  </p>
                  <button
                    onClick={() => setShowAppealModal(true)}
                    className="px-3 py-1 bg-rose-600 text-white text-xs font-semibold rounded hover:bg-rose-700 transition"
                  >
                    Submit Moderator Appeal
                  </button>
                </div>
              )}

              {/* Scope & Description */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Scope Summary</h3>
                <p className="text-sm bg-secondary/30 p-3 rounded-lg leading-relaxed">
                  {selectedProject.ai_scope_summary || selectedProject.raw_description}
                </p>
              </div>

              {/* Candidates Shortlist Section */}
              <div className="space-y-3 pt-4 border-t border-border">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold flex items-center gap-2">
                    <Users className="w-4 h-4 text-primary" />
                    Shortlisted Candidates ({selectedProject.shortlisted_candidates?.length || 0})
                  </h3>
                  <button
                    onClick={() => setShowShortlistModal(true)}
                    className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Candidate
                  </button>
                </div>

                {(!selectedProject.shortlisted_candidates || selectedProject.shortlisted_candidates.length === 0) ? (
                  <p className="text-xs text-muted-foreground">
                    No candidates shortlisted yet. Shortlist applicants or talent profiles to track their hiring stage.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {selectedProject.shortlisted_candidates.map((c: CandidateShortlistEntry) => (
                      <div
                        key={c.id}
                        className="p-3 bg-card border border-border rounded-lg flex items-center justify-between gap-2"
                      >
                        <div>
                          <div className="text-xs font-semibold text-foreground">Candidate ID: {c.candidate_id}</div>
                          {c.notes && <p className="text-[11px] text-muted-foreground">{c.notes}</p>}
                        </div>

                        <div className="flex items-center gap-2">
                          <select
                            value={c.stage}
                            onChange={(e) => handleUpdateCandidateStage(c.candidate_id, e.target.value as CandidateShortlistEntry["stage"])}
                            className="px-2 py-1 text-xs bg-background border border-border rounded font-medium"
                          >
                            <option value="shortlisted">Shortlisted</option>
                            <option value="interviewing">Interviewing</option>
                            <option value="offered">Offered</option>
                            <option value="hired">Hired</option>
                            <option value="declined">Declined</option>
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Status Audit Trail */}
              {Boolean(selectedProject.status_history?.length) && (
                <div className="space-y-2 pt-4 border-t border-border">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Status Audit History
                  </h3>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                    {(selectedProject.status_history ?? []).map((h) => (
                      <div key={h.id} className="text-[11px] text-muted-foreground flex items-center justify-between bg-secondary/20 px-2.5 py-1.5 rounded">
                        <span>
                          <strong>{h.from_status}</strong> → <strong>{h.to_status}</strong> ({h.action})
                        </span>
                        <span>{new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Sidebar: Hiring Intent Proof Card */}
          <div className="space-y-4">
            <div className="p-5 bg-card border border-border rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Hiring Intent Evidence</span>
                <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Active Proof
                </span>
              </div>

              {selectedProject.hiring_intent_evidence && (
                <div className="space-y-3 text-xs">
                  <div className="flex items-center justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">Org Domain Verification:</span>
                    <span className="font-semibold text-foreground">
                      {selectedProject.hiring_intent_evidence.verified_org ? "Verified" : "Unverified"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">Payment Status:</span>
                    <span className={`font-semibold ${selectedProject.hiring_intent_evidence.payment_verified ? "text-emerald-600" : "text-amber-600"}`}>
                      {selectedProject.hiring_intent_evidence.payment_verified ? "Verified Funded" : "Unverified Payment"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">Freshness Status:</span>
                    <span className="font-semibold text-foreground capitalize">
                      {selectedProject.hiring_intent_evidence.freshness_status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">Application Fee:</span>
                    <span className="font-semibold text-foreground">
                      ${selectedProject.hiring_intent_evidence.native_application_fee.toFixed(2)} (Free)
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">Prior Hires:</span>
                    <span className="font-semibold text-foreground">
                      {selectedProject.hiring_intent_evidence.prior_hires_count} hires
                    </span>
                  </div>
                </div>
              )}

              {selectedProject.status === "approved_open" && (
                <button
                  onClick={() => handleReconfirm(selectedProject.id)}
                  className="w-full py-2 bg-emerald-600 text-white text-xs font-semibold rounded hover:bg-emerald-700 transition flex items-center justify-center gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Reconfirm Hiring Intent Now
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: Clarification Q&A Queue */}
      {activeTab === "clarifications" && selectedProject && (
        <div className="p-6 bg-card border border-border rounded-xl space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-primary" />
                Candidate Clarification Requests
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Answer candidate questions publicly to clarify project scope and reduce repetitive inquiries.
              </p>
            </div>
          </div>

          {clarifications.length === 0 ? (
            <p className="text-xs text-muted-foreground py-8 text-center">
              No questions submitted by candidates for this project yet.
            </p>
          ) : (
            <div className="space-y-4">
              {clarifications.map((q) => (
                <div key={q.id} className="p-4 bg-background border border-border rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-foreground">Question:</span>
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${q.status === "answered" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                      {q.status}
                    </span>
                  </div>
                  <p className="text-sm text-foreground bg-secondary/20 p-2.5 rounded">{q.question}</p>

                  {q.answer ? (
                    <div className="pl-4 border-l-2 border-emerald-500 space-y-1">
                      <span className="text-xs font-semibold text-emerald-600">Your Answer:</span>
                      <p className="text-xs text-muted-foreground">{q.answer}</p>
                    </div>
                  ) : (
                    <div className="space-y-2 pt-2">
                      <textarea
                        rows={2}
                        placeholder="Write your answer (will be publicly visible on listing)..."
                        value={answerDrafts[q.id] || ""}
                        onChange={(e) => setAnswerDrafts({ ...answerDrafts, [q.id]: e.target.value })}
                        className="w-full px-3 py-1.5 text-xs bg-background border border-border rounded"
                      />
                      <button
                        onClick={() => handleAnswerClarification(q.id)}
                        disabled={saving}
                        className="px-3 py-1 bg-primary text-primary-foreground text-xs font-semibold rounded hover:bg-primary/90 transition flex items-center gap-1.5"
                      >
                        <Send className="w-3 h-3" /> Submit Answer
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 5: AI Matches, Applications & Direct Negotiation (Phase 15) */}
      {activeTab === "matching" && selectedProject && (
        <div className="space-y-6">
          {/* Firewall Security Notice */}
          <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <div className="text-xs">
              <span className="font-bold text-foreground">Fair Marketplace Matching Firewall Active:</span>{" "}
              <span className="text-muted-foreground">
                Matches are computed 100% organically based on skill evidence, budget alignment, availability, and newcomer rotation.
                Paid subscription tiers and advertising credits are strictly excluded from ranking algorithms.
              </span>
            </div>
          </div>

          {/* Section A: Matched Talent Shortlist */}
          <div className="p-6 bg-card border border-border rounded-xl space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
              <div>
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  Top Matched Candidates ({matches.length})
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  High-relevance shortlist (top 3–5) with transparent match reasoning and evidence gaps.
                </p>
              </div>

              {/* Request More Candidates */}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Reason to expand shortlist..."
                  value={moreCandidatesReason}
                  onChange={(e) => setMoreCandidatesReason(e.target.value)}
                  className="px-2.5 py-1 text-xs bg-background border border-border rounded w-48"
                />
                <button
                  onClick={handleRequestMoreCandidates}
                  disabled={loadingMatches || !moreCandidatesReason.trim()}
                  className="px-3 py-1 text-xs font-semibold bg-secondary text-secondary-foreground rounded hover:bg-secondary/80 disabled:opacity-50"
                >
                  Request More
                </button>
              </div>
            </div>

            {loadingMatches ? (
              <div className="py-8 text-center text-muted-foreground flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" /> Computing fair matches...
              </div>
            ) : matches.length === 0 ? (
              <div className="py-8 text-center bg-secondary/20 rounded-lg space-y-2">
                <p className="text-sm font-semibold text-foreground">No candidate matches found</p>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  No verified talent profiles currently meet all hard requirements (skills or budget overlap).
                  We never fill shortlists with false matches.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {matches.map((m) => (
                  <div
                    key={m.freelancer_id}
                    className="p-4 bg-background border border-border rounded-lg space-y-3 flex flex-col justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-foreground">
                          {Math.round(m.overall_score * 100)}% Match
                        </span>
                        <div className="flex items-center gap-1.5">
                          {m.is_newcomer && (
                            <span className="px-2 py-0.5 text-[10px] font-bold bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 rounded">
                              Newcomer Boost
                            </span>
                          )}
                          <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 rounded">
                            L{m.verification_level} Verified
                          </span>
                        </div>
                      </div>

                      <h4 className="text-xs font-semibold text-foreground line-clamp-1">{m.headline}</h4>
                      <p className="text-[11px] text-muted-foreground">ID: {m.freelancer_id}</p>

                      {/* Breakdown meters */}
                      <div className="grid grid-cols-2 gap-1 text-[10px] text-muted-foreground bg-secondary/30 p-2 rounded">
                        <div>Skill: <strong>{Math.round(m.skill_score * 100)}%</strong></div>
                        <div>Budget: <strong>{Math.round(m.budget_score * 100)}%</strong></div>
                        <div>Availability: <strong>{Math.round(m.availability_score * 100)}%</strong></div>
                        <div>Pref: <strong>{Math.round(m.work_pref_score * 100)}%</strong></div>
                      </div>

                      {/* Match reasons */}
                      {m.reasons?.length > 0 && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold uppercase text-muted-foreground">Match Reasons:</span>
                          <ul className="text-[11px] text-emerald-700 dark:text-emerald-400 space-y-0.5 list-disc pl-3">
                            {m.reasons.slice(0, 2).map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Gaps / missing info */}
                      {m.missing_information?.length > 0 && (
                        <div className="space-y-0.5">
                          <span className="text-[10px] font-bold uppercase text-muted-foreground">Information Gaps:</span>
                          <p className="text-[10px] text-amber-700 dark:text-amber-400">
                            {m.missing_information.join(", ")}
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 pt-2 border-t border-border">
                      <button
                        onClick={() => handleInviteTalent(m.freelancer_id)}
                        disabled={saving}
                        className="flex-1 py-1 text-xs font-semibold bg-primary text-primary-foreground rounded hover:bg-primary/90 transition text-center"
                      >
                        Invite
                      </button>
                      <button
                        onClick={() => handleStartDiscussion(m.freelancer_id)}
                        disabled={saving}
                        className="px-2.5 py-1 text-xs font-semibold bg-secondary text-secondary-foreground rounded hover:bg-secondary/80"
                      >
                        Chat
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section B: Received Freelancer Applications */}
          <div className="p-6 bg-card border border-border rounded-xl space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-4">
              <div>
                <h3 className="text-base font-bold flex items-center gap-2">
                  <FileText className="w-4 h-4 text-primary" />
                  Received Freelancer Applications ({applications.length})
                </h3>
                <p className="text-xs text-muted-foreground">
                  Free expressions of interest with structured pitches and past artifacts (no unpaid custom deliverables).
                </p>
              </div>
            </div>

            {applications.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                No freelancer applications received yet for this project.
              </p>
            ) : (
              <div className="space-y-3">
                {applications.map((app) => (
                  <div key={app.id} className="p-4 bg-background border border-border rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-foreground">Candidate: {app.freelancer_id}</span>
                        <span className="px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 rounded">
                          {app.status}
                        </span>
                      </div>
                      <span className="text-xs font-bold text-foreground">
                        Proposed: ${app.proposed_rate} ({app.proposed_rate_period}) • ~{app.estimated_days} days
                      </span>
                    </div>

                    <p className="text-xs text-foreground bg-secondary/20 p-2.5 rounded whitespace-pre-line">
                      {app.structured_pitch}
                    </p>

                    <div className="flex items-center justify-between pt-2">
                      <button
                        onClick={() => handleStartDiscussion(app.freelancer_id, app.id)}
                        className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                      >
                        <MessageSquare className="w-3.5 h-3.5" /> Open Direct Discussion
                      </button>

                      <button
                        onClick={() => {
                          setOfferTargetAppId(app.id);
                          setOfferAmountInput(app.proposed_rate || selectedProject.budget_min || 3000);
                          setShowOfferModal(true);
                        }}
                        className="px-3 py-1 text-xs font-semibold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition"
                      >
                        Extend Formal Offer
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section C: Direct Discussion Thread */}
          {activeConvId && (
            <div className="p-6 bg-card border border-border rounded-xl space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-primary" />
                  Direct Negotiation Thread (Conversation: {activeConvId})
                </h3>
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Authenticated Participants
                </span>
              </div>

              {/* Pre-offer Contact Details Protection Notice */}
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-800 dark:text-amber-200">
                <strong>Platform Safety Notice:</strong> Raw phone numbers and emails are masked in messages prior to formal offer acceptance to prevent off-platform bypass scams.
              </div>

              <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
                {messages.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-4 text-center">No messages yet. Send a greeting to start negotiation.</p>
                ) : (
                  messages.map((m) => (
                    <div
                      key={m.id}
                      className={`p-3 rounded-lg text-xs space-y-1 ${
                        m.sender_role === "client"
                          ? "bg-primary/10 ml-8 border border-primary/20"
                          : "bg-secondary/30 mr-8 border border-border"
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="font-semibold capitalize">{m.sender_role} ({m.sender_id})</span>
                        <span>{new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                      <p className="text-foreground">{m.content}</p>
                    </div>
                  ))
                )}
              </div>

              <div className="flex gap-2 pt-2">
                <input
                  type="text"
                  placeholder="Type a message (rates, milestones, scope clarifications)..."
                  value={messageContent}
                  onChange={(e) => setMessageContent(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                  className="flex-1 px-3 py-1.5 text-xs bg-background border border-border rounded"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={saving || !messageContent.trim()}
                  className="px-4 py-1.5 bg-primary text-primary-foreground text-xs font-semibold rounded hover:bg-primary/90 flex items-center gap-1.5"
                >
                  <Send className="w-3 h-3" /> Send
                </button>
              </div>
            </div>
          )}

          {/* Section D: Negotiation Assistant & Project Offers */}
          <div className="p-6 bg-card border border-border rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
              <div>
                <h3 className="text-base font-bold flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary" />
                  Bilateral Negotiation & Formal Offers ({offers.length})
                </h3>
                <p className="text-xs text-muted-foreground">
                  Draft terms with AI assistance, counter-propose milestones, and finalize with concurrency locks.
                </p>
              </div>

              <button
                onClick={handleDraftNegotiation}
                disabled={draftingTerms}
                className="px-3 py-1.5 text-xs font-semibold bg-secondary text-secondary-foreground rounded hover:bg-secondary/80 flex items-center gap-1.5"
              >
                {draftingTerms ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                Draft Terms with Assistant
              </button>
            </div>

            {draftedTerms && (
              <div className="p-4 bg-background border border-border rounded-lg space-y-2 text-xs">
                <span className="font-bold text-foreground">AI Drafted Scope & Milestones:</span>
                <p className="text-muted-foreground">{draftedTerms.scope_summary}</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                  {draftedTerms.milestones?.map((ms, i) => (
                    <div key={i} className="p-2 bg-secondary/30 rounded flex justify-between">
                      <span>{ms.title} (due day {ms.due_days})</span>
                      <strong>${ms.amount}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {offers.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                No formal offers created for this project yet.
              </p>
            ) : (
              <div className="space-y-3">
                {offers.map((off) => (
                  <div key={off.id} className="p-4 bg-background border border-border rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-foreground">
                          Offer v{off.version} ({off.contract_type})
                        </span>
                        <span
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                            off.status === "accepted"
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                              : off.status === "superseded"
                              ? "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300"
                              : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                          }`}
                        >
                          {off.status}
                        </span>
                      </div>
                      <span className="text-xs font-bold text-foreground">
                        ${off.agreed_amount.toLocaleString()} {off.currency}
                      </span>
                    </div>

                    <p className="text-xs text-muted-foreground">{off.scope_summary}</p>

                    {off.milestones?.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 text-[11px]">
                        {off.milestones.map((m, idx) => (
                          <div key={idx} className="p-1.5 bg-secondary/20 rounded flex justify-between">
                            <span>{m.title}</span>
                            <strong>${m.amount}</strong>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t border-border">
                      <span>Deadline: {new Date(off.decision_deadline).toLocaleDateString()}</span>
                      {off.status === "pending_review" && off.creator_role === "freelancer" && (
                        <button
                          onClick={() => handleAcceptOfferClient(off.id)}
                          disabled={saving}
                          className="px-3 py-1 bg-emerald-600 text-white font-semibold rounded hover:bg-emerald-700 transition"
                        >
                          Accept Counter-Offer
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Extend Formal Offer Modal */}
      {showOfferModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-base font-bold flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-emerald-600" />
              Extend Formal Project Offer
            </h3>
            <p className="text-xs text-muted-foreground">
              Define the agreed compensation and milestone schedule. Once accepted by candidate, the project position is filled.
            </p>
            <form onSubmit={handleCreateOfferSubmit} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Agreed Amount (USD)</label>
                <input
                  type="number"
                  required
                  value={offerAmountInput}
                  onChange={(e) => setOfferAmountInput(Number(e.target.value))}
                  className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Scope Summary</label>
                <textarea
                  rows={2}
                  required
                  value={offerScopeInput}
                  onChange={(e) => setOfferScopeInput(e.target.value)}
                  placeholder="Summary of agreed deliverables and expectations..."
                  className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOfferModal(false)}
                  className="px-3 py-1.5 text-xs font-semibold bg-secondary rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 text-white rounded hover:bg-emerald-700"
                >
                  Submit Formal Offer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Candidate Modal */}
      {showShortlistModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold">Shortlist Candidate</h3>
            <form onSubmit={handleAddCandidate} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Candidate Profile / User ID</label>
                <input
                  type="text"
                  required
                  value={candidateIdToAdd}
                  onChange={(e) => setCandidateIdToAdd(e.target.value)}
                  placeholder="e.g. usr-cand-123"
                  className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Notes (Optional)</label>
                <textarea
                  rows={2}
                  value={candidateNotesToAdd}
                  onChange={(e) => setCandidateNotesToAdd(e.target.value)}
                  placeholder="Notes about portfolio, rates, or fit..."
                  className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowShortlistModal(false)}
                  className="px-3 py-1.5 text-xs font-semibold bg-secondary rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-3 py-1.5 text-xs font-semibold bg-primary text-primary-foreground rounded hover:bg-primary/90"
                >
                  Add Candidate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Moderation Appeal Modal */}
      {showAppealModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-base font-bold flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-rose-600" />
              Appeal Moderation Flag
            </h3>
            <p className="text-xs text-muted-foreground">
              Provide context to human reviewers regarding your project requirements, scope, or basis.
            </p>
            <form onSubmit={handleAppealSubmit} className="space-y-3">
              <textarea
                rows={4}
                required
                value={appealDetails}
                onChange={(e) => setAppealDetails(e.target.value)}
                placeholder="Explain the context and why this project brief complies with marketplace guidelines..."
                className="w-full px-3 py-2 text-sm bg-background border border-border rounded"
              />
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAppealModal(false)}
                  className="px-3 py-1.5 text-xs font-semibold bg-secondary rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-3 py-1.5 text-xs font-semibold bg-rose-600 text-white rounded hover:bg-rose-700"
                >
                  Submit Appeal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
