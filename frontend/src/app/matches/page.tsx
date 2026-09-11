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

  return (
    <main className="flex flex-1 flex-col gap-8">
      <section>
        <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Lead matches
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--fog)]">
          Ranked by skill fit, freshness, client/budget signals, and red-flag checks — not keyword spam alone.
        </p>
      </section>

      <form
        className="flex flex-wrap gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          load(keywords);
        }}
      >
        <input
          value={keywords}
          onChange={(event) => setKeywords(event.target.value)}
          className="min-w-[260px] flex-1 rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          placeholder="python, fastapi, next.js"
        />
        <button type="submit" className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]">
          {pending ? "Working…" : "Score leads"}
        </button>
      </form>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {submitMessage ? <p className="text-sm text-[var(--signal)]">{submitMessage}</p> : null}

      {draftMeta && activeJobId ? (
        <section className="space-y-4 border border-white/10 bg-black/20 p-5">
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

          <label className="grid gap-1 text-sm">
            <span className="text-[var(--mute)]">Proposal</span>
            <textarea
              value={form.proposal}
              onChange={(event) => setForm((current) => ({ ...current, proposal: event.target.value }))}
              rows={10}
              className="rounded-2xl border border-white/15 bg-black/30 px-4 py-3 outline-none focus:border-[var(--signal)]/50"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-3">
            <label className="grid gap-1 text-sm">
              <span className="text-[var(--mute)]">Bid amount</span>
              <input
                type="number"
                value={form.bid_amount ?? ""}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    bid_amount: event.target.value === "" ? null : Number(event.target.value),
                  }))
                }
                className="rounded-full border border-white/15 bg-black/30 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
              />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-[var(--mute)]">Currency</span>
              <input
                value={form.currency}
                onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))}
                className="rounded-full border border-white/15 bg-black/30 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
              />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-[var(--mute)]">Delivery days</span>
              <input
                type="number"
                value={form.delivery_days ?? ""}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    delivery_days: event.target.value === "" ? null : Number(event.target.value),
                  }))
                }
                className="rounded-full border border-white/15 bg-black/30 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
              />
            </label>
          </div>

          <label className="grid gap-1 text-sm">
            <span className="text-[var(--mute)]">Milestone plan</span>
            <textarea
              value={form.milestone_plan || ""}
              onChange={(event) => setForm((current) => ({ ...current, milestone_plan: event.target.value }))}
              rows={3}
              className="rounded-2xl border border-white/15 bg-black/30 px-4 py-3 outline-none focus:border-[var(--signal)]/50"
            />
          </label>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={pending}
              onClick={confirmSubmit}
              className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              {pending ? "Submitting…" : "Confirm & submit"}
            </button>
            {form.project_url ? (
              <a
                href={form.project_url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-white/20 px-5 py-2.5 text-sm"
              >
                Open listing
              </a>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="space-y-4">
        {items.map((job) => (
          <article key={job.id} className="border-b border-white/10 pb-5">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-xl">{job.title}</h2>
              <span className="rounded-full bg-[var(--signal)]/15 px-3 py-1 text-sm text-[var(--signal)]">
                {Math.round((job.match_score || 0) * 100)}% lead score
              </span>
            </div>
            <p className="mt-1 text-sm text-[var(--fog)]">
              {[job.company, job.source_label || job.source_attribution || job.source_name].filter(Boolean).join(" · ")}
            </p>
            <p className="mt-2 text-sm text-[var(--mute)]">
              fit: {(job.matched_keywords || []).join(", ") || "—"}
              {typeof job.freshness_score === "number" ? ` · freshness ${Math.round(job.freshness_score * 100)}%` : ""}
              {typeof job.client_quality_score === "number"
                ? ` · client ${Math.round(job.client_quality_score * 100)}%`
                : ""}
            </p>
            {(job.red_flags || []).length > 0 ? (
              <p className="mt-1 text-sm text-[var(--ember)]">flags: {(job.red_flags || []).join(", ")}</p>
            ) : null}
            <p className="mt-3 text-sm text-[var(--mute)]">{job.description_excerpt || job.description}</p>
            <div className="mt-3 flex flex-wrap gap-4 text-sm">
              <a
                href={job.apply_url || job.url}
                target="_blank"
                rel="noreferrer"
                className="underline-offset-4 hover:underline"
              >
                Open on source
              </a>
              <button type="button" onClick={() => makeDraft(job.id)} className="text-[var(--signal)]">
                Fill apply form
              </button>
            </div>
          </article>
        ))}
        {!pending && items.length === 0 && !error ? (
          <p className="text-[var(--mute)]">No matches yet. Pull jobs from the desk, then adjust keywords.</p>
        ) : null}
      </div>
    </main>
  );
}
