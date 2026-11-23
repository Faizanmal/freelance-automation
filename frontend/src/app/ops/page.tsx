"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  adminResolveProjectModeration,
  adminResolveSupportCase,
  adminResolveDispute,
  adminGetDisputeDetails,
  adminReviewListingReport,
  adminSupportQueue,
  me,
  opsModerationQueues,
  opsSourcePolicies,
  opsSetSourceDisabled,
  opsMarketplaceMetrics,
  opsProductLearning,
  opsExpireDueClaims,
  opsReviewVerificationClaim,
  opsGetVerificationClaim,
  opsGetMarketplaceReport,
  opsResolveMarketplaceReport,
  opsWaitlistSummary,
  opsAudit,
  type AdminSourcePolicy,
  type User,
} from "@/lib/api";

type QueueSnapshot = Awaited<ReturnType<typeof opsModerationQueues>>;
type SupportSnapshot = Awaited<ReturnType<typeof adminSupportQueue>>;
type WaitlistSnapshot = Awaited<ReturnType<typeof opsWaitlistSummary>>;
type AuditSnapshot = Awaited<ReturnType<typeof opsAudit>>;
type DisputeSnapshot = Awaited<ReturnType<typeof adminGetDisputeDetails>>;
type MetricsSnapshot = Awaited<ReturnType<typeof opsMarketplaceMetrics>>;
type ProductLearningSnapshot = Awaited<ReturnType<typeof opsProductLearning>>;
type ClaimSnapshot = Awaited<ReturnType<typeof opsGetVerificationClaim>>;
type ReportSnapshot = Awaited<ReturnType<typeof opsGetMarketplaceReport>>;

