"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, useTransition } from "react";
import {
  getAuthFindings,
  getDemoFindings,
  getToken,
  type LeadFinding,
  type LeadFindingsResponse,
} from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const DEFAULT_KEYWORDS = "python,react,fastapi,typescript,remote";

const ACTION_LABEL: Record<LeadFinding["action"], string> = {
  draft_bid: "Draft bid",
  watch: "Watch",
  skip: "Skip",
};

export default function FindingsPage() {
  const router = useRouter();
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);
  const [freelanceFocus, setFreelanceFocus] = useState(true);
  const [data, setData] = useState<LeadFindingsResponse | null>(null);
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
        setError(err instanceof Error ? err.message : "Failed to load findings");
        setData(null);
      }
    });
  }, []);

  useEffect(() => {
    load(DEFAULT_KEYWORDS, true);
  }, [load]);

  return (
    <motion.main 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-8"
    >
      <section>
        <motion.h1 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl" 
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Lead findings
        </motion.h1>
        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="mt-2 max-w-2xl text-[var(--fog)]"
        >
          Source-aware digest for freelancers — boost marketplace and contract-friendly leads, downrank
          full-time employee noise, and show the freelance benefits that matter.
        </motion.p>
      </section>

      <div className="flex flex-wrap items-center gap-4 border-b border-white/10 pb-6">
        <label className="flex items-center gap-2 text-sm text-[var(--paper)] font-medium cursor-pointer">
          <input
            type="checkbox"
            checked={freelanceFocus}
            onChange={(event) => {
              const next = event.target.checked;
              setFreelanceFocus(next);
              load(keywords, next);
            }}
            className="size-4 accent-[var(--signal)] rounded"
          />
          Freelance focus
        </label>
        <p className="text-sm text-[var(--mute)]">
          Prefers Freelancer/Upwork and contract signals over salary/full-time boards
        </p>
      </div>

      {!authed ? (
        <motion.form
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex flex-wrap gap-3 rounded-2xl bg-white/5 p-3 backdrop-blur-md border border-white/10"
          onSubmit={(event) => {
            event.preventDefault();
            load(keywords, freelanceFocus);
          }}
        >
          <input
            value={keywords}
            onChange={(event) => setKeywords(event.target.value)}
            className="min-w-[260px] flex-1 rounded-full border border-white/10 bg-black/40 px-5 py-2.5 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60"
            placeholder="python, fastapi, next.js"
          />
          <Button type="submit" disabled={pending}>
            {pending ? "Working…" : "Refresh findings"}
          </Button>
        </motion.form>
      ) : (
        <div className="flex flex-wrap items-center gap-4">
          <Button
            type="button"
            onClick={() => load(keywords, freelanceFocus)}
            disabled={pending}
          >
            {pending ? "Working…" : "Refresh findings"}
          </Button>
          <p className="text-sm text-[var(--mute)]">Using your saved preferences</p>
        </div>
      )}

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}

      {data ? (
        <motion.section 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="border border-white/10 bg-black/20 rounded-2xl p-4 text-sm text-[var(--fog)]"
        >
          <p>
            <span className="text-[var(--paper)]">Scanned {data.total_scanned}</span> · matched {data.total_matched} · showing {data.total_findings}
            {data.freelance_focus ? " · freelance focus on" : " · all matches"}
            {data.keywords.length ? ` · keywords ${data.keywords.join(", ")}` : ""}
          </p>
          <div className="mt-3 flex gap-3">
            <span className="px-2 py-1 rounded bg-white/10 text-[var(--paper)]">Draft: {data.action_counts.draft_bid}</span>
            <span className="px-2 py-1 rounded bg-[var(--signal)]/10 text-[var(--signal)]">Watch: {data.action_counts.watch}</span>
            <span className="px-2 py-1 rounded bg-red-400/10 text-red-400/80">Skip: {data.action_counts.skip}</span>
          </div>
        </motion.section>
      ) : null}

      <motion.div layout className="grid gap-6">
        <AnimatePresence mode="popLayout">
          {(data?.items || []).map((finding, index) => (
            <Card 
              key={finding.job_id} 
              className="flex flex-col p-6"
              initial={{ opacity: 0, scale: 0.98, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.1, 0.6) }}
            >
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <h2 className="text-xl font-medium text-[var(--paper)]">{finding.title}</h2>
                <div className="flex items-center gap-2">
                  {typeof finding.freelance_fit === "number" ? (
                    <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-medium tracking-wider text-[var(--mute)] border border-white/10 uppercase">
                      Freelance: {Math.round(finding.freelance_fit * 100)}%
                    </span>
                  ) : null}
                  <span className="rounded-full bg-[var(--signal)]/15 px-2.5 py-1 text-[11px] font-medium tracking-wider text-[var(--signal)] border border-[var(--signal)]/20 uppercase">
                    Match: {Math.round(finding.score * 100)}%
                  </span>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium tracking-wider border uppercase ${
                    finding.action === "draft_bid" ? "bg-[var(--signal)] text-[var(--ink)] border-[var(--signal)]" : 
                    finding.action === "watch" ? "bg-blue-400/15 text-blue-300 border-blue-400/20" : 
                    "bg-red-400/15 text-red-300 border-red-400/20"
                  }`}>
                    {ACTION_LABEL[finding.action]}
                  </span>
                </div>
              </div>
              
              <p className="mb-4 text-sm font-medium text-[var(--fog)]">
                {[finding.company, finding.source_label || finding.source_attribution || finding.source_name]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              
              <div className="bg-black/30 p-4 rounded-xl border border-white/5 mb-4 space-y-3">
                <p className="text-sm leading-relaxed text-[var(--paper)]">{finding.why}</p>
                {finding.freelance_benefits_line ? (
                  <p className="text-sm text-[var(--signal)] flex items-start gap-2">
                    <span className="shrink-0 mt-0.5">✦</span>
                    <span>{finding.freelance_benefits_line}</span>
                  </p>
                ) : null}
              </div>

              <div className="grid md:grid-cols-2 gap-4 mb-6">
                {finding.signals.length > 0 ? (
                  <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                    <p className="text-xs font-semibold tracking-wide text-[var(--paper)] uppercase mb-2">Positive Signals</p>
                    <ul className="space-y-1.5 text-sm text-[var(--fog)]">
                      {finding.signals.map((signal) => (
                        <li key={signal} className="flex items-start gap-2">
                          <span className="text-[var(--signal)] mt-0.5">✓</span>
                          <span>{signal}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {finding.risks.length > 0 ? (
                  <div className="bg-red-400/5 rounded-xl p-4 border border-red-400/10">
                    <p className="text-xs font-semibold tracking-wide text-[var(--paper)] uppercase mb-2">Watchouts</p>
                    <ul className="space-y-1.5 text-sm text-red-200">
                      {finding.risks.map((risk) => (
                        <li key={risk} className="flex items-start gap-2">
                          <span className="text-red-400 mt-0.5">!</span>
                          <span>{risk}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>

              <div className="mt-auto flex flex-wrap gap-3 pt-4 border-t border-white/5">
                {finding.action === "draft_bid" ? (
                  <Button
                    variant="default"
                    className="py-2 text-sm px-6"
                    onClick={() => {
                      if (!getToken()) {
                        router.push("/auth");
                        return;
                      }
                      router.push(`/matches?job=${finding.job_id}`);
                    }}
                  >
                    Continue on Matches
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  className="py-2 text-sm px-6"
                  onClick={() => window.open(finding.apply_url || finding.url, "_blank")}
                >
                  Open on source
                </Button>
              </div>
            </Card>
          ))}
        </AnimatePresence>
        
        {!pending && data && data.items.length === 0 && !error ? (
          <p className="text-sm text-[var(--mute)] bg-black/20 p-6 rounded-2xl border border-white/5 text-center mt-4">
            No freelance-friendly findings yet.{" "}
            <Link href="/sources" className="text-[var(--signal)] hover:underline">
              Pull Freelancer or public boards
            </Link>
            , or turn off Freelance focus.
          </p>
        ) : null}
      </motion.div>
    </motion.main>
  );
}
