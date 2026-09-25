"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { listJobs, type Job } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
          Job feed
        </motion.h1>
        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="mt-2 max-w-2xl text-[var(--fog)]"
        >
          Normalized listings from connected sources. Search title, company, or description.
        </motion.p>
      </section>

      <motion.form
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex flex-wrap gap-3 rounded-2xl bg-white/5 p-3 backdrop-blur-md border border-white/10"
        onSubmit={(event) => {
          event.preventDefault();
          load(search, source);
        }}
      >
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search python, react, design…"
          className="min-w-[220px] flex-1 rounded-full border border-white/10 bg-black/40 px-5 py-2.5 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60"
        />
        <select
          value={source}
          onChange={(event) => setSource(event.target.value)}
          className="rounded-full border border-white/10 bg-black/40 px-5 py-2.5 outline-none transition focus:border-[var(--signal)]/50"
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
        <Button type="submit" disabled={pending}>
          {pending ? "Searching…" : "Filter"}
        </Button>
      </motion.form>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--mute)]">{total} results</p>
      </div>

      <motion.div layout className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence mode="popLayout">
          {jobs.map((job, index) => (
            <Card 
              key={job.id} 
              className="flex flex-col p-6"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.05, 0.5) }}
            >
              <div className="mb-4 flex items-start justify-between gap-2">
                <h2 className="text-xl font-medium leading-tight text-[var(--paper)]">{job.title}</h2>
                <span className="shrink-0 rounded-full bg-white/10 px-2 py-1 text-[10px] tracking-wider text-[var(--mute)] uppercase">
                  {job.source_name}
                </span>
              </div>
              <p className="mb-4 text-sm text-[var(--fog)] font-medium">
                {[job.company, job.location].filter(Boolean).join(" · ")}
              </p>
              <p className="mb-6 line-clamp-3 flex-1 text-sm leading-relaxed text-[var(--mute)]">
                {stripHtml(job.description)}
              </p>
              <div className="mt-auto pt-4 border-t border-white/5">
                <div className="mb-4 flex flex-wrap gap-2">
                  {(job.tags || []).slice(0, 4).map((tag) => (
                    <span key={tag} className="rounded bg-black/40 px-2 py-1 text-xs text-[var(--signal)] border border-[var(--signal)]/20">
                      {tag}
                    </span>
                  ))}
                </div>
                <Button 
                  variant="outline" 
                  className="w-full text-sm py-2"
                  onClick={() => window.open(job.url, "_blank")}
                >
                  View Details
                </Button>
              </div>
            </Card>
          ))}
        </AnimatePresence>
      </motion.div>
    </motion.main>
  );
}
