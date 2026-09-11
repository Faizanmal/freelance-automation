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
    <main className="flex flex-1 flex-col gap-8">
      <section>
        <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Lead findings
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--fog)]">
          Source-aware digest for freelancers — boost marketplace and contract-friendly leads, downrank
          full-time employee noise, and show the freelance benefits that matter.
        </p>
      </section>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-[var(--fog)]">
          <input
            type="checkbox"
            checked={freelanceFocus}
            onChange={(event) => {
              const next = event.target.checked;
              setFreelanceFocus(next);
              load(keywords, next);
            }}
            className="size-4 accent-[var(--signal)]"
          />
          Freelance focus
        </label>
        <p className="text-sm text-[var(--mute)]">
          Prefers Freelancer/Upwork and contract signals over salary/full-time boards
        </p>
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
            className="min-w-[260px] flex-1 rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
            placeholder="python, fastapi, next.js"
          />
          <button type="submit" className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]">
            {pending ? "Working…" : "Refresh findings"}
          </button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => load(keywords, freelanceFocus)}
            className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]"
          >
            {pending ? "Working…" : "Refresh findings"}
          </button>
          <p className="text-sm text-[var(--mute)]">Using your saved preferences</p>
        </div>
      )}

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}

      {data ? (
        <section className="border-y border-white/10 py-4 text-sm text-[var(--fog)]">
          <p>
            Scanned {data.total_scanned} · matched {data.total_matched} · showing {data.total_findings}
            {data.freelance_focus ? " · freelance focus on" : " · all matches"}
            {data.keywords.length ? ` · keywords ${data.keywords.join(", ")}` : ""}
          </p>
          <p className="mt-1 text-[var(--mute)]">
            Draft {data.action_counts.draft_bid} · Watch {data.action_counts.watch} · Skip{" "}
            {data.action_counts.skip}
          </p>
        </section>
      ) : null}

      <div className="space-y-6">
        {(data?.items || []).map((finding) => (
          <article key={finding.job_id} className="border-b border-white/10 pb-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-xl text-[var(--paper)]">{finding.title}</h2>
              <span className="text-sm text-[var(--signal)]">
                {Math.round(finding.score * 100)}% · {ACTION_LABEL[finding.action]}
                {typeof finding.freelance_fit === "number"
                  ? ` · freelance ${Math.round(finding.freelance_fit * 100)}%`
                  : ""}
              </span>
            </div>
            <p className="mt-1 text-sm text-[var(--fog)]">
              {[finding.company, finding.source_label || finding.source_attribution || finding.source_name]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <p className="mt-3 text-[var(--paper)]">{finding.why}</p>
            {finding.freelance_benefits_line ? (
              <p className="mt-2 text-sm text-[var(--signal)]">{finding.freelance_benefits_line}</p>
            ) : null}

            {finding.signals.length > 0 ? (
              <div className="mt-3">
                <p className="text-xs tracking-wide text-[var(--mute)] uppercase">Signals</p>
                <ul className="mt-1 space-y-1 text-sm text-[var(--fog)]">
                  {finding.signals.map((signal) => (
                    <li key={signal}>{signal}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {finding.risks.length > 0 ? (
              <div className="mt-3">
                <p className="text-xs tracking-wide text-[var(--mute)] uppercase">Watchouts</p>
                <ul className="mt-1 space-y-1 text-sm text-[var(--ember)]">
                  {finding.risks.map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              <a
                href={finding.apply_url || finding.url}
                target="_blank"
                rel="noreferrer"
                className="underline-offset-4 hover:underline"
              >
                Open on source
              </a>
              {finding.action === "draft_bid" ? (
                <button
                  type="button"
                  className="text-[var(--signal)]"
                  onClick={() => {
                    if (!getToken()) {
                      router.push("/auth");
                      return;
                    }
                    router.push(`/matches?job=${finding.job_id}`);
                  }}
                >
                  Continue on Matches
                </button>
              ) : null}
            </div>
          </article>
        ))}
        {!pending && data && data.items.length === 0 && !error ? (
          <p className="text-[var(--mute)]">
            No freelance-friendly findings yet.{" "}
            <Link href="/sources" className="text-[var(--signal)]">
              Pull Freelancer or public boards
            </Link>
            , or turn off Freelance focus.
          </p>
        ) : null}
      </div>
    </main>
  );
}
