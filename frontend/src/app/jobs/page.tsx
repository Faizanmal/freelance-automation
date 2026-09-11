"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { listJobs, type Job } from "@/lib/api";

function stripHtml(value: string) {
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const load = useCallback((nextSearch = "", nextSource = "") => {
    startTransition(async () => {
      try {
        setError(null);
        const data = await listJobs({
          search: nextSearch || undefined,
          source: nextSource || undefined,
          limit: 80,
        });
        setJobs(data.items);
        setTotal(data.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load jobs");
      }
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="flex flex-1 flex-col gap-8">
      <section>
        <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Job feed
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--fog)]">
          Normalized listings from connected sources. Search title, company, or description.
        </p>
      </section>

      <form
        className="flex flex-wrap gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          load(search, source);
        }}
      >
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search python, react, design…"
          className="min-w-[220px] flex-1 rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
        />
        <select
          value={source}
          onChange={(event) => setSource(event.target.value)}
          className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5"
        >
          <option value="">All sources</option>
          <option value="remoteok">RemoteOK</option>
          <option value="arbeitnow">Arbeitnow</option>
          <option value="himalayas">Himalayas</option>
          <option value="jobicy">Jobicy</option>
          <option value="serpapi_freelance">SerpAPI Freelance</option>
          <option value="serpapi_jobs">SerpAPI Jobs</option>
          <option value="serpapi_companies">Company careers</option>
          <option value="serpapi_maps">Maps outreach</option>
          <option value="upwork">Upwork</option>
          <option value="freelancer">Freelancer</option>
        </select>
        <button type="submit" className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]">
          {pending ? "Loading…" : "Filter"}
        </button>
      </form>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      <p className="text-sm text-[var(--mute)]">{total} results</p>

      <div className="space-y-4">
        {jobs.map((job) => (
          <article key={job.id} className="border-b border-white/10 pb-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl text-[var(--paper)]">{job.title}</h2>
              <span className="text-xs tracking-wide text-[var(--mute)] uppercase">{job.source_name}</span>
            </div>
            <p className="mt-1 text-sm text-[var(--fog)]">
              {[job.company, job.location].filter(Boolean).join(" · ")}
            </p>
            <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-[var(--mute)]">
              {stripHtml(job.description).slice(0, 280)}
              {stripHtml(job.description).length > 280 ? "…" : ""}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(job.tags || []).slice(0, 6).map((tag) => (
                <span key={tag} className="text-xs text-[var(--signal)]">
                  #{tag}
                </span>
              ))}
            </div>
            <a href={job.url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm text-[var(--paper)] underline-offset-4 hover:underline">
              Open listing
            </a>
          </article>
        ))}
      </div>
    </main>
  );
}