export default function OperationsPage() {
  const router = useRouter();
  const [actor, setActor] = useState<User | null>(null);
  const [moderation, setModeration] = useState<QueueSnapshot | null>(null);
  const [support, setSupport] = useState<SupportSnapshot | null>(null);
  const [sources, setSources] = useState<AdminSourcePolicy[]>([]);
  const [waitlist, setWaitlist] = useState<WaitlistSnapshot | null>(null);
  const [audit, setAudit] = useState<AuditSnapshot | null>(null);
  const [expiryResult, setExpiryResult] = useState<number | null>(null);
  const [claimDetails, setClaimDetails] = useState<Record<string, ClaimSnapshot>>({});
  const [reportDetails, setReportDetails] = useState<Record<string, ReportSnapshot>>({});
  const [disputeDetails, setDisputeDetails] = useState<Record<string, DisputeSnapshot>>({});
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [productLearning, setProductLearning] = useState<ProductLearningSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async (user: User) => {
    const isModerator = user.is_superuser || user.account_role === "marketplace_moderator";
    const isSupport = user.is_superuser || user.account_role === "support_agent";
    const isSourceOperator = user.is_superuser || user.account_role === "source_operator";
    const canReview = isModerator || isSupport;
    const [mod, help, sourceData, waiting, auditData, measured, learning] = await Promise.all([
      isModerator ? opsModerationQueues(50) : Promise.resolve(null),
      isSupport ? adminSupportQueue(50) : Promise.resolve(null),
      isSourceOperator ? opsSourcePolicies() : Promise.resolve(null),
      canReview ? opsWaitlistSummary() : Promise.resolve(null),
      isModerator ? opsAudit(30) : Promise.resolve(null),
      isModerator ? opsMarketplaceMetrics() : Promise.resolve(null),
      isModerator ? opsProductLearning() : Promise.resolve(null),
    ]);
    setModeration(mod);
    setSupport(help);
    setSources(sourceData?.sources || []);
    setWaitlist(waiting);
    setAudit(auditData);
    setMetrics(measured);
    setProductLearning(learning);
  };

  useEffect(() => {
    me().then(async (user) => {
      if (!user.is_superuser && !["marketplace_moderator", "support_agent", "source_operator"].includes(user.account_role || "")) {
        router.push("/");
        return;
      }
      setActor(user);
      await load(user);
    }).catch(() => router.push("/auth"));
  }, [router]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Operation failed"); }
    finally { setBusy(false); }
  };

  const decideListing = (id: number, outcome: string) => {
    const notes = window.prompt("Enter a review reason (at least 10 characters):")?.trim();
    if (!notes || notes.length < 10) { setError("A review reason is required."); return; }
    void run(async () => {
      await adminReviewListingReport(id, { outcome, notes, status: "resolved" });
      if (actor) await load(actor);
    });
  };

  const decideProject = (id: string, decision: "approved" | "rejected") => {
    const notes = window.prompt("Enter a moderation reason (at least 10 characters):")?.trim();
    if (!notes || notes.length < 10) { setError("A moderation reason is required."); return; }
    void run(async () => {
      await adminResolveProjectModeration(id, decision, notes);
      if (actor) await load(actor);
    });
  };

  const resolveCase = (id: string) => {
    const note = window.prompt("Enter the support resolution (at least 10 characters):")?.trim();
    if (!note || note.length < 10) { setError("A resolution note is required."); return; }
    void run(async () => {
      await adminResolveSupportCase(id, note);
      if (actor) await load(actor);
    });
  };

  const resolveDispute = (id: string, outcome: "resolved_client" | "resolved_freelancer" | "no_action") => {
    const note = window.prompt("Record a human review outcome and reason (at least 10 characters):")?.trim();
    if (!note || note.length < 10) { setError("A documented human outcome is required."); return; }
    void run(async () => {
      await adminResolveDispute(id, outcome, note);
      if (actor) await load(actor);
    });
  };

  const showDispute = (id: string) => {
    void run(async () => {
      const details = await adminGetDisputeDetails(id);
      setDisputeDetails((current) => ({ ...current, [id]: details }));
    });
  };

  const toggleSource = (source: AdminSourcePolicy) => {
    const reason = window.prompt(`Reason to ${source.operator_disabled ? "enable" : "disable"} ${source.display_name}:`)?.trim();
    if (!reason || reason.length < 10) { setError("A reason of at least 10 characters is required."); return; }
    void run(async () => {
      await opsSetSourceDisabled(source.key, !source.operator_disabled, reason);
      if (actor) await load(actor);
    });
  };

  const expireClaims = () => {
    const reason = window.prompt("Reason for processing expired verification claims:")?.trim();
    if (!reason || reason.length < 10) { setError("A reason of at least 10 characters is required."); return; }
    void run(async () => {
      const result = await opsExpireDueClaims(reason);
      setExpiryResult(result.expired_count);
      if (actor) await load(actor);
    });
  };

  const reviewClaim = (claimId: string, status: "verified" | "rejected") => {
    const reason = window.prompt("Record the verification review basis (at least 10 characters):")?.trim();
    if (!reason || reason.length < 10) { setError("A verification review reason is required."); return; }
    void run(async () => {
      await opsReviewVerificationClaim(claimId, status, reason);
      if (actor) await load(actor);
    });
  };

  const showClaimEvidence = (claimId: string) => {
    void run(async () => {
      const details = await opsGetVerificationClaim(claimId);
      setClaimDetails((current) => ({ ...current, [claimId]: details }));
    });
  };

  const showReport = (reportId: string) => {
    void run(async () => {
      const details = await opsGetMarketplaceReport(reportId);
      setReportDetails((current) => ({ ...current, [reportId]: details }));
    });
  };

  const decideMarketplaceReport = (reportId: string, status: "resolved" | "dismissed") => {
    const note = window.prompt("Record the human review outcome (at least 10 characters):")?.trim();
    if (!note || note.length < 10) { setError("A review outcome and reason are required."); return; }
    void run(async () => {
      await opsResolveMarketplaceReport(reportId, status, note);
      if (actor) await load(actor);
    });
  };

  if (!actor) return <p className="mx-auto mt-20 text-center text-[var(--mute)]">Loading operations console…</p>;
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-5 py-12">
      <header>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>Marketplace operations</h1>
        <p className="mt-2 text-sm text-[var(--fog)]">Queues are separated by assigned role. Privileged decisions require a recorded reason.</p>
        <Badge variant="outline" className="mt-3">{actor.is_superuser ? "Superuser" : actor.account_role}</Badge>
      </header>
      {error && <p role="alert" className="text-sm text-[var(--ember)]">{error}</p>}

      {moderation && <section className="space-y-3">
        <h2 className="text-2xl">Moderation</h2>
        <Card className="space-y-4 p-4">
          <h3 className="font-semibold">Native projects ({moderation.projects.length})</h3>
          {moderation.projects.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3 text-sm">
            <span>Project {item.project_id} · {item.reason} · {item.status}{item.appeal_summary && <span className="block text-xs text-[var(--mute)]">Appeal: {item.appeal_summary}</span>}</span>
            <span className="flex gap-2"><Button disabled={busy} variant="outline" onClick={() => decideProject(item.id, "approved")}>Approve</Button><Button disabled={busy} variant="outline" onClick={() => decideProject(item.id, "rejected")}>Request changes</Button></span>
          </div>)}
          <h3 className="pt-2 font-semibold">Listing reports ({moderation.listing_reports.length})</h3>
          {moderation.listing_reports.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3 text-sm">
            <span>Listing {item.job_id} · {item.reason} · {item.summary || "No summary"}</span>
            <span className="flex gap-2"><Button disabled={busy} variant="outline" onClick={() => decideListing(item.id, "confirmed_concern")}>Confirm</Button><Button disabled={busy} variant="outline" onClick={() => decideListing(item.id, "no_action")}>No action</Button></span>
          </div>)}
          <h3 className="pt-2 font-semibold">Marketplace reports and appeals ({moderation.marketplace_reports.length})</h3>
          {moderation.marketplace_reports.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3 text-sm">
            <span>{item.report_type} · {item.target_type} · {item.reason} · {item.status}{reportDetails[item.id] && <span className="block max-w-2xl text-xs text-[var(--mute)]">{reportDetails[item.id].details}</span>}</span>
            <span className="flex gap-2"><Button disabled={busy} variant="outline" onClick={() => showReport(item.id)}>Details</Button><Button disabled={busy} variant="outline" onClick={() => decideMarketplaceReport(item.id, "resolved")}>Resolve</Button><Button disabled={busy} variant="outline" onClick={() => decideMarketplaceReport(item.id, "dismissed")}>Dismiss</Button></span>
          </div>)}
          <h3 className="pt-2 font-semibold">Verification review ({moderation.verification_claims.length})</h3>
          <p className="text-xs text-[var(--fog)]">Claims are listed with identifiers only. Verification decisions remain in the verification workflow.</p>
          {moderation.verification_claims.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3 text-sm">
            <span>{item.claim_type} · {item.status} · {item.id}{claimDetails[item.id] && <span className="block text-xs text-[var(--mute)]">Evidence: {claimDetails[item.id].evidence.map((e) => `${e.provider}/${e.evidence_type}${e.is_valid ? " valid" : " invalid"}`).join(", ") || "none"}</span>}</span><span className="flex gap-2"><Button disabled={busy} variant="outline" onClick={() => showClaimEvidence(item.id)}>Evidence</Button><Button disabled={busy} variant="outline" onClick={() => reviewClaim(item.id, "verified")}>Verify</Button><Button disabled={busy} variant="outline" onClick={() => reviewClaim(item.id, "rejected")}>Reject</Button></span>
          </div>)}
          <Button disabled={busy} variant="outline" onClick={expireClaims}>Process due verification expiries</Button>
          {expiryResult !== null && <p className="text-xs text-[var(--fog)]">Expired claims processed: {expiryResult}</p>}
          <p className="border-t border-white/10 pt-3 text-xs text-[var(--fog)]">Payment exceptions: {moderation.payment_exceptions.available ? "available" : moderation.payment_exceptions.reason}</p>
        </Card>
      </section>}

      {support && <section className="space-y-3">
        <h2 className="text-2xl">Support</h2>
        <Card className="space-y-4 p-4">
          {support.cases.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3 text-sm">
            <span>{item.category} · {item.summary}</span><Button disabled={busy} variant="outline" onClick={() => resolveCase(item.id)}>Resolve</Button>
          </div>)}
          <p className="text-xs text-[var(--fog)]">Disputes await human review. Provider escalation is unavailable while payments are not integrated.</p>
          {support.disputes.map((dispute) => <div key={String(dispute.id)} className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3 text-sm">
            <span>{String(dispute.reason)} · {String(dispute.status)} · {String(dispute.contract_id)}{disputeDetails[String(dispute.id)] && <span className="block max-w-2xl text-xs text-[var(--mute)]">{disputeDetails[String(dispute.id)].statement} · {disputeDetails[String(dispute.id)].evidence.length} evidence items · {disputeDetails[String(dispute.id)].addenda.length} addenda</span>}</span>
            <span className="flex gap-2"><Button disabled={busy} variant="outline" onClick={() => showDispute(String(dispute.id))}>Review details</Button><Button disabled={busy} variant="outline" onClick={() => resolveDispute(String(dispute.id), "resolved_client")}>Client outcome</Button><Button disabled={busy} variant="outline" onClick={() => resolveDispute(String(dispute.id), "resolved_freelancer")}>Freelancer outcome</Button><Button disabled={busy} variant="outline" onClick={() => resolveDispute(String(dispute.id), "no_action")}>No action</Button></span>
          </div>)}
          <p className="text-xs text-[var(--fog)]">Payment exceptions: {support.payment_exceptions.available ? "available" : support.payment_exceptions.reason}</p>
        </Card>
      </section>}

      {sources.length > 0 && <section className="space-y-3">
        <h2 className="text-2xl">Source takedown controls</h2>
        <Card className="divide-y divide-white/10 p-4">
          {sources.map((source) => <div key={source.key} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
            <span>{source.display_name} · {source.operator_disabled ? "disabled" : source.health}</span>
            <Button disabled={busy} variant="outline" onClick={() => toggleSource(source)}>{source.operator_disabled ? "Re-enable" : "Disable source"}</Button>
          </div>)}
        </Card>
      </section>}

      {waitlist && <Card className="p-4 text-sm">
        <h2 className="text-xl">Opt-in waitlist</h2>
        <p className="mt-2 text-[var(--fog)]">Client interest: {waitlist.counts_by_persona.client || 0} · freelancer interest: {waitlist.counts_by_persona.freelancer || 0}</p>
        <p className="text-xs text-[var(--mute)]">Separate concierge contact consent: {waitlist.concierge_contact_consented}. These are persisted opt-ins, not customer counts.</p>
      </Card>}

      {audit && <Card className="p-4">
        <h2 className="text-xl">Recent privileged access and actions</h2>
        <ul className="mt-3 space-y-2 text-xs text-[var(--fog)]">
          {audit.items.map((item) => <li key={item.id} className="border-t border-white/10 pt-2">{item.action} · {item.created_at || "time unavailable"}</li>)}
        </ul>
      </Card>}

      {metrics && <section className="space-y-3">
        <h2 className="text-2xl">Outcome metrics</h2>
        <Card className="p-4">
          <p className="mb-3 text-xs text-[var(--fog)]">Persisted records only · {metrics.instrumentation_status}. Suppressed cohorts and missing instrumentation are shown explicitly.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {metrics.metrics.map((metric) => <div key={metric.name} className="rounded-md border border-white/10 p-3">
              <p className="text-xs font-medium text-[var(--fog)]">{metric.name.replaceAll("_", " ")}</p>
              <p className="mt-1 text-lg text-[var(--paper)]">{metric.value === null ? metric.status.replaceAll("_", " ") : metric.name.endsWith("_rate") ? `${(metric.value * 100).toFixed(1)}%` : metric.value.toFixed(1)}</p>
              <p className="text-[11px] text-[var(--mute)]">Sample: {String(metric.sample_size)} · {metric.basis}</p>
            </div>)}
          </div>
        </Card>
      </section>}

      {productLearning && <section className="space-y-3">
        <h2 className="text-2xl">Product learning</h2>
        <Card className="p-4">
          <p className="mb-4 text-xs text-[var(--fog)]">Consent-gated events · aggregated by environment · fewer than 10 people suppressed. Empty means no observations; self-reported outcomes are not verified.</p>
          <div className="grid gap-4 lg:grid-cols-2">
            {Object.entries(productLearning.environments).map(([environment, events]) => <div key={environment}>
              <h3 className="mb-2 text-sm font-semibold capitalize">{environment}</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(events).map(([name, cell]) => <div key={name} className="rounded-md border border-white/10 p-3">
                  <p className="text-xs text-[var(--fog)]">{name.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-sm">{cell.status === "measured" ? `${cell.events} events · ${cell.people} people` : cell.status.replaceAll("_", " ")}</p>
                </div>)}
              </div>
            </div>)}
          </div>
          <p className="mt-4 text-xs text-[var(--mute)]">Instrumentation is partial. This view is not a complete funnel or customer count.</p>
        </Card>
      </section>}
    </main>
  );
}
