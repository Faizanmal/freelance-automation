"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, useTransition } from "react";
import {
  draftProposal,
  getDemoMatches,
  getToken,
  submitApplication,
  type ApplyFormFields,
  type Job,
  type ProposalDraftResponse,
} from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const DEFAULT_KEYWORDS = "python,react,fastapi,typescript,remote";

const emptyForm = (): ApplyFormFields => ({
  proposal: "",
  bid_amount: null,
  currency: "USD",
  delivery_days: 7,
  milestone_plan: "",
  milestone_percentage: 100,
  submit_mode: "unsupported",
});

export default function MatchesPage() {
  const router = useRouter();
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);
  const [items, setItems] = useState<Job[]>([]);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [draftMeta, setDraftMeta] = useState<ProposalDraftResponse | null>(null);
  const [form, setForm] = useState<ApplyFormFields>(emptyForm());
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const load = useCallback((value: string) => {
    startTransition(async () => {
      try {
        setError(null);
        const data = await getDemoMatches(value);
        setItems(data.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load matches");
        setItems([]);
      }
    });
  }, []);

  useEffect(() => {
    load(DEFAULT_KEYWORDS);
  }, [load]);

  const makeDraft = (jobId: number) => {
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
  };

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
            `Submitted via ${result.submit_mode} (status: ${result.status}${
              result.external_id ? `, id ${result.external_id}` : ""
            })`,
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Submit failed");
      }
    });
  };

  const inputClass = "w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60 shadow-inner";

  return (
    <motion.main 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-10"
    >
      <section>
        <motion.h1 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl" 
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Lead matches
        </motion.h1>
        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="mt-2 max-w-2xl text-[var(--fog)]"
        >
          Ranked by skill fit, freshness, client/budget signals, and red-flag checks — not keyword spam alone.
        </motion.p>
      </section>

      <motion.form
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex flex-wrap gap-3 rounded-2xl bg-white/5 p-3 backdrop-blur-md border border-white/10"
        onSubmit={(event) => {
          event.preventDefault();
          load(keywords);
        }}
      >
        <input
          value={keywords}
          onChange={(event) => setKeywords(event.target.value)}
          className="min-w-[260px] flex-1 rounded-full border border-white/10 bg-black/40 px-5 py-2.5 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60"
          placeholder="python, fastapi, next.js"
        />
        <Button type="submit" disabled={pending}>
          {pending ? "Working…" : "Score leads"}
        </Button>
      </motion.form>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {submitMessage ? <p className="text-sm text-[var(--signal)]">{submitMessage}</p> : null}

      <AnimatePresence>
        {draftMeta && activeJobId ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <Card className="p-8 space-y-6">
              <div>
                <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
                  Apply form
                </h2>
                <p className="mt-1 text-sm text-[var(--mute)]">
                  {draftMeta.title} · {draftMeta.source_name} · provider {draftMeta.provider} · mode{" "}
                  {form.submit_mode}
                </p>
                <p className="mt-2 text-sm text-[var(--fog)]">{draftMeta.disclaimer}</p>
              </div>

              <label className="grid gap-2 text-sm">
                <span className="text-[var(--fog)] font-medium">Proposal</span>
                <textarea
                  value={form.proposal}
                  onChange={(event) => setForm((current) => ({ ...current, proposal: event.target.value }))}
                  rows={10}
                  className={inputClass}
                />
              </label>

              <div className="grid gap-6 md:grid-cols-3">
                <label className="grid gap-2 text-sm">
                  <span className="text-[var(--fog)] font-medium">Bid amount</span>
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
                  <span className="text-[var(--fog)] font-medium">Currency</span>
                  <input
                    value={form.currency}
                    onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-2 text-sm">
                  <span className="text-[var(--fog)] font-medium">Delivery days</span>
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
                <span className="text-[var(--fog)] font-medium">Milestone plan</span>
                <textarea
                  value={form.milestone_plan || ""}
                  onChange={(event) => setForm((current) => ({ ...current, milestone_plan: event.target.value }))}
                  rows={3}
                  className={inputClass}
                />
              </label>

              <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-white/10">
                <Button
                  type="button"
                  disabled={pending}
                  onClick={confirmSubmit}
                >
                  {pending ? "Submitting…" : "Confirm & submit"}
                </Button>
                {form.project_url ? (
                  <Button
                    variant="outline"
                    onClick={() => window.open(form.project_url, "_blank")}
                  >
                    Open listing
                  </Button>
                ) : null}
              </div>
            </Card>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <motion.div layout className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        <AnimatePresence mode="popLayout">
          {items.map((job, index) => (
            <Card 
              key={job.id} 
              className="flex flex-col p-6"
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.05, 0.5) }}
            >
              <div className="mb-4 flex items-start justify-between gap-3">
                <h2 className="text-xl font-medium leading-tight text-[var(--paper)]">{job.title}</h2>
                <span className="shrink-0 rounded-full bg-[var(--signal)]/15 px-2 py-1 text-[11px] font-medium tracking-wider text-[var(--signal)] border border-[var(--signal)]/20 uppercase">
                  {Math.round((job.match_score || 0) * 100)}% fit
                </span>
              </div>
              <p className="mb-4 text-sm font-medium text-[var(--fog)]">
                {[job.company, job.source_label || job.source_attribution || job.source_name].filter(Boolean).join(" · ")}
              </p>
              
              <div className="mb-4 space-y-1.5 text-sm">
                <p className="text-[var(--mute)]">
                  <span className="text-[var(--fog)]">Matched:</span> {(job.matched_keywords || []).join(", ") || "—"}
                </p>
                <p className="text-[var(--mute)]">
                  {typeof job.freshness_score === "number" ? <span className="mr-3"><span className="text-[var(--fog)]">Freshness:</span> {Math.round(job.freshness_score * 100)}%</span> : null}
                  {typeof job.client_quality_score === "number" ? <span><span className="text-[var(--fog)]">Client:</span> {Math.round(job.client_quality_score * 100)}%</span> : null}
                </p>
                {(job.red_flags || []).length > 0 ? (
                  <p className="text-[var(--ember)] flex items-start gap-1">
                    <span className="text-red-400/80 font-medium">Flags:</span> 
                    <span>{(job.red_flags || []).join(", ")}</span>
                  </p>
                ) : null}
              </div>

              <p className="mb-6 line-clamp-4 flex-1 text-sm leading-relaxed text-[var(--mute)] bg-black/20 p-3 rounded-xl border border-white/5">
                {job.description_excerpt || job.description}
              </p>
              
              <div className="mt-auto flex flex-wrap gap-3 pt-4 border-t border-white/5">
                <Button 
                  variant="default"
                  className="flex-1 py-2 text-sm"
                  onClick={() => makeDraft(job.id)}
                >
                  Fill apply form
                </Button>
                <Button 
                  variant="outline"
                  className="flex-1 py-2 text-sm"
                  onClick={() => window.open(job.apply_url || job.url, "_blank")}
                >
                  Open on source
                </Button>
              </div>
            </Card>
          ))}
        </AnimatePresence>
      </motion.div>
      
      {!pending && items.length === 0 && !error ? (
        <p className="text-sm text-[var(--mute)] bg-black/20 p-6 rounded-2xl border border-white/5 text-center">
          No matches yet. Pull jobs from the desk, then adjust keywords.
        </p>
      ) : null}
    </motion.main>
  );
}
