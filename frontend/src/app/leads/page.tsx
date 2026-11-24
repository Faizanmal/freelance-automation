"use client";



import Link from "next/link";

import { useRouter, useSearchParams } from "next/navigation";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";

import {

  draftProposal,
  reportJobExpired,
  reportListingTrust,

  getAuthFindings,

  getDemoFindings,

  getPipelineStats,

  getToken,

  setLeadAction,

  postMatchFeedback,
  recordProductEvent,

  submitApplication,

  type ApplyFormFields,

  type LeadFinding,

  type LeadFindingsResponse,

  type PipelineStats,

  type ProposalDraftResponse,

} from "@/lib/api";

const SAVE_REASONS = [
  { id: "skills_fit", label: "Skills fit" },
  { id: "budget_fit", label: "Budget fit" },
  { id: "interesting_project", label: "Interesting project" },
  { id: "other", label: "Other" },
] as const;

const SKIP_REASONS = [
  { id: "wrong_skills", label: "Wrong skills" },
  { id: "low_budget", label: "Low budget" },
  { id: "full_time", label: "Full-time / not freelance" },
  { id: "spammy", label: "Spammy / low quality" },
  { id: "other", label: "Other" },
] as const;

import { motion, AnimatePresence } from "framer-motion";

import { Card } from "@/components/ui/card";

import { Button } from "@/components/ui/button";

import { Badge } from "@/components/ui/badge";

import { EmptyState } from "@/components/ui/empty-state";

import { MatchScore, MatchScoreBar } from "@/components/ui/match-score";

import { PageHeader } from "@/components/ui/page-header";

import { Skeleton } from "@/components/ui/skeleton";

import { LeadSignalMeters } from "@/components/lead-signal-meters";

import { useToast } from "@/components/ui/toast";

import { Check, Copy, ExternalLink, Filter, Mail } from "lucide-react";

import { cn } from "@/lib/cn";

import {
  buildGmailComposeUrl,
  buildSafeMailtoUrl,
  openSafeExternalUrl,
  sanitizeEmailAddress,
} from "@/lib/security";



const DEFAULT_KEYWORDS = "python,react,fastapi,typescript,remote";



const ACTION_LABEL: Record<LeadFinding["action"], string> = {

  draft_bid: "Draft",

  watch: "Watch",

  skip: "Skip",

};



type StatusFilter = "all" | "new" | "high" | "saved" | "pitched" | "won" | "skipped";



const emptyForm = (): ApplyFormFields => ({

  proposal: "",

  bid_amount: null,

  currency: "USD",

  delivery_days: 7,

  milestone_plan: "",

  milestone_percentage: 100,

  submit_mode: "unsupported",

});



