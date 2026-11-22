"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  DollarSign,
  FileText,
  HelpCircle,
  Layers,
  MessageSquare,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  acceptProjectOffer,
  counterProposeOffer,
  declineProjectOffer,
  getProjectClarifications,
  getProjectDetails,
  getProjectOffers,
  listFreelancerApplications,
  submitExpressionOfInterest,
  submitProjectClarification,
  withdrawApplication,
  type ProjectApplicationItem,
  type ProjectClarificationItem,
  type ProjectOfferItem,
} from "@/lib/api";

export default function NativeProjectDetailPage() {
  const params = useParams();
  const projectId = params?.id as string;

  const [project, setProject] = useState<any | null>(null);
  const [clarifications, setClarifications] = useState<ProjectClarificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [conflictWarning, setConflictWarning] = useState<string | null>(null);

  // New question form
  const [questionText, setQuestionText] = useState("");

  // Phase 15: Freelancer application & offer negotiation state
  const [myApplications, setMyApplications] = useState<ProjectApplicationItem[]>([]);
  const [projectOffers, setProjectOffers] = useState<ProjectOfferItem[]>([]);
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [pitchInput, setPitchInput] = useState("");
  const [proposedRate, setProposedRate] = useState<number>(85);
  const [proposedRatePeriod, setProposedRatePeriod] = useState<"hourly" | "fixed">("hourly");
  const [estimatedDays, setEstimatedDays] = useState<number>(14);
  const [artifactsInput, setArtifactsInput] = useState("");

  // Counter offer state
  const [showCounterModal, setShowCounterModal] = useState(false);
  const [counterTargetOfferId, setCounterTargetOfferId] = useState("");
  const [counterAmount, setCounterAmount] = useState<number>(3500);
  const [counterScope, setCounterScope] = useState("");

  useEffect(() => {
    if (projectId) {
      loadProjectData(projectId);
    }
  }, [projectId]);

  async function loadProjectData(id: string) {
    try {
      setLoading(true);
      setError(null);
      const [projRes, clarRes, appRes, offersRes] = await Promise.all([
        getProjectDetails(id),
        getProjectClarifications(id, false).catch(() => ({ clarifications: [] })),
        listFreelancerApplications().catch(() => ({ applications: [] })),
        getProjectOffers(id).catch(() => ({ offers: [] })),
      ]);
      setProject(projRes.project);
      setClarifications(clarRes.clarifications || []);
      // Filter applications for this project
      const thisProjectApps = (appRes.applications || []).filter(
        (a: ProjectApplicationItem) => a.project_id === id
      );
      setMyApplications(thisProjectApps);
      setProjectOffers(offersRes.offers || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load project brief or project is not published.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitApplication(e: React.FormEvent) {
    e.preventDefault();
    if (!pitchInput.trim() || pitchInput.trim().length < 20) {
      setError("Please provide a structured pitch of at least 20 characters.");
      return;
    }
    try {
      setSaving(true);
      setError(null);
      const artifacts = artifactsInput
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      await submitExpressionOfInterest(projectId, {
        structured_pitch: pitchInput.trim(),
        relevant_artifacts: artifacts,
        proposed_rate: proposedRate,
        proposed_rate_period: proposedRatePeriod,
        estimated_days: estimatedDays,
      });

      setShowApplyModal(false);
      setSuccess("Expression of interest submitted successfully at $0.00 platform fee!");
      await loadProjectData(projectId);
    } catch (err: any) {
      setError(err?.message || "Failed to submit application");
    } finally {
      setSaving(false);
    }
  }

  async function handleWithdraw(applicationId: string) {
    try {
      setSaving(true);
      setError(null);
      await withdrawApplication(applicationId);
      setSuccess("Expression of interest gracefully withdrawn.");
      await loadProjectData(projectId);
    } catch (err: any) {
      setError(err?.message || "Failed to withdraw application");
    } finally {
      setSaving(false);
    }
  }

  async function handleAcceptOfferFreelancer(offerId: string) {
    try {
      setSaving(true);
      setError(null);
      setConflictWarning(null);
      await acceptProjectOffer(offerId);
      setSuccess("Offer accepted! Contract established.");
      await loadProjectData(projectId);
    } catch (err: any) {
      if (err?.message?.includes("Conflict") || err?.message?.includes("409") || err?.message?.includes("superseded")) {
        setConflictWarning("Concurrency Conflict (409): This project position has already been filled or this offer has been superseded.");
      } else {
        setError(err?.message || "Failed to accept offer");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleCounterOfferSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!counterTargetOfferId) return;
    try {
      setSaving(true);
      setError(null);
      await counterProposeOffer(counterTargetOfferId, {
        counter_amount: counterAmount,
        scope_summary: counterScope || "Revised milestones and deliverable schedule.",
      });
      setShowCounterModal(false);
      setSuccess("Counter-proposal submitted for client review.");
      await loadProjectData(projectId);
    } catch (err: any) {
      setError(err?.message || "Failed to submit counter-proposal");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmitQuestion(e: React.FormEvent) {
    e.preventDefault();
    if (!questionText.trim() || questionText.length < 10) {
      setError("Clarification question must be at least 10 characters.");
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const res = await submitProjectClarification(projectId, {
        question: questionText.trim(),
      });
      setSuccess("Your question was submitted to the client! Once answered, it will appear publicly below.");
      setQuestionText("");
      // Reload clarifications
      const clarRes = await getProjectClarifications(projectId, false);
      setClarifications(clarRes.clarifications || []);
    } catch (err: any) {
      setError(err?.message || "Failed to submit clarification question.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="container max-w-5xl mx-auto px-4 py-16 text-center text-muted-foreground">
        Loading project brief...
      </div>
    );
  }

  if (error && !project) {
    return (
      <div className="container max-w-5xl mx-auto px-4 py-16 space-y-4 text-center">
        <AlertCircle className="w-12 h-12 text-destructive mx-auto" />
        <h2 className="text-xl font-bold">Project Not Available</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">{error}</p>
        <Link
          href="/freelance-jobs"
          className="inline-block px-4 py-2 bg-primary text-primary-foreground text-sm font-semibold rounded"
        >
          Browse Opportunities
        </Link>
      </div>
    );
  }

  const intent = project?.hiring_intent_evidence;

  return (
    <div className="container max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between">
          <span className="text-sm font-medium">{error}</span>
          <button onClick={() => setError(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

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

      {success && (
        <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 flex items-center justify-between">
          <span className="text-sm font-medium">{success}</span>
          <button onClick={() => setSuccess(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Project Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 bg-card border border-border rounded-xl space-y-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-primary/10 text-primary uppercase tracking-wider">
                  Native Project
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  {project.status === "approved_open" ? "Open for Proposals" : project.status}
                </span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight">{project.title}</h1>
              <p className="text-xs text-muted-foreground">
                Posted by <strong className="text-foreground">{project.org_name}</strong> • Created{" "}
                {new Date(project.created_at).toLocaleDateString()}
              </p>
            </div>

            {/* Compensation & Timeline Row */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 bg-secondary/20 rounded-lg">
              <div>
                <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Budget</span>
                <div className="text-sm font-bold text-foreground">
                  ${project.budget_min.toLocaleString()} - ${project.budget_max.toLocaleString()} {project.currency}
                </div>
                <span className="text-[10px] text-muted-foreground">{project.rate_period}</span>
              </div>

              <div>
                <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Hiring Deadline</span>
                <div className="text-sm font-bold text-foreground">
                  {new Date(project.hiring_deadline).toLocaleDateString()}
                </div>
                <span className="text-[10px] text-muted-foreground">Decision Target</span>
              </div>

              <div>
                <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Arrangement</span>
                <div className="text-sm font-bold text-foreground capitalize">{project.work_type}</div>
                <span className="text-[10px] text-muted-foreground">{project.commitment_type}</span>
              </div>
            </div>

            {/* Scope Summary */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Scope & Requirements
              </h3>
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
                {project.ai_scope_summary || project.raw_description}
              </p>
            </div>

            {/* Acceptance Criteria */}
            {project.acceptance_criteria && project.acceptance_criteria.length > 0 && (
              <div className="space-y-2 pt-3 border-t border-border">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Acceptance Criteria
                </h3>
                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-1">
                  {project.acceptance_criteria.map((c: string, i: number) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Skills Required */}
            {project.skills_required && project.skills_required.length > 0 && (
              <div className="space-y-2 pt-3 border-t border-border">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Skills Required
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {project.skills_required.map((s: string, i: number) => (
                    <span
                      key={i}
                      className="text-xs px-2.5 py-1 bg-secondary text-secondary-foreground font-medium rounded"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Clarification Q&A Section */}
          <div className="p-6 bg-card border border-border rounded-xl space-y-5">
            <div>
              <h3 className="text-base font-bold flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-primary" />
                Public Clarification Q&A
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Have a question about scope or expectations? Submit a clarification request. Answered inquiries are posted publicly to maintain fairness.
              </p>
            </div>

            {/* Answered Clarifications */}
            {clarifications.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-3">
                No public clarification questions answered yet.
              </p>
            ) : (
              <div className="space-y-3">
                {clarifications.map((q) => (
                  <div key={q.id} className="p-3 bg-secondary/20 rounded-lg space-y-1.5 text-xs">
                    <div className="font-semibold text-foreground">Q: {q.question}</div>
                    {q.answer && (
                      <div className="text-muted-foreground pl-3 border-l-2 border-primary">
                        <strong>Client Answer:</strong> {q.answer}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Question Submission Form */}
            <form onSubmit={handleSubmitQuestion} className="space-y-3 pt-4 border-t border-border">
              <label className="text-xs font-semibold text-foreground block">
                Ask a Question (Max 3 inquiries per 24 hours to prevent spam)
              </label>
              <textarea
                rows={3}
                required
                value={questionText}
                onChange={(e) => setQuestionText(e.target.value)}
                placeholder="Ask about project scope, tech stack requirements, or deliverables..."
                className="w-full px-3 py-2 text-xs bg-background border border-border rounded"
              />
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-primary text-primary-foreground text-xs font-semibold rounded hover:bg-primary/90 transition flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" /> Submit Question
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Actions, Mutual Interest & Proof of Hiring Intent */}
        <div className="space-y-4">
          {/* Mutual Interest & Application Card (100% Free / $0.00 Platform Fee) */}
          <div className="p-5 bg-card border border-border rounded-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Mutual Interest Application
              </h3>
              <span className="text-xs font-bold text-emerald-600 bg-emerald-100 dark:bg-emerald-950 px-2 py-0.5 rounded">
                $0.00 Free
              </span>
            </div>

            {myApplications.length === 0 ? (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Express interest with your structured pitch and verified portfolio artifacts. No connects, bidding wars, or pay-to-apply fees.
                </p>
                <button
                  onClick={() => setShowApplyModal(true)}
                  disabled={saving || project.status === "offered_hired" || project.status === "closed"}
                  className="w-full py-2.5 bg-primary text-primary-foreground text-xs font-bold rounded-lg hover:bg-primary/90 transition flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" /> Express Interest ($0.00 Fee)
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {myApplications.map((app) => (
                  <div key={app.id} className="p-3 bg-secondary/30 rounded-lg space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-foreground">Your Expression of Interest</span>
                      <span className="px-2 py-0.5 text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 rounded uppercase">
                        {app.status}
                      </span>
                    </div>
                    <p className="text-muted-foreground line-clamp-2">{app.structured_pitch}</p>
                    <div className="text-[11px] text-muted-foreground flex justify-between">
                      <span>Rate: ${app.proposed_rate}/{app.proposed_rate_period}</span>
                      <span>~{app.estimated_days} days</span>
                    </div>

                    {(app.status === "submitted" || app.status === "shortlisted") && (
                      <button
                        onClick={() => handleWithdraw(app.id)}
                        disabled={saving}
                        className="text-[11px] text-destructive hover:underline font-semibold block pt-1"
                      >
                        Withdraw Application
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Bilateral Offers Card */}
          {projectOffers.length > 0 && (
            <div className="p-5 bg-card border border-border rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Contract Offers ({projectOffers.length})
                </h3>
                <span className="text-xs font-semibold text-primary flex items-center gap-1">
                  <DollarSign className="w-3.5 h-3.5" /> Bilateral
                </span>
              </div>

              <div className="space-y-3">
                {projectOffers.map((off) => (
                  <div key={off.id} className="p-3.5 bg-background border border-border rounded-lg space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-foreground">Offer v{off.version}</span>
                      <span
                        className={`px-2 py-0.5 text-[10px] font-bold rounded ${
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

                    <div className="font-bold text-foreground text-sm">
                      ${off.agreed_amount.toLocaleString()} {off.currency}
                    </div>

                    <p className="text-muted-foreground text-[11px]">{off.scope_summary}</p>

                    {off.status === "pending_review" && off.creator_role === "client" && (
                      <div className="flex items-center gap-2 pt-2 border-t border-border">
                        <button
                          onClick={() => handleAcceptOfferFreelancer(off.id)}
                          disabled={saving}
                          className="flex-1 py-1 bg-emerald-600 text-white font-semibold rounded hover:bg-emerald-700 transition text-center"
                        >
                          Accept Offer
                        </button>
                        <button
                          onClick={() => {
                            setCounterTargetOfferId(off.id);
                            setCounterAmount(off.agreed_amount);
                            setCounterScope(off.scope_summary);
                            setShowCounterModal(true);
                          }}
                          disabled={saving}
                          className="px-2.5 py-1 bg-secondary text-secondary-foreground font-semibold rounded hover:bg-secondary/80"
                        >
                          Counter
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Proof of Hiring Intent Card */}
          <div className="p-5 bg-card border border-border rounded-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Proof of Hiring Intent
              </h3>
              <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                <ShieldCheck className="w-4 h-4" /> Evidence
              </span>
            </div>

            {intent ? (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Org Domain Status:</span>
                  <span className={`font-semibold ${intent.verified_org ? "text-emerald-600" : "text-muted-foreground"}`}>
                    {intent.verified_org ? "Verified Domain" : "Unverified"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Payment Verification:</span>
                  <span
                    className={`font-semibold ${
                      intent.payment_verified ? "text-emerald-600" : "text-amber-600"
                    }`}
                  >
                    {intent.payment_verified ? "Verified Funded" : "Unverified / Not Funded"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Decision Deadline:</span>
                  <span className="font-semibold text-foreground">
                    {new Date(intent.decision_deadline).toLocaleDateString()}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Listing Freshness:</span>
                  <span className="font-semibold text-foreground capitalize">
                    {intent.freshness_status}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Prior Platform Hires:</span>
                  <span className="font-semibold text-foreground">
                    {intent.prior_hires_count > 0 ? `${intent.prior_hires_count} hires` : "First listing"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Application Fee:</span>
                  <span className="font-bold text-emerald-600">
                    ${intent.native_application_fee.toFixed(2)} (100% Free)
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">Intent evidence not available.</p>
            )}

            <div className="p-3 bg-secondary/30 rounded-lg text-[11px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Candidate Guarantee:</strong> Native project applications carry $0.00 platform fee. Clients are never permitted to request upfront payment or speculative unpaid tests.
            </div>
          </div>
        </div>
      </div>

      {/* Express Interest Modal */}
      {showApplyModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-base font-bold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              Express Interest ($0.00 Platform Fee)
            </h3>
            <p className="text-xs text-muted-foreground">
              Provide a brief structured response and link relevant portfolio artifacts. No unpaid custom tests are allowed.
            </p>

            <form onSubmit={handleSubmitApplication} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Structured Pitch (Min 20 characters)</label>
                <textarea
                  rows={4}
                  required
                  value={pitchInput}
                  onChange={(e) => setPitchInput(e.target.value)}
                  placeholder="Outline your relevant background, understanding of the project scope, and approach..."
                  className="w-full px-3 py-2 text-xs bg-background border border-border rounded"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-foreground">Proposed Rate ($)</label>
                  <input
                    type="number"
                    required
                    value={proposedRate}
                    onChange={(e) => setProposedRate(Number(e.target.value))}
                    className="w-full px-3 py-1.5 text-xs bg-background border border-border rounded"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-foreground">Rate Period</label>
                  <select
                    value={proposedRatePeriod}
                    onChange={(e: any) => setProposedRatePeriod(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs bg-background border border-border rounded"
                  >
                    <option value="hourly">Hourly ($/hr)</option>
                    <option value="fixed">Fixed Price</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Estimated Delivery Days</label>
                <input
                  type="number"
                  required
                  value={estimatedDays}
                  onChange={(e) => setEstimatedDays(Number(e.target.value))}
                  className="w-full px-3 py-1.5 text-xs bg-background border border-border rounded"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Portfolio Artifact URLs (Optional, one per line)</label>
                <textarea
                  rows={2}
                  value={artifactsInput}
                  onChange={(e) => setArtifactsInput(e.target.value)}
                  placeholder="https://github.com/my-org/project&#10;https://demo.myproject.io"
                  className="w-full px-3 py-1.5 text-xs bg-background border border-border rounded"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowApplyModal(false)}
                  className="px-3 py-1.5 text-xs font-semibold bg-secondary rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-1.5 text-xs font-semibold bg-primary text-primary-foreground rounded hover:bg-primary/90"
                >
                  Submit Expression ($0.00)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Counter Propose Offer Modal */}
      {showCounterModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-primary" />
              Counter-Propose Offer
            </h3>
            <form onSubmit={handleCounterOfferSubmit} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Counter Amount (USD)</label>
                <input
                  type="number"
                  required
                  value={counterAmount}
                  onChange={(e) => setCounterAmount(Number(e.target.value))}
                  className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">Revised Scope / Terms</label>
                <textarea
                  rows={3}
                  required
                  value={counterScope}
                  onChange={(e) => setCounterScope(e.target.value)}
                  placeholder="Explain adjusted milestones, timeline or deliverable scope..."
                  className="w-full px-3 py-1.5 text-xs bg-background border border-border rounded"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCounterModal(false)}
                  className="px-3 py-1.5 text-xs font-semibold bg-secondary rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-3 py-1.5 text-xs font-semibold bg-primary text-primary-foreground rounded hover:bg-primary/90"
                >
                  Submit Counter
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
