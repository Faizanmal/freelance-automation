"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { getApiBase, getToken, healthLive, listJobs, scrapeJobs, type Job } from "@/lib/api";

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [apiStatus, setApiStatus] = useState("checking");
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const refresh = () => {
    startTransition(async () => {
      try {
        setError(null);
        const [health, data] = await Promise.all([healthLive(), listJobs({ limit: 8 })]);
        setApiStatus(health.status);
        setJobs(data.items);
        setTotal(data.total);
      } catch (err) {
        setApiStatus("offline");
        setError(err instanceof Error ? err.message : "API unavailable");
      }
    });
  };

  useEffect(() => {
    refresh();
  }, []);

  const runScrape = () => {
    if (!getToken()) {
      window.location.href = "/auth";
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        setScrapeStatus("Scraping public boards…");
        const result = await scrapeJobs(["remoteok", "arbeitnow", "himalayas", "jobicy"], 40, false);
        setScrapeStatus(
          `Fetched ${result.total_fetched} · ingested ${result.total_ingested} · merged ${result.total_merged} · skipped ${result.total_skipped}`,
        );
        const data = await listJobs({ limit: 8 });
        setJobs(data.items);
        setTotal(data.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scrape failed");
        setScrapeStatus(null);
      }
    });
  };

  return (
    <main className="flex flex-1 flex-col gap-16">
      <section className="relative overflow-hidden rounded-[2rem] border border-white/10 px-6 py-14 md:px-12 md:py-20">
        <div
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            backgroundImage:
              "linear-gradient(120deg, rgba(198,242,92,0.08), transparent 40%), url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
          }}
        />
        <div className="relative max-w-3xl">
          <h1
            className="text-5xl leading-[1.05] tracking-tight text-[var(--paper)] md:text-7xl"
            style={{ fontFamily: "var(--font-display), Georgia, serif" }}
          >
            Signal Desk
          </h1>
          <p className="mt-5 max-w-xl text-lg text-[var(--fog)]">
            Live remote and freelance leads, scored for fit and freshness, with proposal drafts — not another generic job board.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/pricing"
              className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]"
            >
              See pricing
            </Link>
            <Link
              href="/auth"
              className="rounded-full border border-white/20 px-5 py-2.5 text-[var(--paper)] hover:border-[var(--signal)]/60"
            >
              Start free
            </Link>
            <button
              type="button"
              onClick={runScrape}
              disabled={pending}
              className="rounded-full border border-white/10 px-5 py-2.5 text-[var(--fog)] disabled:opacity-60"
            >
              {pending ? "Working…" : "Pull live jobs"}
            </button>
          </div>
          <p className="mt-4 text-sm text-[var(--mute)]">
            API {getApiBase()} · status <span className="text-[var(--signal)]">{apiStatus}</span>
            {scrapeStatus ? ` · ${scrapeStatus}` : null}
          </p>
          {error ? <p className="mt-2 text-sm text-[var(--ember)]">{error}</p> : null}
        </div>
      </section>

      <section className="grid gap-10 md:grid-cols-3">
        {[
          {
            title: "Pull",
            body: "RemoteOK, Arbeitnow, Himalayas, Jobicy on Free. Upwork, Freelancer, and SerpAPI discovery on Pro.",
          },
          {
            title: "Findings",
            body: "Ranked leads with freelance focus — contract/marketplace boosts, full-time noise downranked, draft / watch / skip.",
          },
          {
            title: "Draft",
            body: "Generate a proposal draft you review before sending. Signal Desk never auto-submits.",
          },
        ].map((item) => (
          <div key={item.title} className="border-t border-white/10 pt-5">
            <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              {item.title}
            </h2>
            <p className="mt-3 text-[var(--fog)]">{item.body}</p>
          </div>
        ))}
      </section>

      <section>
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Latest in the desk
            </h2>
            <p className="mt-1 text-sm text-[var(--mute)]">{total} jobs stored</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <Link href="/findings" className="text-[var(--signal)]">
              Lead findings
            </Link>
            <Link href="/jobs" className="text-[var(--signal)]">
              Browse all
            </Link>
          </div>
        </div>
        <div className="space-y-3">
          {jobs.length === 0 ? (
            <p className="text-[var(--mute)]">No jobs yet. Sign in and pull live jobs to seed the desk.</p>
          ) : (
            jobs.map((job) => (
              <a
                key={job.id}
                href={job.url}
                target="_blank"
                rel="noreferrer"
                className="block border-b border-white/10 py-4 transition hover:border-[var(--signal)]/40"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-lg text-[var(--paper)]">{job.title}</h3>
                  <span className="text-xs tracking-wide text-[var(--mute)] uppercase">{job.source_name}</span>
                </div>
                <p className="mt-1 text-sm text-[var(--fog)]">
                  {[job.company, job.location].filter(Boolean).join(" · ") || "Remote opportunity"}
                </p>
              </a>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