function LeadsPageInner() {

  const router = useRouter();

  const searchParams = useSearchParams();

  const { toast } = useToast();

  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);

  const [freelanceFocus, setFreelanceFocus] = useState(true);

  const [sourceFilter, setSourceFilter] = useState("all");

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(() => {

    const raw = searchParams.get("filter");

    if (
      raw === "saved" ||
      raw === "pitched" ||
      raw === "won" ||
      raw === "skipped" ||
      raw === "new" ||
      raw === "high" ||
      raw === "all"
    ) {

      return raw;

    }

    return "all";

  });

  const [search, setSearch] = useState("");

  const [data, setData] = useState<LeadFindingsResponse | null>(null);

  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [draftMeta, setDraftMeta] = useState<ProposalDraftResponse | null>(null);

  const [form, setForm] = useState<ApplyFormFields>(emptyForm());

  const [copiedPitch, setCopiedPitch] = useState(false);

  const [pitchKind, setPitchKind] = useState<"initial" | "followup">("initial");

  const [hideAgenciesFilter, setHideAgenciesFilter] = useState(false);

  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);

  const [focusOverride, setFocusOverride] = useState<boolean | undefined>(undefined);

  const [pending, startTransition] = useTransition();

  const [authed, setAuthed] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(getToken());
  });

  const [pipelineStats, setPipelineStats] = useState<PipelineStats | null>(null);
  const [writingJobIds, setWritingJobIds] = useState<Set<number>>(() => new Set());
  const writeQueuesRef = useRef(new Map<number, Promise<void>>());
  const writeGenRef = useRef(new Map<number, number>());
  const pendingWritesRef = useRef(0);
  const dataRef = useRef(data);
  dataRef.current = data;



  const load = useCallback((value: string, focus?: boolean, silent = false) => {
    startTransition(async () => {
      try {
        if (!silent) {
          setLoading(true);
        }
        setError(null);

        const token = getToken();

        setAuthed(Boolean(token));

        const response = token

          ? await getAuthFindings(25, focus, true)

          : await getDemoFindings(value, 10, focus ?? true);

        if (typeof response.freelance_focus === "boolean") {
          setFreelanceFocus(response.freelance_focus);
        }

        // Don't clobber in-flight Save/Skip/Undo writes with a stale fetch.
        if (pendingWritesRef.current === 0) {
          setData(response);
        }
        if (token) {
          void getPipelineStats()
            .then(setPipelineStats)
            .catch(() => setPipelineStats(null));
        } else {
          setPipelineStats(null);
        }

      } catch (err) {

        const message = err instanceof Error ? err.message : "Failed to load leads";
        if (/no jobs in the database/i.test(message) || /call post \/jobs\/scrape/i.test(message)) {

          setError(null);

          setData({

            generated_at: new Date().toISOString(),

            total_scanned: 0,

            total_matched: 0,

            total_findings: 0,

            freelance_focus: focus ?? true,

            action_counts: { draft_bid: 0, watch: 0, skip: 0 },

            keywords: value.split(",").map((part) => part.trim()).filter(Boolean),

            items: [],

          });

          return;

        }

        setError(message);

        setData(null);

      } finally {
        setLoading(false);
      }

    });

  }, []);



  useEffect(() => {

    load(DEFAULT_KEYWORDS);

  }, [load]);



  const filterParam = searchParams.get("filter");
  const [prevFilterParam, setPrevFilterParam] = useState(filterParam);
  if (prevFilterParam !== filterParam) {
    setPrevFilterParam(filterParam);
    if (
      filterParam === "saved" ||
      filterParam === "pitched" ||
      filterParam === "won" ||
      filterParam === "skipped" ||
      filterParam === "new" ||
      filterParam === "high" ||
      filterParam === "all"
    ) {
      setStatusFilter(filterParam);
    }
  }



  const makeDraft = useCallback(

    (jobId: number) => {

      if (!getToken()) {

        router.push("/auth");

        return;

      }

      startTransition(async () => {

        try {

          setError(null);

          setSubmitMessage(null);

          const response = await draftProposal(jobId);

          setActiveJobId(jobId);

          setPitchKind("initial");

          setDraftMeta(response);

          setForm({

            proposal: response.form_fields.proposal || response.draft,

            bid_amount: response.form_fields.bid_amount ?? null,

            currency: response.form_fields.currency || "USD",

            delivery_days: response.form_fields.delivery_days ?? 7,

            milestone_plan: response.form_fields.milestone_plan || "",

            milestone_percentage: response.form_fields.milestone_percentage ?? 100,

            source_name: response.form_fields.source_name || response.source_name,

            source_id: response.form_fields.source_id,

            project_url: response.form_fields.project_url || response.source_url,

            submit_mode: response.form_fields.submit_mode || "unsupported",

            apply_email: response.form_fields.apply_email ?? response.apply_email ?? null,

            email_subject:
              response.form_fields.email_subject ||
              response.email_subject ||
              `Contract inquiry: ${response.title}`,

          });

          setCopiedPitch(false);

        } catch (err) {

          setError(
            err instanceof Error && !/internal server error|500/i.test(err.message)
              ? err.message
              : "Unable to generate draft bid right now. Please try again or open the original listing directly.",
          );

        }

      });

    },

    [router],

  );



  useEffect(() => {

    const jobParam = searchParams.get("job");

    if (!jobParam) return;

    const jobId = Number(jobParam);

    if (!Number.isFinite(jobId) || jobId <= 0) return;

    if (!getToken()) {

      router.push("/auth");

      return;

    }

    makeDraft(jobId);

  }, [searchParams, router, makeDraft]);



  useEffect(() => {

    if (!draftMeta || !activeJobId) return;

    const onKey = (event: KeyboardEvent) => {

      if (event.key === "Escape") {

        setActiveJobId(null);

        setDraftMeta(null);

        setForm(emptyForm());

        setSubmitMessage(null);

      }

    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);

  }, [draftMeta, activeJobId]);



  const confirmSubmit = () => {

    if (!activeJobId) return;

    if (!getToken()) {

      router.push("/auth");

      return;

    }

    startTransition(async () => {

      try {

        setError(null);

        setSubmitMessage(null);

        const result = await submitApplication(activeJobId, form, true);

        setSubmitMessage(

          result.detail ||

            `${result.status} via ${result.submit_mode}${

              result.external_id ? ` (id ${result.external_id})` : ""

            }`,

        );

        if (result.apply_url && (result.submit_mode === "external_apply" || result.status === "prepared")) {

          openSafeExternalUrl(result.apply_url);

        }

      } catch (err) {

        setError(err instanceof Error ? err.message : "Submit failed");

      }

    });

  };



  const closeDraft = () => {

    setActiveJobId(null);

    setDraftMeta(null);

    setForm(emptyForm());

    setSubmitMessage(null);

  };



  const handleReportExpired = (jobId: number) => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        await reportJobExpired(jobId, "dead_link");
        await load(keywords, focusOverride, true);
        setSubmitMessage("Reported as dead/closed link. It will be pruned.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not report link");
      }
    });
  };

  const handleTrustReport = (jobId: number) => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        const res = await reportListingTrust(jobId, {
          reason_code: "other_trust_concern",
          details: "User flagged listing for human review from Desk",
        });
        setSubmitMessage(
          res.message ||
            "Concern queued for human review — not an automatic ban.",
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not submit report");
      }
    });
  };

  const applyOptimisticStatus = useCallback(
    (
      current: LeadFindingsResponse,
      jobId: number,
      status: "save" | "skip" | "pitched" | "won" | "clear",
    ): LeadFindingsResponse => {
      const previousStatus =
        current.items.find((item) => item.job_id === jobId)?.user_status ?? null;
      const nextStatus = status === "clear" ? null : status;
      if (previousStatus === nextStatus) {
        return current;
      }
      const updatedItems = current.items.map((item) =>
        item.job_id === jobId ? { ...item, user_status: nextStatus } : item,
      );
      const allNonSkipped = updatedItems.filter((item) => item.user_status !== "skip");
      const skippedItems = updatedItems.filter((item) => item.user_status === "skip");
      const maxActive = authed ? 25 : 10;
      const nonSkipped =
        allNonSkipped.length > maxActive
          ? [...allNonSkipped]
              .sort((a, b) => b.score - a.score)
              .slice(0, maxActive)
          : allNonSkipped;
      const skippedCount = skippedItems.length;
      const priorSkipped =
        status === "skip"
          ? Math.max(Number(current.skipped_count) || 0, skippedCount)
          : status === "clear" && previousStatus === "skip"
            ? Math.max(0, (Number(current.skipped_count) || 0) - 1)
            : Number(current.skipped_count) || skippedCount;
      return {
        ...current,
        total_findings: nonSkipped.length,
        skipped_count: priorSkipped,
        action_counts: {
          draft_bid: nonSkipped.filter((item) => item.action === "draft_bid").length,
          watch: nonSkipped.filter((item) => item.action === "watch").length,
          skip: priorSkipped,
        },
        items: [...nonSkipped, ...skippedItems],
      };
    },
    [authed],
  );

  useEffect(() => {
    const flushOrBlock = (event: BeforeUnloadEvent) => {
      if (pendingWritesRef.current > 0) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", flushOrBlock);
    return () => {
      window.removeEventListener("beforeunload", flushOrBlock);
    };
  }, []);

  const updateLeadStatus = (
    jobId: number,
    status: "save" | "skip" | "pitched" | "won" | "clear",
    opts?: { reason?: string },
  ) => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }

    const reason = opts?.reason;
    const previousStatus =
      dataRef.current?.items.find((item) => item.job_id === jobId)?.user_status ?? null;
    const snapshot = dataRef.current;
    // Each click (including Undo) gets its own generation so a stale success
    // handler from a prior write cannot overwrite a newer durable intent.
    const gen = (writeGenRef.current.get(jobId) || 0) + 1;
    writeGenRef.current.set(jobId, gen);

    if (snapshot) {
      setData(applyOptimisticStatus(snapshot, jobId, status));
    }
    setWritingJobIds((prev) => new Set(prev).add(jobId));

    const isLatest = () => writeGenRef.current.get(jobId) === gen;

    const runWrite = async () => {
      pendingWritesRef.current += 1;
      try {
        setError(null);
        // Always await a durable API write. Clear uses setLeadAction so pipeline
        // soft-delete + hard delete both run (Undo must survive hard reload).
        if (status === "won") {
          await postMatchFeedback({
            job_id: jobId,
            kind: "outcome",
            outcome: "contract",
            reason: reason || "contract",
          });
        } else if (status === "pitched") {
          await postMatchFeedback({
            job_id: jobId,
            kind: "outcome",
            outcome: "interview",
            reason: reason || "interview",
          });
        } else if (status === "save" || status === "skip") {
          await postMatchFeedback({
            job_id: jobId,
            kind: status,
            reason,
          });
        } else if (status === "clear") {
          // setLeadAction clear soft-deletes pipeline state then hard-deletes the row.
          await setLeadAction(jobId, "clear", { reason });
        } else {
          await setLeadAction(jobId, status, { reason });
        }

        if (!isLatest()) {
          // A newer Undo/Save already owns UI + final persistence; still finished
          // this request so it was not cancelled — just skip stale UI updates.
          return;
        }

        if (status === "save" || status === "skip") {
          try {
            void Promise.resolve(
              recordProductEvent(
                status === "save" ? "lead_saved" : "lead_skipped",
                "discovery",
              ),
            ).catch(() => null);
          } catch {
            /* analytics must not fail the durable write */
          }
        }

        const message =
          status === "save"
            ? "Lead saved"
            : status === "pitched"
              ? "Lead marked as pitched / interview"
              : status === "won"
                ? "Lead marked as contract won"
                : status === "skip"
                  ? "Lead skipped — hidden from default list"
                  : "Lead status cleared";

        setData((current) =>
          current ? applyOptimisticStatus(current, jobId, status) : current,
        );

        setSubmitMessage(message);

        try {
          if (status === "save" || status === "skip" || status === "pitched" || status === "won") {
            toast(message, {
              tone: "success",
              actionLabel: "Undo",
              durationMs: 8000,
              onAction: () => updateLeadStatus(jobId, "clear"),
            });
          }
        } catch {
          /* ignore UI-only failures */
        }

        void getPipelineStats()
          .then(setPipelineStats)
          .catch(() => null);
      } catch (err) {
        if (!isLatest()) return;
        if (snapshot) {
          const rollbackStatus =
            previousStatus === "save" ||
            previousStatus === "skip" ||
            previousStatus === "pitched" ||
            previousStatus === "won"
              ? previousStatus
              : "clear";
          setData(applyOptimisticStatus(snapshot, jobId, rollbackStatus));
        } else {
          await load(keywords, focusOverride, true);
        }
        setError(err instanceof Error ? err.message : "Could not update lead");
      } finally {
        pendingWritesRef.current = Math.max(0, pendingWritesRef.current - 1);
        if (isLatest()) {
          setWritingJobIds((prev) => {
            const next = new Set(prev);
            next.delete(jobId);
            return next;
          });
        }
      }
    };

    // Queue per job so writes stay ordered, but never cancel — Undo is a new
    // durable request that runs after (or as) the latest generation.
    const prior = writeQueuesRef.current.get(jobId) ?? Promise.resolve();
    const queued = prior.catch(() => undefined).then(runWrite);
    writeQueuesRef.current.set(jobId, queued);
  };



  const sources = useMemo(() => {

    const names = new Set<string>();

    for (const item of data?.items || []) {

      if (item.source_name) names.add(item.source_name);

    }

    return Array.from(names).sort();

  }, [data]);



  const visibleItems = useMemo(() => {

    const query = search.trim().toLowerCase();

    const items = [...(data?.items || [])].sort((a, b) => b.score - a.score);

    return items.filter((item) => {

      if (sourceFilter !== "all" && item.source_name !== sourceFilter) return false;

      if (statusFilter !== "skipped" && item.user_status === "skip") return false;

      if (statusFilter === "saved" && item.user_status !== "save") return false;

      if (statusFilter === "pitched" && item.user_status !== "pitched" && item.user_status !== "won") return false;

      if (statusFilter === "won" && item.user_status !== "won") return false;

      if (statusFilter === "skipped" && item.user_status !== "skip") return false;

      if (statusFilter === "high" && item.score < 0.7) return false;

      if (statusFilter === "new" && item.user_status) return false;

      if (hideAgenciesFilter && item.client_signal?.is_agency) return false;

      if (query) {

        const haystack = [item.title, item.company, item.source_name, item.why, ...(item.matched_keywords || [])]

          .filter(Boolean)

          .join(" ")

          .toLowerCase();

        if (!haystack.includes(query)) return false;

      }

      return true;

    });

  }, [data, sourceFilter, statusFilter, search, hideAgenciesFilter]);



  const selected = useMemo(

    () => visibleItems.find((item) => item.job_id === selectedId) || null,

    [visibleItems, selectedId],

  );



  const isExternalApply = form.submit_mode === "external_apply";

  const canDirectSubmit = form.submit_mode === "api_bid" || form.submit_mode === "email_apply";

  const drawerOpen = Boolean(draftMeta && activeJobId);



  const statusCounts = useMemo(() => {
    const items = data?.items || [];
    const nonSkipped = items.filter((item) => item.user_status !== "skip");
    const skippedFromItems = items.filter((item) => item.user_status === "skip").length;
    return {
      // Prefer server totals so All/Skipped stay aligned across reload.
      all: typeof data?.total_findings === "number" ? data.total_findings : nonSkipped.length,
      new: nonSkipped.filter((item) => !item.user_status).length,
      high: nonSkipped.filter((item) => item.score >= 0.7).length,
      // Pipeline-stats is the shared SoT with Desk + Pipeline.
      saved:
        typeof pipelineStats?.saved_count === "number"
          ? pipelineStats.saved_count
          : items.filter((item) => item.user_status === "save").length,
      pitched:
        typeof pipelineStats?.pitched_count === "number"
          ? pipelineStats.pitched_count
          : items.filter((item) => item.user_status === "pitched" || item.user_status === "won")
              .length,
      won:
        typeof pipelineStats?.won_count === "number"
          ? pipelineStats.won_count
          : items.filter((item) => item.user_status === "won").length,
      skipped: Math.max(
        skippedFromItems,
        typeof data?.skipped_count === "number" ? data.skipped_count : 0,
        typeof pipelineStats?.skipped_count === "number" ? pipelineStats.skipped_count : 0,
      ),
    };
  }, [data, pipelineStats]);

  const summaryCounts = useMemo(() => {
    const items = data?.items || [];
    const nonSkipped = items.filter((item) => item.user_status !== "skip");
    return {
      draft_bid: nonSkipped.filter((item) => item.action === "draft_bid").length,
      watch: nonSkipped.filter((item) => item.action === "watch").length,
      skip: authed
        ? statusCounts.skipped
        : (data?.action_counts.skip ?? items.filter((item) => item.action === "skip").length),
    };
  }, [data, authed, statusCounts.skipped]);

  const statusTabs: { id: StatusFilter; label: string; count: number }[] = [

    { id: "all", label: "All", count: statusCounts.all },

    { id: "new", label: "New", count: statusCounts.new },

    { id: "high", label: "High match", count: statusCounts.high },

    { id: "saved", label: "Saved", count: statusCounts.saved },

    { id: "pitched", label: "Pitched", count: statusCounts.pitched },

    { id: "won", label: "Won", count: statusCounts.won },

    { id: "skipped", label: "Skipped", count: statusCounts.skipped },

  ];

  const handleCopyPitch = async () => {
    const text = (form.proposal || "").trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedPitch(true);
      setTimeout(() => setCopiedPitch(false), 2500);
    } catch {
      setSubmitMessage("Could not access clipboard — select and copy text manually.");
    }
  };

  const handleOpenGmail = () => {
    const to = draftMeta?.apply_email || form.apply_email || null;
    const subject =
      form.email_subject ||
      draftMeta?.email_subject ||
      (draftMeta?.title ? `Contract inquiry: ${draftMeta.title}` : "Contract inquiry");
    const gmailUrl = buildGmailComposeUrl({
      to,
      subject,
      body: form.proposal,
    });
    openSafeExternalUrl(gmailUrl);
  };

  const handleOpenMailApp = () => {
    const to = draftMeta?.apply_email || form.apply_email || null;
    const subject =
      form.email_subject ||
      draftMeta?.email_subject ||
      (draftMeta?.title ? `Contract inquiry: ${draftMeta.title}` : "Contract inquiry");
    const mailtoUri = buildSafeMailtoUrl({
      to,
      subject,
      body: form.proposal,
    });
    if (typeof window !== "undefined") {
      window.location.href = mailtoUri;
    }
  };

  const handleExportCsv = () => {
    if (!visibleItems.length) return;
    const headers = [
      "Job ID",
      "Title",
      "Company",
      "Source",
      "Match Score",
      "Reasons",
      "Status",
      "URL",
      "Posted At",
    ];
    const escapeCsv = (val: string | number | null | undefined) => {
      const str = String(val ?? "");
      return `"${str.replace(/"/g, '""')}"`;
    };
    const rows = visibleItems.map((item) => [
      item.job_id,
      escapeCsv(item.title),
      escapeCsv(item.company),
      escapeCsv(item.source_label || item.source_name),
      Math.round((item.score || 0) * 100),
      escapeCsv([item.why, ...(item.matched_keywords || [])].filter(Boolean).join("; ")),
      escapeCsv(item.user_status),
      escapeCsv(item.url),
      escapeCsv(item.posted_at),
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," +
      encodeURIComponent([headers.join(","), ...rows.map((r) => r.join(","))].join("\n"));
    const link = document.createElement("a");
    link.setAttribute("href", csvContent);
    link.setAttribute(
      "download",
      `signal-desk-leads-${new Date().toISOString().slice(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };



  return (

    <div className="flex flex-1 flex-col gap-6">

      <PageHeader

        title={authed ? "Your Opportunities" : "Sample leads"}

        description={

          authed

            ? "Relevant freelance and contract work, ranked for you."

            : "Preview of how ranking works. Sign in to use your Hunt Rules, Save/Skip, and digests."

        }

        actions={

          <>

            <Button type="button" variant="outline" onClick={() => load(keywords, focusOverride)} disabled={pending}>

              {pending ? "Working…" : "Refresh leads"}

            </Button>

            {visibleItems.length > 0 ? (
              <Button type="button" variant="outline" onClick={handleExportCsv} title="Export filtered leads to CSV">
                Export CSV
              </Button>
            ) : null}

            {authed ? (

              <Link

                href="/preferences?tab=matching"

                className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"

              >

                Edit Hunt Rules

              </Link>

            ) : (

              <Link

                href="/auth"

                className="inline-flex h-10 items-center rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)]"

              >

                Sign in

              </Link>

            )}

          </>

        }

      />



      {!authed && !pending && data !== null ? (

        <p className="text-sm text-[var(--text-muted)]">

          <Link href="/auth" className="text-[var(--accent)] hover:underline">

            Sign in

          </Link>{" "}

          to unlock your personal lead desk.

        </p>

      ) : null}



      <div className="flex flex-col gap-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-3">

        <div className="flex flex-wrap items-center gap-2">

          <Filter className="size-4 text-[var(--text-muted)]" />

          {statusTabs.map((tab) => (

            <button

              key={tab.id}

              type="button"

              onClick={() => setStatusFilter(tab.id)}

              className={cn(

                "rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",

                statusFilter === tab.id

                  ? "bg-[var(--accent-muted)] text-[var(--accent)]"

                  : "text-[var(--text-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]",

              )}

            >

              {tab.label} ({tab.count})

            </button>

          ))}

        </div>

        <div className="flex flex-wrap items-center gap-3">

          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--text)]">

            <input

              type="checkbox"

              checked={freelanceFocus}

              onChange={(event) => {

                const next = event.target.checked;

                setFreelanceFocus(next);

                setFocusOverride(next);

                load(keywords, next);

              }}

              className="size-4 rounded accent-[var(--accent)]"

            />

            Freelance focus

          </label>

          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--text)]">

            <input

              type="checkbox"

              checked={hideAgenciesFilter}

              onChange={(event) => setHideAgenciesFilter(event.target.checked)}

              className="size-4 rounded accent-[var(--accent)]"

            />

            Hide staffing agencies

          </label>

          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">

            Source

            <select

              value={sourceFilter}

              onChange={(event) => setSourceFilter(event.target.value)}

              className="sd-input w-auto py-1.5"

            >

              <option value="all">All sources</option>

              {sources.map((name) => (

                <option key={name} value={name}>

                  {name}

                </option>

              ))}

            </select>

          </label>

          <input

            value={search}

            onChange={(event) => setSearch(event.target.value)}

            placeholder="Search title, company, skills…"

            className="sd-input max-w-sm flex-1"

            aria-label="Search opportunities"

          />

        </div>

        {!authed ? (

          <form

            className="flex flex-wrap gap-3"

            onSubmit={(event) => {

              event.preventDefault();

              load(keywords, freelanceFocus);

            }}

          >

            <input

              value={keywords}

              onChange={(event) => setKeywords(event.target.value)}

              className="sd-input min-w-[260px] flex-1"

              placeholder="python, fastapi, next.js"

            />

            <Button type="submit" disabled={pending}>

              {pending ? "Working…" : "Refresh leads"}

            </Button>

          </form>

        ) : (

          <p className="text-sm text-[var(--text-muted)]">Using your saved preferences</p>

        )}

      </div>



      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}

      {submitMessage ? <p className="text-sm text-[var(--success)]">{submitMessage}</p> : null}

      {authed && data?.ineligible_samples && data.ineligible_samples.length > 0 ? (
        <details className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-muted)]">
          <summary className="cursor-pointer font-medium text-[var(--text-secondary)]">
            Hard-filtered examples ({data.ineligible_samples.length})
            {data.candidate_stage ? ` · ${data.candidate_stage}` : ""}
            {data.cache_hit ? " · cached" : ""}
          </summary>
          <ul className="mt-2 space-y-1">
            {data.ineligible_samples.slice(0, 5).map((sample) => (
              <li key={`${sample.job_id}-${sample.title}`}>
                {(sample.title || "Listing").slice(0, 72)} —{" "}
                {(sample.hard_filters_failed || []).join(", ") || "ineligible"}
                {sample.evidence?.[0] ? ` (${sample.evidence[0]})` : ""}
              </li>
            ))}
          </ul>
        </details>
      ) : null}



      {data ? (

        <section className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-3 text-sm text-[var(--text-secondary)]">

          {!authed ? (

            <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--warning)] uppercase">

              Sample leads — not your Hunt Rules

            </p>

          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3">

            <p>

              <span className="text-[var(--text)]">Scanned {data.total_scanned} recent listings</span>{data.total_indexed && data.total_indexed > data.total_scanned ? ` (of ${data.total_indexed} indexed)` : ""} · matched {data.total_matched} ·

              showing {visibleItems.length}

              {data.freelance_focus ? " · freelance focus on" : " · all matches"}

              {data.generated_at ? ` · updated ${new Date(data.generated_at).toLocaleString()}` : ""}

            </p>

            <div className="flex flex-wrap gap-2">

              <Badge variant="outline">Draft: {summaryCounts.draft_bid}</Badge>

              <Badge variant="accent">Watch: {summaryCounts.watch}</Badge>

              <Badge variant="danger">Skip: {summaryCounts.skip}</Badge>

            </div>

          </div>

        </section>

      ) : null}



      {loading || (pending && !data) ? (

        <div className="grid gap-3">

          <Skeleton className="h-40 w-full" />

          <Skeleton className="h-40 w-full" />

        </div>

      ) : null}



      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">

        <div className="grid gap-3">

          {!loading && visibleItems.map((finding) => (

            <Card

              key={finding.job_id}

              interactive

              className={cn(

                "flex cursor-pointer flex-col p-5",

                selectedId === finding.job_id && "border-[var(--accent)]/50 ring-1 ring-[var(--accent)]/30",

              )}

              onClick={() => setSelectedId(finding.job_id)}

            >

              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">

                <div className="min-w-0">

                  <h2 className="text-lg font-medium text-[var(--text)]">{finding.title}</h2>

                  <p className="mt-1 text-sm text-[var(--text-secondary)]">

                    {[finding.company, finding.source_label || finding.source_attribution || finding.source_name]

                      .filter(Boolean)

                      .join(" · ")}

                  </p>

                </div>

                <div className="flex flex-wrap items-center gap-2">

                  <MatchScore
                    score={finding.score}
                    showLabel={
                      !(
                        finding.suppress_fit_badge
                        || (finding.employment_risks && finding.employment_risks.length > 0)
                      )
                    }
                  />

                  {finding.client_signal?.poster_type === "direct_founder" ? (
                    <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-400">
                      Direct Founder
                    </Badge>
                  ) : finding.client_signal?.poster_type === "agency_recruiter" ? (
                    <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-400">
                      Staffing Agency
                    </Badge>
                  ) : null}

                  {finding.client_signal?.urgency === "high" && finding.client_signal.urgency_label ? (
                    <Badge variant="outline" className="border-[var(--danger)]/40 bg-[var(--danger-muted)] text-[var(--danger)] font-semibold">
                      Urgent: {finding.client_signal.urgency_label}
                    </Badge>
                  ) : null}

                  {finding.smart_match?.is_boosted ? (
                    <Badge
                      variant="outline"
                      className="border-[var(--fit)]/40 bg-[var(--accent-muted)] text-[var(--fit)] font-medium"
                      title={finding.smart_match.reason || "Learned preference boost"}
                    >
                      Learned fit
                    </Badge>
                  ) : null}

                  {finding.budget_label ? (

                    <Badge variant="outline">{finding.budget_label}</Badge>

                  ) : null}

                  {!(finding.suppress_fit_badge || (finding.employment_risks && finding.employment_risks.length > 0))
                    ? finding.freelance_benefits?.length
                      ? <Badge variant="muted">{finding.freelance_benefits[0]}</Badge>
                      : typeof finding.freelance_fit === "number" && finding.freelance_fit >= 0.7
                        ? <Badge variant="muted">Contract / Freelance</Badge>
                        : null
                    : null}

                  <Badge

                    variant={

                      finding.action === "draft_bid"

                        ? "accent"

                        : finding.action === "watch"

                          ? "outline"

                          : "danger"

                    }

                  >

                    {ACTION_LABEL[finding.action]}

                  </Badge>

                  {finding.user_status === "save" ? <Badge variant="success">Saved</Badge> : null}

                  {finding.user_status === "pitched" ? <Badge variant="accent">Pitched</Badge> : null}

                  {finding.user_status === "won" ? <Badge variant="success">Won</Badge> : null}

                  {finding.user_status === "skip" ? <Badge variant="danger">Skipped</Badge> : null}

                </div>

              </div>



              <p className="mb-3 text-sm leading-relaxed text-[var(--text)]">{finding.why}</p>

              {finding.why_shown ? (
                <p className="mb-2 text-xs text-[var(--text-muted)]">{finding.why_shown}</p>
              ) : null}

              {finding.explanation?.missing_qualifications?.length ? (
                <p className="mb-3 text-xs text-[var(--warning)]">
                  Missing vs Hunt Rules:{" "}
                  {finding.explanation.missing_qualifications.slice(0, 6).join(", ")}
                </p>
              ) : null}

              {finding.freelance_benefits_line ? (

                <p className="mb-3 text-sm text-[var(--accent)]">{finding.freelance_benefits_line}</p>

              ) : null}

              <LeadSignalMeters
                className="mb-4"
                compact
                fit={finding.fit_score ?? finding.score}
                trust={finding.client_quality_score ?? finding.client_signal?.score ?? 0.5}
                freshness={finding.freshness_score ?? 0}
              />

              <div className="mb-4 grid gap-3 md:grid-cols-2">

                {finding.signals.length > 0 ? (

                  <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3">

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">

                      Signals

                    </p>

                    <ul className="space-y-1 text-sm text-[var(--text-secondary)]">

                      {finding.signals.slice(0, 4).map((signal) => (

                        <li key={signal}>+ {signal}</li>

                      ))}

                    </ul>

                  </div>

                ) : null}

                {finding.risks.length > 0 ? (

                  <div className="rounded-md border border-[var(--danger)]/20 bg-[var(--danger-muted)] p-3">

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">

                      Watchouts

                    </p>

                    <ul className="space-y-1 text-sm text-[var(--danger)]">

                      {finding.risks.slice(0, 4).map((risk) => (

                        <li key={risk}>! {risk}</li>

                      ))}

                    </ul>

                  </div>

                ) : null}

              </div>



              <div

                className="mt-auto flex flex-wrap gap-2 border-t border-[var(--border)] pt-4"

                onClick={(event) => event.stopPropagation()}

              >

                <Button

                  variant="default"

                  size="sm"

                  onClick={() => {
                    if (authed) {
                      void postMatchFeedback({
                        job_id: finding.job_id,
                        kind: "apply_click",
                        reason: "open_original",
                      }).catch(() => null);
                      void recordProductEvent("external_apply_clicked", "discovery").catch(() => null);
                    }
                    openSafeExternalUrl(finding.apply_url || finding.url);
                  }}

                >

                  <ExternalLink className="size-3.5" />

                  Open original

                </Button>

                {authed ? (

                  <>

                    <div className="inline-flex flex-wrap items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={writingJobIds.has(finding.job_id)}
                        onClick={() =>
                          updateLeadStatus(
                            finding.job_id,
                            finding.user_status === "save" ? "clear" : "save",
                          )
                        }
                      >
                        {finding.user_status === "save" ? "Unsave" : "Save"}
                      </Button>
                      {finding.user_status !== "save" ? (
                        <details className="relative">
                          <summary className="cursor-pointer list-none rounded px-1.5 py-1 text-[11px] text-[var(--text-muted)] hover:bg-[var(--surface-sunken)]">
                            reason
                          </summary>
                          <div className="absolute right-0 z-20 mt-1 flex min-w-[11rem] flex-col gap-1 rounded-md border border-[var(--border)] bg-[var(--surface)] p-1 shadow-md">
                            {SAVE_REASONS.map((reason) => (
                              <button
                                key={reason.id}
                                type="button"
                                className="rounded px-2 py-1 text-left text-[11px] hover:bg-[var(--surface-sunken)]"
                                onClick={() =>
                                  updateLeadStatus(finding.job_id, "save", {
                                    reason: reason.id,
                                  })
                                }
                              >
                                {reason.label}
                              </button>
                            ))}
                          </div>
                        </details>
                      ) : null}
                    </div>

                    {finding.user_status === "pitched" ? (
                      <div className="inline-flex items-center gap-1">
                        <Button
                          variant="default"
                          size="sm"
                          disabled={writingJobIds.has(finding.job_id)}
                          onClick={() => updateLeadStatus(finding.job_id, "clear")}
                          title="Click to revert / undo pitched"
                        >
                          Pitched ✓
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={writingJobIds.has(finding.job_id)}
                          onClick={() => updateLeadStatus(finding.job_id, "save")}
                          title="Move back to Saved"
                        >
                          Move to Saved
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={writingJobIds.has(finding.job_id)}
                          onClick={() => updateLeadStatus(finding.job_id, "clear")}
                          title="Undo pitched and return to New"
                        >
                          Undo
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={writingJobIds.has(finding.job_id)}
                        onClick={() => updateLeadStatus(finding.job_id, "pitched")}
                      >
                        Mark pitched
                      </Button>
                    )}

                    <Button

                      variant={finding.user_status === "won" ? "default" : "outline"}

                      size="sm"

                      disabled={writingJobIds.has(finding.job_id)}

                      onClick={() =>

                        updateLeadStatus(

                          finding.job_id,

                          finding.user_status === "won" ? "clear" : "won",

                        )

                      }

                    >

                      {finding.user_status === "won" ? "Won ✓" : "Mark won"}

                    </Button>

                    <div className="inline-flex flex-wrap items-center gap-1">
                      <Button
                        variant={finding.user_status === "skip" ? "outline" : "ghost"}
                        size="sm"
                        disabled={writingJobIds.has(finding.job_id)}
                        onClick={() =>
                          updateLeadStatus(
                            finding.job_id,
                            finding.user_status === "skip" ? "clear" : "skip",
                          )
                        }
                      >
                        {finding.user_status === "skip" ? "Restore" : "Skip"}
                      </Button>
                      {finding.user_status !== "skip" && (
                        <details className="relative">
                          <summary className="cursor-pointer list-none rounded px-1.5 py-1 text-[11px] text-[var(--text-muted)] hover:bg-[var(--surface-sunken)]">
                            reason
                          </summary>
                          <div className="absolute right-0 z-20 mt-1 flex min-w-[11rem] flex-col gap-1 rounded-md border border-[var(--border)] bg-[var(--surface)] p-1 shadow-md">
                            {SKIP_REASONS.map((reason) => (
                              <button
                                key={reason.id}
                                type="button"
                                className="rounded px-2 py-1 text-left text-[11px] hover:bg-[var(--surface-sunken)]"
                                onClick={() =>
                                  updateLeadStatus(finding.job_id, "skip", {
                                    reason: reason.id,
                                  })
                                }
                              >
                                {reason.label}
                              </button>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>

                    <Button
                      variant="ghost"
                      size="sm"
                      title="Hide this source from future ranking (adds to Hunt Rules exclusions)"
                      onClick={() => {
                        startTransition(async () => {
                          try {
                            await postMatchFeedback({
                              job_id: finding.job_id,
                              kind: "hide_source",
                              reason: `hide_source:${finding.source_name}`,
                            });
                            setSubmitMessage(
                              `Hidden source “${finding.source_name}” — added to exclusions.`,
                            );
                            await load(keywords, focusOverride, true);
                          } catch (err) {
                            setError(
                              err instanceof Error ? err.message : "Could not hide source",
                            );
                          }
                        });
                      }}
                    >
                      Hide source
                    </Button>

                    <Button

                      variant="ghost"

                      size="sm"

                      className="text-[var(--text-muted)] hover:text-[var(--danger)]"

                      title="Report listing as closed or dead link"

                      onClick={() => handleReportExpired(finding.job_id)}

                    >

                      Dead link

                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-[var(--text-muted)]"
                      title="Queue for human trust review (not an automatic exclusion)"
                      onClick={() => handleTrustReport(finding.job_id)}
                    >
                      Flag concern
                    </Button>

                  </>

                ) : null}

                {finding.action === "draft_bid" ? (

                  <Button variant="secondary" size="sm" onClick={() => makeDraft(finding.job_id)}>

                    Draft bid

                  </Button>

                ) : null}

              </div>

            </Card>

          ))}



          {!pending && data && visibleItems.length === 0 && !error ? (

            <EmptyState

              title={data.total_scanned === 0 ? "No opportunities yet" : "No leads in this view"}

              description={

                data.total_scanned === 0

                  ? "Hunters are still filling the pool (or the backend was paused). Set Hunt Rules and refresh inventory from the Desk — empty is expected until the first successful hunt."

                  : sourceFilter !== "all" || statusFilter !== "all" || search

                    ? "Try clearing filters or search."

                    : "Widen Hunt Rules keywords, or turn off Freelance focus."

              }

              actionHref="/preferences?tab=matching"

              actionLabel="Edit Hunt Rules"

              secondaryHref="/"

              secondaryLabel="Desk"

            />

          ) : null}

        </div>



        <aside className="hidden xl:block">

          <div className="sticky top-20 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-5">

            {selected ? (

              <div className="space-y-4">

                <div>

                  <h3

                    className="text-xl text-[var(--text)]"

                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}

                  >

                    {selected.title}

                  </h3>

                  <p className="mt-1 text-sm text-[var(--text-secondary)]">

                    {[selected.company, selected.source_label || selected.source_name].filter(Boolean).join(" · ")}

                  </p>

                </div>

                <MatchScoreBar score={selected.fit_score ?? selected.score} />
                {selected.why_shown ? (
                  <p className="mt-2 text-xs text-[var(--text-muted)]">{selected.why_shown}</p>
                ) : null}
                {selected.explanation?.confidence_note ? (
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                    {selected.explanation.confidence_note}
                  </p>
                ) : null}

                <p className="text-xs text-[var(--text-muted)]">

                  Match scores are heuristic fit estimates from Hunt Rules — not calibrated probabilities or verified guarantees.

                </p>

                {selected.description_excerpt ? (

                  <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{selected.description_excerpt}</p>

                ) : (

                  <p className="text-sm text-[var(--text-muted)]">Full description lives on the original listing.</p>

                )}

                {selected.matched_keywords?.length ? (

                  <div>

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">

                      Matched skills

                    </p>

                    <div className="flex flex-wrap gap-1.5">

                      {selected.matched_keywords.map((kw) => (

                        <Badge key={kw} variant="outline">

                          {kw}

                        </Badge>

                      ))}

                    </div>

                  </div>

                ) : null}

                {selected.red_flags?.length ? (

                  <div>

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--danger)] uppercase">Risks</p>

                    <ul className="space-y-1 text-sm text-[var(--danger)]">

                      {selected.red_flags.map((flag) => (

                        <li key={flag}>{flag}</li>

                      ))}

                    </ul>

                  </div>

                ) : null}

                {selected.trust ? (
                  <div className="space-y-3 rounded-md border border-white/10 bg-white/[0.02] p-3">
                    <p className="text-xs font-semibold tracking-wide text-[var(--mute)] uppercase">
                      Due diligence (not a verdict)
                    </p>
                    <p className="text-[11px] text-[var(--fog)]">
                      {selected.trust.disclaimer ||
                        "Indicators assist review. Unknown companies are not marked as scams."}
                    </p>
                    {selected.trust.extraction ? (
                      <div className="text-xs text-[var(--fog)]">
                        <span className="text-[var(--paper)]">Work type:</span>{" "}
                        {selected.trust.extraction.work_type || "unknown"}
                        {selected.trust.extraction.ambiguous_or_missing?.length ? (
                          <span>
                            {" "}
                            · Missing: {selected.trust.extraction.ambiguous_or_missing.slice(0, 4).join(", ")}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                    {selected.trust.employer?.company_identity_status ? (
                      <div className="text-xs text-[var(--fog)]">
                        Employer: {selected.trust.employer.company_name || "unknown"} (
                        {selected.trust.employer.company_identity_status})
                      </div>
                    ) : null}
                    {selected.trust.risk_indicators?.length ? (
                      <ul className="space-y-2 text-xs text-[var(--fog)]">
                        {selected.trust.risk_indicators.slice(0, 4).map((ind) => (
                          <li key={ind.code}>
                            <span className="text-[var(--paper)]">{ind.label}</span>
                            <span className="text-[var(--mute)]"> · {ind.severity}</span>
                            <div className="mt-0.5">{ind.what_to_verify}</div>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {selected.trust.due_diligence?.length ? (
                      <ul className="space-y-1 text-[11px] text-[var(--mute)]">
                        {selected.trust.due_diligence.slice(0, 3).map((item) => (
                          <li key={item.id}>• {item.title}</li>
                        ))}
                      </ul>
                    ) : null}
                    {selected.trust.evidence?.note ? (
                      <p className="text-[10px] text-[var(--mute)]">{selected.trust.evidence.note}</p>
                    ) : null}
                  </div>
                ) : null}

                {selected.application ? (

                  <div className="rounded-md border border-[var(--accent)]/30 bg-[var(--accent-muted)] p-3">

                    <div className="flex items-center justify-between">

                      <p className="text-xs font-semibold tracking-wide text-[var(--accent)] uppercase">

                        Your Pitch ({selected.application.status})

                      </p>

                      {selected.application.bid_amount ? (

                        <span className="text-xs font-semibold text-[var(--text)]">

                          ${selected.application.bid_amount.toLocaleString()} {selected.application.currency || "USD"}

                        </span>

                      ) : null}

                    </div>

                    <p className="mt-2 text-xs text-[var(--text-secondary)] whitespace-pre-line line-clamp-4">

                      {selected.application.proposal}

                    </p>

                  </div>

                ) : null}

                <Button

                  className="w-full"

                  onClick={() => openSafeExternalUrl(selected.apply_url || selected.url)}

                >

                  Open original

                </Button>

              </div>

            ) : (

              <div>

                <h3 className="text-lg font-semibold text-[var(--text)]">Opportunity detail</h3>

                <p className="mt-2 text-sm text-[var(--text-muted)]">

                  Select a lead to inspect match signals, risks, and source attribution.

                </p>

              </div>

            )}

          </div>

        </aside>

      </div>



      <AnimatePresence>

        {drawerOpen ? (

          <>

            <motion.button

              type="button"

              aria-label="Close draft drawer"

              initial={{ opacity: 0 }}

              animate={{ opacity: 1 }}

              exit={{ opacity: 0 }}

              className="fixed inset-0 z-40 bg-black/60"

              onClick={closeDraft}

            />

            <motion.aside

              role="dialog"

              aria-modal="true"

              aria-labelledby="draft-drawer-title"

              initial={{ x: "100%" }}

              animate={{ x: 0 }}

              exit={{ x: "100%" }}

              transition={{ type: "spring", stiffness: 320, damping: 32 }}

              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-md)]"

            >

              <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-6 py-5">

                <div>

                  <h2

                    id="draft-drawer-title"

                    className="text-2xl"

                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}

                  >

                    Draft bid

                  </h2>

                  <p className="mt-1 text-sm text-[var(--text-muted)]">

                    {draftMeta?.title} · {draftMeta?.source_name} · {form.submit_mode}

                  </p>

                </div>

                <Button type="button" variant="ghost" onClick={closeDraft}>

                  Close

                </Button>

              </div>

              <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">

                <p className="text-sm text-[var(--text-secondary)]">{draftMeta?.disclaimer}</p>

                {sanitizeEmailAddress(draftMeta?.apply_email || form.apply_email) ? (
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[var(--accent)]/30 bg-[var(--accent-muted)] px-3 py-2 text-xs">
                    <span className="font-medium text-[var(--text)]">
                      Direct contact detected:{" "}
                      <span className="font-semibold text-[var(--accent)]">
                        {sanitizeEmailAddress(draftMeta?.apply_email || form.apply_email)}
                      </span>
                    </span>
                    <span className="text-[var(--text-muted)]">1-click email pre-fill ready</span>
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="inline-flex rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-1">
                    <button
                      type="button"
                      onClick={() => {
                        setPitchKind("initial");
                        if (draftMeta?.initial_draft) {
                          setForm((curr) => ({
                            ...curr,
                            proposal: draftMeta.initial_draft || curr.proposal,
                            email_subject: draftMeta.email_subject || curr.email_subject,
                          }));
                        }
                      }}
                      className={cn(
                        "rounded-md px-3 py-1 text-xs font-semibold transition-all",
                        pitchKind === "initial"
                          ? "bg-[var(--accent)] text-[var(--accent-foreground)] shadow-sm"
                          : "text-[var(--text-muted)] hover:text-[var(--text)]"
                      )}
                    >
                      Initial Pitch
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setPitchKind("followup");
                        if (draftMeta?.followup_draft) {
                          setForm((curr) => ({
                            ...curr,
                            proposal: draftMeta.followup_draft || curr.proposal,
                            email_subject: draftMeta.title
                              ? `Following up: ${draftMeta.title}`
                              : "Following up",
                          }));
                        }
                      }}
                      className={cn(
                        "rounded-md px-3 py-1 text-xs font-semibold transition-all",
                        pitchKind === "followup"
                          ? "bg-[var(--accent)] text-[var(--accent-foreground)] shadow-sm"
                          : "text-[var(--text-muted)] hover:text-[var(--text)]"
                      )}
                    >
                      Follow-Up Bump
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={handleCopyPitch}>
                      {copiedPitch ? <Check className="size-3.5 text-[var(--success)]" /> : <Copy className="size-3.5" />}
                      {copiedPitch ? "Pitch copied!" : "Copy pitch"}
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={handleOpenGmail}>
                      <Mail className="size-3.5" />
                      Open in Gmail
                    </Button>
                    <Button type="button" variant="ghost" size="sm" onClick={handleOpenMailApp}>
                      Open Mail App
                    </Button>
                  </div>
                </div>

                <label className="sd-label">

                  <span>Proposal</span>

                  <textarea

                    value={form.proposal}

                    onChange={(event) => setForm((current) => ({ ...current, proposal: event.target.value }))}

                    rows={10}

                    className="sd-input"

                  />

                </label>

                <div className="grid gap-4 sm:grid-cols-3">

                  <label className="sd-label">

                    <span>Bid amount</span>

                    <input

                      type="number"

                      value={form.bid_amount ?? ""}

                      onChange={(event) =>

                        setForm((current) => ({

                          ...current,

                          bid_amount: event.target.value === "" ? null : Number(event.target.value),

                        }))

                      }

                      className="sd-input"

                    />

                  </label>

                  <label className="sd-label">

                    <span>Currency</span>

                    <input

                      value={form.currency}

                      onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))}

                      className="sd-input"

                    />

                  </label>

                  <label className="sd-label">

                    <span>Delivery days</span>

                    <input

                      type="number"

                      value={form.delivery_days ?? ""}

                      onChange={(event) =>

                        setForm((current) => ({

                          ...current,

                          delivery_days: event.target.value === "" ? null : Number(event.target.value),

                        }))

                      }

                      className="sd-input"

                    />

                  </label>

                </div>

                <label className="sd-label">

                  <span>Milestone plan</span>

                  <textarea

                    value={form.milestone_plan || ""}

                    onChange={(event) => setForm((current) => ({ ...current, milestone_plan: event.target.value }))}

                    rows={3}

                    className="sd-input"

                  />

                </label>

                <p className="text-sm text-[var(--text-muted)]">

                  {isExternalApply

                    ? "Confirm saves your draft and opens the listing. You stay in control."

                    : canDirectSubmit

                      ? "Review the draft, then confirm. Signal Desk only sends after this click."

                      : "Direct submit is unavailable for this source. Open the listing to apply."}

                </p>

              </div>

              <div className="flex flex-wrap gap-3 border-t border-[var(--border)] px-6 py-4">

                {canDirectSubmit || isExternalApply ? (

                  <Button type="button" disabled={pending} onClick={confirmSubmit}>

                    {pending

                      ? "Working…"

                      : isExternalApply

                        ? "Confirm draft & open listing"

                        : "Confirm & submit"}

                  </Button>

                ) : null}

                {form.project_url ? (

                  <Button variant="outline" onClick={() => openSafeExternalUrl(form.project_url)}>

                    Open listing

                  </Button>

                ) : null}

              </div>

            </motion.aside>

          </>

        ) : null}

      </AnimatePresence>

    </div>

  );

}



export default function LeadsPage() {

  return (

    <Suspense

      fallback={

        <div className="flex flex-1 flex-col gap-6">

          <Skeleton className="h-10 w-64" />

          <Skeleton className="h-40 w-full" />

          <p className="text-[var(--text-muted)]">Loading leads…</p>

        </div>

      }

    >

      <LeadsPageInner />

    </Suspense>

  );

}

