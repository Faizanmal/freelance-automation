"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { getApiBase, getIntegrationsStatus, getToken, scrapeJobs, type IntegrationsStatus } from "@/lib/api";

export default function SourcesPage() {
  const [status, setStatus] = useState<IntegrationsStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const refresh = () => {
    startTransition(async () => {
      try {
        setError(null);
        setStatus(await getIntegrationsStatus());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load integrations");
      }
    });
  };

  useEffect(() => {
    refresh();
  }, []);

  const pullSource = (source: string) => {
    if (!getToken()) {
      window.location.href = "/auth";
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        setMessage(`Scraping ${source}…`);
        const result = await scrapeJobs([source], 15, false);
        const sourceResult = result.sources?.[source] as Record<string, unknown> | undefined;
        if (sourceResult?.error) {
          setMessage(`${source}: ${String(sourceResult.error)} — ${String(sourceResult.detail || "")}`);
        } else {
          setMessage(
            `${source}: fetched ${result.total_fetched}, ingested ${result.total_ingested}, skipped ${result.total_skipped}`,
          );
        }
        setStatus(await getIntegrationsStatus());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scrape failed");
        setMessage(null);
      }
    });
  };

  return (
    <main className="flex flex-1 flex-col gap-8">
      <section>
        <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Sources
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--fog)]">
          Commercial scrapes only use sources with a clear rights path. High-risk feeds stay registered for demos
          but are blocked until licensed.
        </p>
        <p className="mt-2 text-sm text-[var(--mute)]">API {getApiBase()}</p>
      </section>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {message ? <p className="text-sm text-[var(--signal)]">{message}</p> : null}
      {status?.notes?.restricted ? <p className="text-sm text-[var(--mute)]">{status.notes.restricted}</p> : null}

      <section className="space-y-4">
        <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Commercial free sources
        </h2>
        <ul className="space-y-2 text-[var(--fog)]">
          {(status?.commercial_free_sources || ["remoteok", "arbeitnow", "himalayas", "jobicy"]).map((source) => (
            <li key={source} className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 py-2">
              <span className="text-[var(--paper)]">{source}</span>
              <button
                type="button"
                disabled={pending}
                onClick={() => pullSource(source)}
                className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
              >
                Pull jobs
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Pro marketplace APIs
        </h2>

        <div className="border-b border-white/10 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg text-[var(--paper)]">Upwork</h3>
              <p className="text-sm text-[var(--mute)]">
                {status?.upwork.configured ? "Connected via OAuth / access token" : "Not connected"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <a
                href={`${getApiBase()}/integrations/upwork/authorize`}
                className="rounded-full border border-white/20 px-4 py-2 text-sm hover:border-[var(--signal)]/50"
              >
                Connect OAuth
              </a>
              <button
                type="button"
                disabled={pending}
                onClick={() => pullSource("upwork")}
                className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
              >
                Pull jobs
              </button>
            </div>
          </div>
        </div>

        <div className="border-b border-white/10 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg text-[var(--paper)]">Freelancer.com</h3>
              <p className="text-sm text-[var(--mute)]">
                {status?.freelancer.configured
                  ? "Token configured"
                  : "Set FREELANCER_OAUTH_TOKEN in fastapi/.env"}
              </p>
            </div>
            <button
              type="button"
              disabled={pending}
              onClick={() => pullSource("freelancer")}
              className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              Pull jobs
            </button>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Pro discovery (SerpAPI)
        </h2>
        <p className="text-sm text-[var(--mute)]">
          {status?.notes?.discovery ||
            "Google Search / Google Jobs discovery for freelance and job leads. Requires SERPAPI_API_KEY."}
        </p>
        <div className="border-b border-white/10 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg text-[var(--paper)]">SerpAPI Freelance</h3>
              <p className="text-sm text-[var(--mute)]">
                {status?.serpapi?.configured
                  ? `Configured · ${status.serpapi.freelance_query}`
                  : "Set SERPAPI_API_KEY in fastapi/.env"}
              </p>
            </div>
            <button
              type="button"
              disabled={pending}
              onClick={() => pullSource("serpapi_freelance")}
              className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              Pull freelance leads
            </button>
          </div>
        </div>
        <div className="border-b border-white/10 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg text-[var(--paper)]">SerpAPI Jobs</h3>
              <p className="text-sm text-[var(--mute)]">
                {status?.serpapi?.configured
                  ? `Configured · ${status.serpapi.jobs_query}`
                  : "Set SERPAPI_API_KEY in fastapi/.env"}
              </p>
            </div>
            <button
              type="button"
              disabled={pending}
              onClick={() => pullSource("serpapi_jobs")}
              className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              Pull job leads
            </button>
          </div>
        </div>
        <div className="border-b border-white/10 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg text-[var(--paper)]">Company careers</h3>
              <p className="text-sm text-[var(--mute)]">
                {status?.serpapi?.configured
                  ? `Configured · ${status.serpapi.companies_query || "career page discovery"}`
                  : "Set SERPAPI_API_KEY in fastapi/.env"}
              </p>
            </div>
            <button
              type="button"
              disabled={pending}
              onClick={() => pullSource("serpapi_companies")}
              className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              Pull company pages
            </button>
          </div>
        </div>
        <div className="border-b border-white/10 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg text-[var(--paper)]">Google Maps outreach</h3>
              <p className="text-sm text-[var(--mute)]">
                {status?.serpapi?.configured
                  ? `Configured · ${status.serpapi.maps_query || "local businesses"}${
                      status.serpapi.maps_ll ? ` · ll ${status.serpapi.maps_ll}` : ""
                    }`
                  : "Set SERPAPI_API_KEY in fastapi/.env"}
              </p>
            </div>
            <button
              type="button"
              disabled={pending}
              onClick={() => pullSource("serpapi_maps")}
              className="rounded-full bg-[var(--signal)] px-4 py-2 text-sm font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              Pull maps leads
            </button>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Restricted until licensed
        </h2>
        <ul className="space-y-2 text-sm text-[var(--mute)]">
          {(status?.restricted_sources || ["remotive", "weworkremotely", "peopleperhour", "guru"]).map((source) => (
            <li key={source} className="border-b border-white/10 py-2">
              <span className="text-[var(--paper)]">{source}</span>
              <span className="ml-2">blocked from commercial scrapes</span>
            </li>
          ))}
        </ul>
      </section>

      <Link href="/" className="text-sm text-[var(--mute)]">
        Back to desk
      </Link>
    </main>
  );
}
