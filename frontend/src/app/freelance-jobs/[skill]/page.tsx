"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import {
  getSeoSkillDirectory,
  getToken,
  type SeoSkillDirectoryResponse,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, ArrowRight, Lock, Sparkles } from "lucide-react";

export default function SkillDirectoryLandingPage() {
  const params = useParams<{ skill: string }>();
  const skillSlug = typeof params?.skill === "string" ? params.skill.toLowerCase() : "python";
  const [data, setData] = useState<SeoSkillDirectoryResponse | null>(null);
  const [pending, startTransition] = useTransition();
  const [authed] = useState(() => (typeof window !== "undefined" ? Boolean(getToken()) : false));

  useEffect(() => {
    startTransition(async () => {
      try {
        const res = await getSeoSkillDirectory(skillSlug, 24);
        setData(res);
      } catch {
        const cleanLabel = skillSlug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        setData({
          slug: skillSlug,
          label: cleanLabel,
          headline: `Remote ${cleanLabel} Freelance & Contract Jobs`,
          description: `Curated ${cleanLabel} contract opportunities from direct client postings and remote job boards.`,
          total_matched: 0,
          items: [],
          related_skills: [
            { slug: "python", label: "Python" },
            { slug: "react", label: "React" },
            { slug: "fastapi", label: "FastAPI" },
            { slug: "typescript", label: "TypeScript" },
          ],
        });
      }
    });
  }, [skillSlug]);

  const title = data?.headline || `Remote ${skillSlug.toUpperCase()} Freelance & Contract Jobs`;
  const description =
    data?.description ||
    "Direct client opportunities ranked against your Hunt Rules with 1-click tailored outreach pitches.";

  return (
    <div className="flex flex-1 flex-col gap-8">
      <div>
        <Link
          href="/freelance-jobs"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          <ArrowLeft className="size-3.5" />
          All Skill Directories
        </Link>
      </div>

      <PageHeader
        eyebrow={`${data?.label || skillSlug} Contract Intelligence`}
        title={title}
        description={description}
        actions={
          authed ? (
            <Link
              href="/leads"
              className="inline-flex h-10 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
            >
              Open Leads Desk
              <ArrowRight className="size-4" />
            </Link>
          ) : (
            <Link
              href="/auth"
              className="inline-flex h-10 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
            >
              Get {data?.label || "Skill"} Alerts Free
              <ArrowRight className="size-4" />
            </Link>
          )
        }
      />

      {pending && !data ? (
        <div className="grid gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : data && data.items.length === 0 ? (
        <EmptyState
          title={`No public ${data.label} previews cached right now`}
          description={`Sign in to run a live ${data.label} hunt across SerpAPI, Hacker News, Reddit hiring threads, and GitHub bounties.`}
          actionHref={authed ? "/leads" : "/auth"}
          actionLabel={authed ? "Run Live Hunt" : "Start Free Hunt"}
          secondaryHref="/freelance-jobs"
          secondaryLabel="Browse Other Skills"
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(data?.items || []).map((item) => (
            <Card key={item.id} className="flex flex-col justify-between p-5">
              <div>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h2 className="text-base font-semibold text-[var(--text)]">{item.title}</h2>
                  {item.budget_label ? (
                    <Badge variant="outline">{item.budget_label}</Badge>
                  ) : (
                    <Badge variant="muted">Contract / Remote</Badge>
                  )}
                </div>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {item.company_masked} · {item.location} · via {item.source_attribution}
                </p>
                {item.description_excerpt ? (
                  <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-[var(--text-secondary)]">
                    {item.description_excerpt}
                  </p>
                ) : null}
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-3">
                <div className="flex flex-wrap gap-1.5">
                  {item.tags.slice(0, 4).map((tag) => (
                    <Badge key={tag} variant="outline" className="text-[10px]">
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
                      Open & Draft Pitch
                    </>
                  ) : (
                    <>
                      <Lock className="size-3.5" />
                      Unlock Client & Pitch
                    </>
                  )}
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}

      {data?.related_skills?.length ? (
        <section className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase">
            Related Contract Directories
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.related_skills.map((skill) => (
              <Link
                key={skill.slug}
                href={`/freelance-jobs/${skill.slug}`}
                className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--text)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
              >
                {skill.label} Contracts
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

