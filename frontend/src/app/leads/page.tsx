"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState, useTransition } from "react";
import {
  draftProposal,
  getAuthFindings,
  getDemoFindings,
  getToken,
  setLeadAction,
  submitApplication,
  type ApplyFormFields,
  type LeadFinding,
  type LeadFindingsResponse,
  type ProposalDraftResponse,
} from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const DEFAULT_KEYWORDS = "python,react,fastapi,typescript,remote";

const ACTION_LABEL: Record<LeadFinding["action"], string> = {
  draft_bid: "Draft",
  watch: "Watch",
  skip: "Skip",
};

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
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);
  const [freelanceFocus, setFreelanceFocus] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [data, setData] = useState<LeadFindingsResponse | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [draftMeta, setDraftMeta] = useState<ProposalDraftResponse | null>(null);
  const [form, setForm] = useState<ApplyFormFields>(emptyForm());
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [authed, setAuthed] = useState(false);

  const load = useCallback((value: string, focus: boolean) => {
    startTransition(async () => {
      try {
        setError(null);
        const token = getToken();
        setAuthed(Boolean(token));
        const response = token
          ? await getAuthFindings(10, focus)
          : await getDemoFindings(value, 10, focus);
        setData(response);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load leads";
        // Treat empty inventory as an empty state, not a hard error.
        if (/no jobs in the database/i.test(message) || /call post \/jobs\/scrape/i.test(message)) {
          setError(null);
          setData({
            generated_at: new Date().toISOString(),
            total_scanned: 0,
            total_matched: 0,
            total_findings: 0,
            freelance_focus: focus,
            action_counts: { draft_bid: 0, watch: 0, skip: 0 },
            keywords: value.split(",").map((part) => part.trim()).filter(Boolean),
            items: [],
          });
          return;
        }
        setError(message);
        setData(null);
      }
    });
  }, []);

  useEffect(() => {
    load(DEFAULT_KEYWORDS, true);
  }, [load]);

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
          });
        } catch (err) {
          setError(err instanceof Error ? err.message : "Draft failed");
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
          window.open(result.apply_url, "_blank", "noopener,noreferrer");
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

  const updateLeadStatus = (jobId: number, status: "save" | "skip" | "clear") => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        await setLeadAction(jobId, status);
        await load(keywords, freelanceFocus);
        setSubmitMessage(
          status === "save"
            ? "Lead saved"
            : status === "skip"
              ? "Lead skipped — hidden from default list"
              : "Lead status cleared",
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not update lead");
      }
    });
  };

  const sources = useMemo(() => {
    const names = new Set<string>();
    for (const item of data?.items || []) {
      if (item.source_name) names.add(item.source_name);
    }
    return Array.from(names).sort();
  }, [data]);

  const visibleItems = useMemo(() => {
    const items = [...(data?.items || [])].sort((a, b) => {
      const aScore = a.score * 0.7 + (a.freshness_score || 0) * 0.3;
      const bScore = b.score * 0.7 + (b.freshness_score || 0) * 0.3;
      return bScore - aScore;
    });
    if (sourceFilter === "all") return items;
    return items.filter((item) => item.source_name === sourceFilter);
  }, [data, sourceFilter]);

  const isExternalApply = form.submit_mode === "external_apply";
  const canDirectSubmit = form.submit_mode === "api_bid" || form.submit_mode === "email_apply";
  const inputClass =
    "w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60";
  const drawerOpen = Boolean(draftMeta && activeJobId);

  return (
    <main className="flex flex-1 flex-col gap-8">
      <section>
        <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Leads
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--fog)]">
          Ranked by fit and freshness. Open the original listing to pitch — Signal Desk never auto-submits.
        </p>
      </section>

      <div className="flex flex-wrap items-center gap-4 border-b border-white/10 pb-6">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--paper)]">
          <input
            type="checkbox"
            checked={freelanceFocus}
            onChange={(event) => {
              const next = event.target.checked;
              setFreelanceFocus(next);
              load(keywords, next);
            }}
            className="size-4 rounded accent-[var(--signal)]"
          />
          Freelance focus
        </label>
        <label className="flex items-center gap-2 text-sm text-[var(--fog)]">
          Source
          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value)}
            className="rounded-full border border-white/10 bg-black/40 px-3 py-1.5 outline-none focus:border-[var(--signal)]/50"
          >
            <option value="all">All sources</option>
            {sources.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!authed ? (
        <form
          className="flex flex-wrap gap-3 rounded-2xl border border-white/10 bg-white/5 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            load(keywords, freelanceFocus);
          }}
        >
          <input
            value={keywords}
            onChange={(event) => setKeywords(event.target.value)}
            className="min-w-[260px] flex-1 rounded-full border border-white/10 bg-black/40 px-5 py-2.5 outline-none focus:border-[var(--signal)]/50"
            placeholder="python, fastapi, next.js"
          />
          <Button type="submit" disabled={pending}>
            {pending ? "Working…" : "Refresh leads"}
          </Button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-4">
          <Button type="button" onClick={() => load(keywords, freelanceFocus)} disabled={pending}>
            {pending ? "Working…" : "Refresh leads"}
          </Button>
          <p className="text-sm text-[var(--mute)]">Using your saved preferences</p>
          <Link href="/preferences?tab=matching" className="text-sm text-[var(--signal)] hover:underline">
            Edit Hunt Rules
          </Link>
        </div>
      )}

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {submitMessage ? <p className="text-sm text-[var(--signal)]">{submitMessage}</p> : null}

      {data ? (
        <section className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-[var(--fog)]">
          <p>
            <span className="text-[var(--paper)]">Scanned {data.total_scanned}</span> · matched {data.total_matched} ·
            showing {visibleItems.length}
            {data.freelance_focus ? " · freelance focus on" : " · all matches"}
            {data.keywords.length ? ` · keywords ${data.keywords.join(", ")}` : ""}
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <span className="rounded bg-white/10 px-2 py-1 text-[var(--paper)]">
              Draft: {data.action_counts.draft_bid}
            </span>
            <span className="rounded bg-[var(--signal)]/10 px-2 py-1 text-[var(--signal)]">
              Watch: {data.action_counts.watch}
            </span>
            <span className="rounded bg-red-400/10 px-2 py-1 text-red-400/80">
              Skip: {data.action_counts.skip}
            </span>
          </div>
        </section>
      ) : null}

      <div className="grid gap-4">
        {visibleItems.map((finding) => (
          <Card key={finding.job_id} className="flex flex-col p-6">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <h2 className="text-xl font-medium text-[var(--paper)]">{finding.title}</h2>
              <div className="flex flex-wrap items-center gap-2">
                {typeof finding.freelance_fit === "number" ? (
                  <span className="rounded-full border border-white/10 bg-white/10 px-2.5 py-1 text-[11px] tracking-wider text-[var(--mute)] uppercase">
                    Freelance {Math.round(finding.freelance_fit * 100)}%
                  </span>
                ) : null}
                <span className="rounded-full border border-[var(--signal)]/20 bg-[var(--signal)]/15 px-2.5 py-1 text-[11px] tracking-wider text-[var(--signal)] uppercase">
                  Fit {Math.round(finding.score * 100)}%
                </span>
                <span
                  className={`rounded-full border px-2.5 py-1 text-[11px] tracking-wider uppercase ${
                    finding.action === "draft_bid"
                      ? "border-[var(--signal)] bg-[var(--signal)] text-[var(--ink)]"
                      : finding.action === "watch"
                        ? "border-blue-400/20 bg-blue-400/15 text-blue-300"
                        : "border-red-400/20 bg-red-400/15 text-red-300"
                  }`}
                >
                  {ACTION_LABEL[finding.action]}
                </span>
              </div>
            </div>

            <p className="mb-4 text-sm font-medium text-[var(--fog)]">
              {[finding.company, finding.source_label || finding.source_attribution || finding.source_name]
                .filter(Boolean)
                .join(" · ")}
            </p>

            <div className="mb-4 space-y-3 rounded-xl border border-white/5 bg-black/30 p-4">
              <p className="text-sm leading-relaxed text-[var(--paper)]">{finding.why}</p>
              {finding.freelance_benefits_line ? (
                <p className="text-sm text-[var(--signal)]">{finding.freelance_benefits_line}</p>
              ) : null}
            </div>

            <div className="mb-6 grid gap-4 md:grid-cols-2">
              {finding.signals.length > 0 ? (
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--paper)] uppercase">Signals</p>
                  <ul className="space-y-1.5 text-sm text-[var(--fog)]">
                    {finding.signals.map((signal) => (
                      <li key={signal}>+ {signal}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {finding.risks.length > 0 ? (
                <div className="rounded-xl border border-red-400/10 bg-red-400/5 p-4">
                  <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--paper)] uppercase">Watchouts</p>
                  <ul className="space-y-1.5 text-sm text-red-200">
                    {finding.risks.map((risk) => (
                      <li key={risk}>! {risk}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>

            <div className="mt-auto flex flex-wrap gap-3 border-t border-white/5 pt-4">
              <Button
                variant="default"
                className="px-6 py-2 text-sm"
                onClick={() => window.open(finding.apply_url || finding.url, "_blank")}
              >
                Open original
              </Button>
              {authed ? (
                <>
                  <Button
                    variant="outline"
                    className="px-6 py-2 text-sm"
                    onClick={() =>
                      updateLeadStatus(
                        finding.job_id,
                        finding.user_status === "save" ? "clear" : "save",
                      )
                    }
                  >
                    {finding.user_status === "save" ? "Unsave" : "Save"}
                  </Button>
                  <Button
                    variant="ghost"
                    className="px-6 py-2 text-sm"
                    onClick={() => updateLeadStatus(finding.job_id, "skip")}
                  >
                    Skip
                  </Button>
                </>
              ) : null}
              {finding.action === "draft_bid" ? (
                <Button variant="outline" className="px-6 py-2 text-sm" onClick={() => makeDraft(finding.job_id)}>
                  Draft bid
                </Button>
              ) : null}
            </div>
          </Card>
        ))}

        {!pending && data && visibleItems.length === 0 && !error ? (
          <div className="rounded-2xl border border-white/10 bg-black/20 p-8 text-center">
            <h3 className="text-xl text-[var(--paper)]" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              {data.total_scanned === 0 ? "No opportunities yet" : "No leads in this view"}
            </h3>
            <p className="mt-3 text-sm text-[var(--mute)]">
              {data.total_scanned === 0
                ? "Hunters are still filling the pool. Check back soon, or set Hunt Rules so new matches reach you."
                : sourceFilter !== "all"
                  ? "Try another hunter filter, or clear the source filter."
                  : "Widen Hunt Rules keywords, or turn off Freelance focus."}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-4 text-sm">
              <Link href="/preferences?tab=matching" className="text-[var(--signal)] hover:underline">
                Edit Hunt Rules
              </Link>
              <Link href="/jobs" className="text-[var(--signal)] hover:underline">
                Browse inventory
              </Link>
            </div>
          </div>
        ) : null}
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
              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-white/10 bg-[var(--ink)] shadow-2xl"
            >
              <div className="flex items-start justify-between gap-3 border-b border-white/10 px-6 py-5">
                <div>
                  <h2
                    id="draft-drawer-title"
                    className="text-2xl"
                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}
                  >
                    Draft bid
                  </h2>
                  <p className="mt-1 text-sm text-[var(--mute)]">
                    {draftMeta?.title} · {draftMeta?.source_name} · {form.submit_mode}
                  </p>
                </div>
                <Button type="button" variant="ghost" onClick={closeDraft}>
                  Close
                </Button>
              </div>
              <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
                <p className="text-sm text-[var(--fog)]">{draftMeta?.disclaimer}</p>
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--fog)]">Proposal</span>
                  <textarea
                    value={form.proposal}
                    onChange={(event) => setForm((current) => ({ ...current, proposal: event.target.value }))}
                    rows={10}
                    className={inputClass}
                  />
                </label>
                <div className="grid gap-4 sm:grid-cols-3">
                  <label className="grid gap-2 text-sm">
                    <span className="font-medium text-[var(--fog)]">Bid amount</span>
                    <input
                      type="number"
                      value={form.bid_amount ?? ""}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          bid_amount: event.target.value === "" ? null : Number(event.target.value),
                        }))
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span className="font-medium text-[var(--fog)]">Currency</span>
                    <input
                      value={form.currency}
                      onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))}
                      className={inputClass}
                    />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span className="font-medium text-[var(--fog)]">Delivery days</span>
                    <input
                      type="number"
                      value={form.delivery_days ?? ""}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          delivery_days: event.target.value === "" ? null : Number(event.target.value),
                        }))
                      }
                      className={inputClass}
                    />
                  </label>
                </div>
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--fog)]">Milestone plan</span>
                  <textarea
                    value={form.milestone_plan || ""}
                    onChange={(event) => setForm((current) => ({ ...current, milestone_plan: event.target.value }))}
                    rows={3}
                    className={inputClass}
                  />
                </label>
                <p className="text-sm text-[var(--mute)]">
                  {isExternalApply
                    ? "Confirm saves your draft and opens the listing. You stay in control."
                    : canDirectSubmit
                      ? "Review the draft, then confirm. Signal Desk only sends after this click."
                      : "Direct submit is unavailable for this source. Open the listing to apply."}
                </p>
              </div>
              <div className="flex flex-wrap gap-3 border-t border-white/10 px-6 py-4">
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
                  <Button variant="outline" onClick={() => window.open(form.project_url, "_blank")}>
                    Open listing
                  </Button>
                ) : null}
              </div>
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>
    </main>
  );
}

export default function LeadsPage() {
  return (
    <Suspense
      fallback={
        <main className="flex flex-1 flex-col gap-6">
          <p className="text-[var(--mute)]">Loading leads…</p>
        </main>
      }
    >
      <LeadsPageInner />
    </Suspense>
  );
}
