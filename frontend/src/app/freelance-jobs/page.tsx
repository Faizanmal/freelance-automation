"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import {
  getSeoDirectory,
  getToken,
  type SeoDirectoryIndexResponse,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight, Lock, Sparkles } from "lucide-react";

const FALLBACK_CATEGORIES = [
  {
    slug: "python",
    label: "Python",
    headline: "Remote Python Freelance & Contract Jobs",
    description:
      "Verified Python backend, automation, data, and AI contract opportunities from direct client postings and company boards.",
    job_count: 0,
  },
  {
    slug: "react",
    label: "React",
    headline: "Remote React & Frontend Contract Jobs",
    description:
      "Live React, Next.js, and TypeScript contract roles sourced outside crowded bidding marketplaces.",
    job_count: 0,
  },
  {
    slug: "fastapi",
    label: "FastAPI",
    headline: "FastAPI & Async Python Contract Opportunities",
    description:
      "High-intent FastAPI, microservice, and API architecture freelance projects.",
    job_count: 0,
  },
  {
    slug: "typescript",
    label: "TypeScript",
    headline: "Remote TypeScript Freelance & Contract Roles",
    description:
      "Full-stack and frontend TypeScript contract work from startups and direct hiring posts.",
    job_count: 0,
  },
  {
    slug: "ai-ml",
    label: "AI & LLM Engineering",
    headline: "AI, LLM & Machine Learning Contract Jobs",
    description:
      "Contract roles in LLM orchestration, RAG pipelines, agents, PyTorch, and applied AI.",
    job_count: 0,
  },
  {
    slug: "devops",
    label: "DevOps & Cloud",
    headline: "DevOps, Kubernetes & Cloud Infrastructure Contracts",
    description:
      "Fractional DevOps, AWS/GCP, Terraform, Docker, and CI/CD consulting engagements.",
    job_count: 0,
  },
  {
    slug: "golang",
    label: "Go (Golang)",
    headline: "Remote Golang Backend & Systems Contract Jobs",
    description:
      "High-performance Go backend, distributed systems, and cloud-native freelance roles.",
    job_count: 0,
  },
  {
    slug: "nodejs",
    label: "Node.js",
    headline: "Remote Node.js Backend & Full-Stack Contracts",
    description:
      "Contract Node.js, Express, NestJS, and GraphQL engineering opportunities.",
    job_count: 0,
  },
];

export default function FreelanceJobsDirectoryPage() {
  const [data, setData] = useState<SeoDirectoryIndexResponse | null>(null);
  const [pending, startTransition] = useTransition();
  const [authed] = useState(() => (typeof window !== "undefined" ? Boolean(getToken()) : false));

  useEffect(() => {
    startTransition(async () => {
      try {
        const res = await getSeoDirectory();
        setData(res);
      } catch {
        setData({
          total_active: 0,
          categories: FALLBACK_CATEGORIES,
          recent: [],
        });
      }
    });
  }, []);

  const categories = data?.categories?.length ? data.categories : FALLBACK_CATEGORIES;
  const recent = data?.recent || [];

  return (
    <div className="flex flex-1 flex-col gap-10">
      <PageHeader
        eyebrow="Freelance & Contract Directory"
        title="Remote Contract Opportunities by Skill"
        description="Curated freelance, fractional, and contract roles sourced directly from company boards, Hacker News, GitHub bounties, and Reddit hiring threads — zero marketplace bidding wars."
        actions={
          authed ? (
            <Link
              href="/leads"
              className="inline-flex h-10 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
            >
              Open Your Leads Desk
              <ArrowRight className="size-4" />
            </Link>
          ) : (
            <Link
              href="/auth"
              className="inline-flex h-10 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
            >
              Unlock Full Listings Free
              <ArrowRight className="size-4" />
            </Link>
          )
        }
      />

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text)]">Browse by Specialty</h2>
          {data?.total_active ? (
            <span className="text-xs text-[var(--text-muted)]">
              {data.total_active} active opportunities indexed
            </span>
          ) : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((cat) => (
            <Link key={cat.slug} href={`/freelance-jobs/${cat.slug}`} className="group flex">
              <Card className="flex w-full flex-col justify-between p-5 transition-colors group-hover:border-[var(--accent)]">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-base font-semibold text-[var(--text)] group-hover:text-[var(--accent)]">
                      {cat.label}
                    </h3>
                    {cat.job_count > 0 ? (
                      <Badge variant="accent">{cat.job_count} live</Badge>
                    ) : (
                      <Badge variant="outline">Directory</Badge>
                    )}
                  </div>
                  <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-[var(--text-secondary)]">
                    {cat.description}
                  </p>
                </div>
                <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-[var(--accent)]">
                  Explore {cat.label} roles
                  <ArrowRight className="size-3" />
                </span>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-[var(--text)]">Latest Contract Previews</h2>
            <p className="text-xs text-[var(--text-muted)]">
              Client names and direct application links unlock inside Signal Desk
            </p>
          </div>
        </div>

        {pending && !data ? (
          <div className="grid gap-3">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        ) : recent.length === 0 ? (
          <EmptyState
            title="Live pool is refreshing"
            description="Sign in and configure your Hunt Rules to trigger an instant discovery pass across your target skills."
            actionHref={authed ? "/leads" : "/auth"}
            actionLabel={authed ? "Open Leads" : "Create Free Account"}
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {recent.map((item) => (
              <Card key={item.id} className="flex flex-col justify-between p-5">
                <div>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h3 className="text-base font-medium text-[var(--text)]">{item.title}</h3>
                    {item.budget_label ? (
                      <Badge variant="outline">{item.budget_label}</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    {item.company_masked} · {item.location} · via {item.source_attribution}
                  </p>
                  {item.description_excerpt ? (
                    <p className="mt-2.5 line-clamp-2 text-sm text-[var(--text-secondary)]">
                      {item.description_excerpt}
                    </p>
                  ) : null}
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-3">
                  <div className="flex flex-wrap gap-1.5">
                    {item.tags.slice(0, 3).map((tag) => (
                      <Badge key={tag} variant="muted" className="text-[10px]">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <Link
                    href={authed ? `/leads?job=${item.id}` : "/auth"}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--accent)] hover:underline"
                  >
                    {authed ? (
                      <>
                        <Sparkles className="size-3.5" />
                        Draft 1-Click Pitch
                      </>
                    ) : (
                      <>
                        <Lock className="size-3.5" />
                        Unlock Original & Pitch
                      </>
                    )}
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

