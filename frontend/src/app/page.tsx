"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore, useTransition } from "react";
import {
  getApiBase,
  getAuthServerSnapshot,
  getAuthSnapshot,
  getToken,
  healthLive,
  listJobs,
  scrapeJobs,
  subscribeAuth,
  type Job,
} from "@/lib/api";
import { ActivationChecklist } from "@/components/activation-checklist";

export default function HomePage() {
  const router = useRouter();
  const authed = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthServerSnapshot);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [apiStatus, setApiStatus] = useState("checking");
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scraping, setScraping] = useState(false);
  const [, startTransition] = useTransition();

  const refresh = (isAuthed: boolean) => {
    startTransition(async () => {
      try {
        setError(null);
        if (isAuthed) {
          const [health, data] = await Promise.all([healthLive(), listJobs({ limit: 8 })]);
          setApiStatus(health.status);
          setJobs(data.items);
          setTotal(data.total);
          return;
        }
        const data = await listJobs({ limit: 8 });
        setJobs(data.items);
        setTotal(data.total);
        setApiStatus("ok");
      } catch (err) {
        setApiStatus("offline");
        setError(err instanceof Error ? err.message : "API unavailable");
      }
    });
  };

  useEffect(() => {
    refresh(authed);
  }, [authed]);

  const runScrape = () => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    setScraping(true);
    startTransition(async () => {
      try {
        setError(null);
        setScrapeStatus("Refreshing hunt inventory…");
        const result = await scrapeJobs(undefined, 40, false);
        setScrapeStatus(
          `Fetched ${result.total_fetched ?? 0} · ingested ${result.total_ingested ?? 0} · merged ${result.total_merged ?? 0} · skipped ${result.total_skipped ?? 0}`,
        );
        const data = await listJobs({ limit: 8 });
        setJobs(data.items);
        setTotal(data.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scrape failed");
        setScrapeStatus(null);
      } finally {
        setScraping(false);
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
            Set Hunt Rules. We find public freelance and contract posts outside crowded marketplaces. You get ranked
            leads and a short digest — then pitch on the original page.
          </p>
          {authed ? (
            <>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/leads"
                  className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]"
                >
                  Open leads
                </Link>
                <Link
                  href="/preferences?tab=matching"
                  className="rounded-full border border-white/20 px-5 py-2.5 text-[var(--paper)] hover:border-[var(--signal)]/60"
                >
                  Hunt Rules
                </Link>
                <button
                  type="button"
                  onClick={runScrape}
                  disabled={scraping}
                  className="rounded-full border border-white/10 px-5 py-2.5 text-[var(--fog)] disabled:opacity-60"
                >
                  {scraping ? "Working…" : "Refresh inventory"}
                </button>
              </div>
              <p className="mt-4 text-sm text-[var(--mute)]">
                API {getApiBase()} · status <span className="text-[var(--signal)]">{apiStatus}</span>
                {scrapeStatus ? ` · ${scrapeStatus}` : null}
              </p>
              {error ? <p className="mt-2 text-sm text-[var(--ember)]">{error}</p> : null}
            </>
          ) : (
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
            </div>
          )}
        </div>
      </section>

      {authed ? <ActivationChecklist /> : null}

      <section className="grid gap-10 md:grid-cols-3">
        {[
          {
            title: "Hunt",
            body: "Background hunters search public web and company/ATS openings that match your rules — no marketplace bid wars as the default path.",
          },
          {
            title: "Leads",
            body: "Ranked matches with why/risks and freelance focus. Open the original listing to pitch yourself.",
          },
          {
            title: "Digest",
            body: "Email on your show schedule with a short cap of new fits. We never invent jobs or auto-apply.",
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
              {authed ? "Latest in the desk" : "Sample of the desk"}
            </h2>
            <p className="mt-1 text-sm text-[var(--mute)]">{total} opportunities stored</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <Link href="/leads" className="text-[var(--signal)]">
              Leads
            </Link>
            <Link href="/jobs" className="text-[var(--signal)]">
              Browse all
            </Link>
          </div>
        </div>
        <div className="space-y-3">
          {jobs.length === 0 ? (
            <p className="text-[var(--mute)]">
              {authed
                ? "No leads yet. Set Hunt Rules — hunters fill the pool in the background."
                : "No public listings yet. Start free and set Hunt Rules."}
            </p>
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
        {!authed && error ? (
          <p className="mt-3 text-sm text-[var(--mute)]">Live feed unavailable right now — pricing and signup still work.</p>
        ) : null}
      </section>
    </main>
  );
}
