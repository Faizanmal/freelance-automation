"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";
import {
  addLeadNote,
  addLeadReminder,
  cancelCopilotRun,
  getPipelineBoard,
  getToken,
  getWorkspaceDashboard,
  listLeadNotes,
  setPipelineStage,
  startCopilotRun,
  updateCopilotDraft,
  updatePipelineLead,
  type CopilotDraft,
  type CopilotIntent,
  type PipelineLead,
  type PipelineStage,
  type WorkspaceDashboard,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";
import {
  CalendarClock,
  Download,
  ExternalLink,
  List,
  Columns3,
  Sparkles,
} from "lucide-react";

const STAGES: PipelineStage[] = [
  "saved",
  "researching",
  "ready",
  "applied",
  "interview",
  "negotiating",
  "won",
  "lost",
  "archived",
];

const COPILOT_INTENTS: { id: CopilotIntent; label: string }[] = [
  { id: "lead_brief", label: "Research brief" },
  { id: "requirements_gap", label: "Requirements gap" },
  { id: "portfolio_selection", label: "Portfolio picks" },
  { id: "proposal_draft", label: "Proposal draft" },
  { id: "interview_prep", label: "Interview prep" },
  { id: "scope_clarification", label: "Scope questions" },
  { id: "negotiation_scenario", label: "Negotiation" },
];

function formatMoney(n: number) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function PipelinePage() {
  const router = useRouter();
  const { toast } = useToast();
  const [view, setView] = useState<"board" | "list">("board");
  const [columns, setColumns] = useState<Record<string, PipelineLead[]>>({});
  const [dashboard, setDashboard] = useState<WorkspaceDashboard | null>(null);
  const [showDemo, setShowDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<PipelineLead | null>(null);
  const [notes, setNotes] = useState<Array<{ id: number; body: string; kind: string }>>([]);
  const [noteBody, setNoteBody] = useState("");
  const [draft, setDraft] = useState<CopilotDraft | null>(null);
  const [draftBody, setDraftBody] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [runMeta, setRunMeta] = useState<{
    duration_ms?: number;
    cost_usd?: number;
    unverified?: string[];
  } | null>(null);
  const [q, setQ] = useState("");
  const [pending, startTransition] = useTransition();

  const refresh = useCallback(async () => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    setLoading(true);
    try {
      const [board, dash] = await Promise.all([
        getPipelineBoard(),
        getWorkspaceDashboard(showDemo),
      ]);
      setColumns(board.columns || {});
      setDashboard(dash);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load pipeline", "error");
    } finally {
      setLoading(false);
    }
  }, [router, showDemo, toast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const allLeads = useMemo(() => {
    const items = Object.values(columns).flat();
    if (!q.trim()) return items;
    const needle = q.trim().toLowerCase();
    return items.filter((lead) => {
      const title = lead.job?.title?.toLowerCase() || "";
      const company = (lead.job?.company || lead.employer_name || "").toLowerCase();
      return title.includes(needle) || company.includes(needle);
    });
  }, [columns, q]);

  async function openLead(lead: PipelineLead) {
    setSelected(lead);
    setDraft(null);
    setDraftBody("");
    setRunId(null);
    setRunMeta(null);
    try {
      const res = await listLeadNotes(lead.job_id);
      setNotes(res.notes || []);
    } catch {
      setNotes([]);
    }
  }

  function moveStage(jobId: number, stage: PipelineStage) {
    startTransition(async () => {
      try {
        const res = await setPipelineStage(jobId, stage, {
          confirm_applied: stage === "applied",
        });
        toast(`Moved to ${stage}`, "success");
        if (selected?.job_id === jobId) setSelected(res.lead);
        await refresh();
      } catch (err) {
        toast(err instanceof Error ? err.message : "Stage update failed", "error");
      }
    });
  }

  async function saveNote() {
    if (!selected || !noteBody.trim()) return;
    try {
      await addLeadNote(selected.job_id, noteBody.trim(), "note");
      setNoteBody("");
      const res = await listLeadNotes(selected.job_id);
      setNotes(res.notes || []);
      toast("Note saved", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not save note", "error");
    }
  }

  async function scheduleFollowUp() {
    if (!selected) return;
    const when = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString();
    try {
      await addLeadReminder(selected.job_id, when, "Follow up on this lead");
      await updatePipelineLead(selected.job_id, { follow_up_at: when });
      toast("Follow-up scheduled (3 days)", "success");
      await refresh();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Reminder failed", "error");
    }
  }

  async function runCopilot(intent: CopilotIntent) {
    if (!selected) return;
    try {
      const result = await startCopilotRun(selected.job_id, intent, {
        idempotency_key: `${selected.job_id}:${intent}:${Date.now()}`,
      });
      setRunId(result.id);
      setRunMeta({
        duration_ms: result.output?.duration_ms,
        cost_usd: result.cost_usd,
        unverified: result.output?.unverified_claims || result.draft?.unverified_claims || [],
      });
      if (result.draft) {
        setDraft(result.draft);
        setDraftBody(result.draft.body);
      } else if (result.output?.body) {
        setDraftBody(result.output.body);
      }
      if (result.output?.auto_sent) {
        toast("Unexpected auto-send flag", "error");
      } else {
        toast(
          result.output?.fallback
            ? "Draft ready via safe fallback — not sent"
            : "Draft ready — not sent",
          "success",
        );
      }
      if (selected.pipeline_stage === "saved") {
        await setPipelineStage(selected.job_id, "researching");
        await refresh();
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Copilot failed", "error");
    }
  }

  async function saveDraftEdits() {
    if (!draft) return;
    try {
      const res = await updateCopilotDraft(draft.id, draftBody, draft.title || undefined);
      setDraft(res.draft);
      setDraftBody(res.draft.body);
      toast(`Draft v${res.draft.version} saved`, "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Draft save failed", "error");
    }
  }

  async function cancelRun() {
    if (!runId) return;
    try {
      await cancelCopilotRun(runId);
      toast("Run cancelled");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Cancel failed", "error");
    }
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader
        title="Pipeline"
        description="Your lead workspace — agent assists, you control outward actions."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={view === "board" ? "default" : "outline"}
              size="sm"
              onClick={() => setView("board")}
            >
              <Columns3 className="size-4" /> Board
            </Button>
            <Button
              variant={view === "list" ? "default" : "outline"}
              size="sm"
              onClick={() => setView("list")}
            >
              <List className="size-4" /> List
            </Button>
            <a
              className="inline-flex h-8 items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] px-3 text-xs font-semibold"
              href={`${apiBase}/api/v1/pipeline/export.csv`}
            >
              <Download className="size-4" /> Export CSV
            </a>
            <a
              className="inline-flex h-8 items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] px-3 text-xs font-semibold"
              href={`${apiBase}/api/v1/pipeline/export.ics`}
            >
              <CalendarClock className="size-4" /> Calendar
            </a>
          </div>
        }
      />

      {dashboard && (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4">
            <p className="text-sm text-[var(--text-muted)]">Follow-ups due</p>
            <p className="mt-1 text-2xl font-semibold">{dashboard.follow_ups_due}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-[var(--text-muted)]">Qualified leads</p>
            <p className="mt-1 text-2xl font-semibold">{dashboard.qualified_leads}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-[var(--text-muted)]">Active opportunities</p>
            <p className="mt-1 text-2xl font-semibold">{dashboard.active_opportunities}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-[var(--text-muted)]">Won revenue</p>
            <p className="mt-1 text-2xl font-semibold">{formatMoney(dashboard.won_revenue)}</p>
            {dashboard.demo && (
              <p className="mt-1 text-xs text-[var(--warning)]">Sample data — not yours</p>
            )}
          </Card>
          <div className="sm:col-span-2 lg:col-span-4 flex flex-wrap items-center gap-3 text-sm text-[var(--text-muted)]">
            <span>
              Conversion saved→applied{" "}
              {(dashboard.stage_conversion.saved_to_applied * 100).toFixed(0)}%
            </span>
            <span>·</span>
            <span>
              Time tracked {Math.round(dashboard.time_spent_seconds / 60)} min
            </span>
            <label className="ml-auto flex items-center gap-2">
              <input
                type="checkbox"
                checked={showDemo}
                onChange={(e) => setShowDemo(e.target.checked)}
              />
              Show sample dashboard
            </label>
          </div>
        </section>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          className="w-full max-w-sm rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          placeholder="Search title or employer"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <p className="text-xs text-[var(--text-muted)]">
          No bulk apply or unsolicited contact. Drafts never send by themselves.
        </p>
      </div>

      {loading ? (
        <div className="grid gap-3 md:grid-cols-3">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : allLeads.length === 0 ? (
        <EmptyState
          title="No pipeline leads yet"
          description="Save a lead from Leads to start the research → proposal → follow-up workflow."
          actionHref="/leads"
          actionLabel="Open Leads"
        />
      ) : view === "board" ? (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {STAGES.map((stage) => {
            const items = (columns[stage] || []).filter((lead) =>
              allLeads.some((l) => l.id === lead.id),
            );
            return (
              <div
                key={stage}
                className="min-w-[220px] flex-1 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)]/40 p-2"
              >
                <div className="mb-2 flex items-center justify-between px-1">
                  <h3 className="text-xs font-semibold uppercase tracking-wide">
                    {stage}
                  </h3>
                  <Badge>{items.length}</Badge>
                </div>
                <div className="flex flex-col gap-2">
                  {items.map((lead) => (
                    <button
                      key={lead.id}
                      type="button"
                      onClick={() => void openLead(lead)}
                      className={cn(
                        "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-3 text-left text-sm transition hover:border-[var(--border-strong)]",
                        selected?.id === lead.id && "ring-2 ring-[var(--accent)]/40",
                      )}
                    >
                      <p className="font-medium leading-snug">
                        {lead.job?.title || `Job #${lead.job_id}`}
                      </p>
                      <p className="mt-1 text-xs text-[var(--text-muted)]">
                        {lead.job?.company || lead.employer_name || "—"}
                      </p>
                      {lead.follow_up_at && (
                        <p className="mt-2 flex items-center gap-1 text-xs text-[var(--warning)]">
                          <CalendarClock className="size-3" /> Follow-up
                        </p>
                      )}
                      {lead.apply_clicked_at && !lead.applied_confirmed_at && (
                        <p className="mt-1 text-xs text-[var(--text-muted)]">
                          Apply clicked (not confirmed)
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--surface-hover)] text-left">
              <tr>
                <th className="p-3">Lead</th>
                <th className="p-3">Stage</th>
                <th className="p-3">Follow-up</th>
                <th className="p-3">Applied</th>
              </tr>
            </thead>
            <tbody>
              {allLeads.map((lead) => (
                <tr
                  key={lead.id}
                  className="cursor-pointer border-t border-[var(--border)] hover:bg-[var(--surface-hover)]"
                  onClick={() => void openLead(lead)}
                >
                  <td className="p-3">
                    <div className="font-medium">{lead.job?.title || lead.job_id}</div>
                    <div className="text-xs text-[var(--text-muted)]">
                      {lead.job?.company || lead.employer_name || "—"}
                    </div>
                  </td>
                  <td className="p-3">
                    <Badge>{lead.pipeline_stage}</Badge>
                  </td>
                  <td className="p-3 text-xs">{lead.follow_up_at || "—"}</td>
                  <td className="p-3 text-xs">
                    {lead.applied_confirmed_at
                      ? "Confirmed"
                      : lead.apply_clicked_at
                        ? "Clicked only"
                        : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <Card className="grid gap-6 p-5 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">
                  {selected.job?.title || `Job #${selected.job_id}`}
                </h2>
                <p className="text-sm text-[var(--text-muted)]">
                  {selected.job?.company || selected.employer_name || "Employer TBD"}
                </p>
              </div>
              {selected.job?.url ? (
                <a
                  className="inline-flex h-8 items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] px-3 text-xs font-semibold"
                  href={selected.job.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink className="size-4" /> Listing
                </a>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2">
              {STAGES.map((stage) => (
                <Button
                  key={stage}
                  size="sm"
                  variant={selected.pipeline_stage === stage ? "default" : "outline"}
                  disabled={pending}
                  onClick={() => moveStage(selected.job_id, stage)}
                >
                  {stage}
                </Button>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => void scheduleFollowUp()}>
                Schedule follow-up
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => moveStage(selected.job_id, "won")}
              >
                Mark won
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => moveStage(selected.job_id, "lost")}
              >
                Mark lost
              </Button>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-medium">Notes</h3>
              <textarea
                className="min-h-20 w-full rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-2 text-sm"
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="Negotiation notes, research, next steps…"
              />
              <Button className="mt-2" size="sm" onClick={() => void saveNote()}>
                Add note
              </Button>
              <ul className="mt-3 space-y-2">
                {notes.map((n) => (
                  <li
                    key={n.id}
                    className="rounded-[var(--radius)] border border-[var(--border)] p-2 text-sm"
                  >
                    <Badge className="mb-1">{n.kind}</Badge>
                    <p className="whitespace-pre-wrap">{n.body}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4" />
              <h3 className="text-sm font-medium">AI copilot</h3>
              <span className="text-xs text-[var(--text-muted)]">
                Grounded drafts · never auto-sends
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {COPILOT_INTENTS.map((intent) => (
                <Button
                  key={intent.id}
                  size="sm"
                  variant="outline"
                  onClick={() => void runCopilot(intent.id)}
                >
                  {intent.label}
                </Button>
              ))}
            </div>
            {runId && (
              <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                <span>Run {runId.slice(0, 8)}…</span>
                {runMeta?.duration_ms != null && <span>{runMeta.duration_ms} ms</span>}
                {runMeta?.cost_usd != null && <span>~${runMeta.cost_usd.toFixed(5)}</span>}
                <Button size="sm" variant="ghost" onClick={() => void cancelRun()}>
                  Cancel
                </Button>
              </div>
            )}
            {runMeta?.unverified && runMeta.unverified.length > 0 && (
              <div className="rounded-[var(--radius)] border border-[var(--warning)]/40 bg-[var(--warning)]/10 p-3 text-xs">
                <p className="font-medium">Unverified claims highlighted</p>
                <ul className="mt-1 list-disc pl-4">
                  {runMeta.unverified.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              </div>
            )}
            <textarea
              className="min-h-48 w-full rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
              value={draftBody}
              onChange={(e) => setDraftBody(e.target.value)}
              placeholder="Editable draft appears here after a copilot run…"
            />
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={!draft} onClick={() => void saveDraftEdits()}>
                Save draft version
              </Button>
              <Link
                href="/leads"
                className="inline-flex h-8 items-center rounded-[var(--radius)] border border-[var(--border)] px-3 text-xs font-semibold"
              >
                Open Leads to send manually
              </Link>
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              External applications must use the original listing. Copilot cannot
              dispatch messages or applications.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
