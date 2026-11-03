"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore, useTransition } from "react";
import {
  getAuthFindings,
  getAuthServerSnapshot,
  getAuthSnapshot,
  getPreferences,
  getToken,
  healthLive,
  listJobs,
  me,
  scrapeJobs,
  subscribeAuth,
  type Job,
  type LeadFinding,
  type Preferences,
  type User,
} from "@/lib/api";
import { sanitizeExternalUrl } from "@/lib/security";
import { ActivationChecklist } from "@/components/activation-checklist";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowRight,
  Bookmark,
  CalendarClock,
  Radar,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";

function greetingForHour(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function formatDigestSummary(prefs: Preferences | null) {
  if (!prefs) return null;
  if (!prefs.digest_mode) return "Digest paused";
  const days = (prefs.digest_days || []).join(", ") || "weekdays";
  const time = prefs.digest_time_local || "09:00";
  const zone = prefs.timezone || "local timezone";
  return `${days} · ${time} · ${zone}`;
}

export default function HomePage() {
  const router = useRouter();
  const authed = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthServerSnapshot);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [apiStatus, setApiStatus] = useState("checking");
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scraping, setScraping] = useState(false);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [findings, setFindings] = useState<LeadFinding[]>([]);
  const [findingsMeta, setFindingsMeta] = useState<{
    total_findings: number;
    generated_at?: string;
  } | null>(null);
  const [greeting] = useState(() => greetingForHour());
  const [, startTransition] = useTransition();

  const refresh = (isAuthed: boolean) => {
    startTransition(async () => {
      try {
        setError(null);
        setLoading(true);
        if (isAuthed) {
          const [health, data, currentUser, currentPrefs, leadData] = await Promise.all([
            healthLive(),
            listJobs({ limit: 8 }),
            me().catch(() => null),
            getPreferences().catch(() => null),
            getAuthFindings(8, true).catch(() => null),
          ]);
          setApiStatus(health.status);
          setJobs(data.items);
          setTotal(data.total);
          setUser(currentUser);
          setPrefs(currentPrefs);
          setFindings(leadData?.items || []);
          setFindingsMeta(
            leadData
              ? { total_findings: leadData.total_findings, generated_at: leadData.generated_at }
              : null,
          );
          return;
        }
        const data = await listJobs({ limit: 8 });
        setJobs(data.items);
        setTotal(data.total);
        setApiStatus("ok");
        setUser(null);
        setPrefs(null);
        setFindings([]);
        setFindingsMeta(null);
      } catch (err) {
        setApiStatus("offline");
        setError(err instanceof Error ? err.message : "API unavailable");
      } finally {
        setLoading(false);
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
        const remaining =
          typeof result.daily_scrape_remaining === "number"
            ? ` · ${result.daily_scrape_remaining} hunts left today`
            : "";
        setScrapeStatus(
          `Fetched ${result.total_fetched ?? 0} · ingested ${result.total_ingested ?? 0} · merged ${result.total_merged ?? 0} · skipped ${result.total_skipped ?? 0}${remaining}`,
        );
        const [data, leadData] = await Promise.all([
          listJobs({ limit: 8 }),
          getAuthFindings(8, true).catch(() => null),
        ]);
        setJobs(data.items);
        setTotal(data.total);
        setFindings(leadData?.items || []);
        setFindingsMeta(
          leadData
            ? { total_findings: leadData.total_findings, generated_at: leadData.generated_at }
            : null,
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : "Scrape failed";
        setError(message);
        setScrapeStatus(
          /daily manual hunt limit/i.test(message) ? "Daily hunt cap reached — upgrade for more" : null,
        );
      } finally {
        setScraping(false);
      }
    });
  };

  const savedCount = useMemo(
    () => findings.filter((item) => item.user_status === "save").length,
    [findings],
  );
  const highFitCount = useMemo(
    () => findings.filter((item) => item.score >= 0.7).length,
    [findings],
  );
  const firstName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "there";
  const digestLine = formatDigestSummary(prefs);

  if (!authed) {
    return (
      <div className="flex flex-1 flex-col gap-14">
        <section className="relative overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[var(--surface)] px-6 py-14 md:px-12 md:py-20">
          <div
            className="pointer-events-none absolute inset-0 opacity-80"
            style={{
              backgroundImage:
                "radial-gradient(700px 320px at 0% 0%, rgba(59,130,246,0.12), transparent 60%), radial-gradient(500px 280px at 100% 10%, rgba(39,39,42,0.5), transparent 55%)",
            }}
          />
          <div className="relative max-w-3xl">
            <p className="text-xs font-semibold tracking-[0.22em] text-[var(--accent)] uppercase">
              Freelance opportunity intelligence
            </p>
            <h1
              className="mt-3 text-5xl leading-[1.05] tracking-tight text-[var(--text)] md:text-7xl"
              style={{ fontFamily: "var(--font-display), Georgia, serif" }}
            >
              Signal Desk
            </h1>
            <p className="mt-5 max-w-xl text-lg text-[var(--text-secondary)]">
              Set Hunt Rules. We find public freelance and contract posts outside crowded marketplaces. You get ranked
              leads and a short digest — then pitch on the original page.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/pricing"
                className="inline-flex h-10 items-center rounded-[var(--radius)] bg-[var(--accent)] px-5 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
              >
                See pricing
              </Link>
              <Link
                href="/auth"
                className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-5 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
              >
                Start free
              </Link>
            </div>
          </div>
        </section>

        <section className="grid gap-8 md:grid-cols-3">
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
            <div key={item.title} className="border-t border-[var(--border)] pt-5">
              <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
                {item.title}
              </h2>
              <p className="mt-3 text-[var(--text-secondary)]">{item.body}</p>
            </div>
          ))}
        </section>

        <section className="flex flex-col gap-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="inline-block size-2 rounded-full bg-[var(--success)] animate-pulse" />
                <span className="text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase">Live Desk Preview</span>
              </div>
              <h2 className="mt-1 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
                Recent opportunities from our shared hunt pool
              </h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                {total} contract opportunities indexed across direct client posts, ATS boards, and developer communities.
              </p>
            </div>
            <Link
              href="/auth"
              className="inline-flex h-9 items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border)] px-4 text-xs font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
            >
              Set your Hunt Rules
              <ArrowRight className="size-3.5" />
            </Link>
          </div>

          {jobs.length === 0 ? (
            <EmptyState
              title="No public sample listings yet"
              description="Start free, verify email, set Hunt Rules — then open Leads when the desk has fits."
              actionHref="/help"
              actionLabel="How it works"
            />
          ) : (
            <div className="divide-y divide-[var(--border)] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-sm">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex flex-col gap-2 p-5 transition-colors hover:bg-[var(--surface-hover)] sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-medium text-[var(--text)]">{job.title}</h3>
                      <Badge variant="outline" className="text-[10px] tracking-wide uppercase">
                        {job.source_name}
                      </Badge>
                      {job.location && /remote/i.test(job.location) ? (
                        <Badge variant="muted" className="text-[10px]">Remote</Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      {[job.company, job.location].filter(Boolean).join(" · ") || "Remote contract"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {job.budget_label ? (
                      <span className="text-xs font-medium text-[var(--text-muted)]">
                        {job.budget_label}
                      </span>
                    ) : job.budget_min || job.budget_max ? (
                      <span className="text-xs font-medium text-[var(--text-muted)]">
                        ${job.budget_min ?? 0}
                        {job.budget_max ? ` - $${job.budget_max}` : "+"}
                      </span>
                    ) : null}
                    <a
                      href={sanitizeExternalUrl(job.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex h-8 items-center gap-1 rounded-[var(--radius)] border border-[var(--border)] px-3 text-xs font-medium text-[var(--text)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                    >
                      View post
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {error ? (
            <p className="text-sm text-[var(--text-muted)]">
              Live feed unavailable right now — pricing and signup still work.
            </p>
          ) : null}

          <div className="mt-4 rounded-[1rem] border border-[var(--border)] bg-gradient-to-r from-[var(--surface)] to-[var(--surface-hover)] p-6 md:p-8">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text)]">
                  Get high-fit contract posts delivered directly to your inbox
                </h3>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">
                  Signal Desk filters noise, scores jobs against your exact tech stack and rates, and delivers tailored outreach hooks.
                </p>
              </div>
              <div className="flex shrink-0 gap-3">
                <Link
                  href="/auth"
                  className="inline-flex h-10 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] px-5 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
                >
                  Create free account
                </Link>
                <Link
                  href="/pricing"
                  className="inline-flex h-10 items-center justify-center rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm font-medium text-[var(--text)] hover:bg-[var(--surface)]"
                >
                  Compare plans
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-8">
      <PageHeader
        eyebrow="Signal Desk"
        title={`${greeting}, ${firstName}`}
        description="Here's what's happening in your freelance opportunity desk."
        actions={
          <>
            <Link
              href="/leads"
              className="inline-flex h-10 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
            >
              Explore opportunities
              <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/preferences?tab=matching"
              className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
            >
              Hunt Rules
            </Link>
            <Button type="button" variant="secondary" onClick={runScrape} disabled={scraping}>
              <RefreshCw className={`size-4 ${scraping ? "animate-spin" : ""}`} />
              {scraping ? "Working…" : "Refresh inventory"}
            </Button>
          </>
        }
      />

      <p className="text-sm text-[var(--text-muted)]" data-testid="desk-status">
        Desk{" "}
        <span className={apiStatus === "offline" ? "text-[var(--danger)]" : "text-[var(--success)]"}>
          {apiStatus === "checking" ? "checking…" : apiStatus === "offline" ? "offline" : "online"}
        </span>
        {scrapeStatus ? ` · ${scrapeStatus}` : null}
      </p>

      {error ? (
        <p className="text-sm text-[var(--danger)]">
          {error}
          {/upgrade|daily manual hunt|Pro/i.test(error) ? (
            <>
              {" "}
              <Link href="/pricing" className="underline text-[var(--accent)]">
                See Pricing
              </Link>
            </>
          ) : null}
        </p>
      ) : null}

      <ActivationChecklist />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "New opportunities",
            value: findingsMeta?.total_findings ?? findings.length,
            icon: Sparkles,
            hint: "Ranked fits from your Hunt Rules",
          },
          {
            label: "High-fit opportunities",
            value: highFitCount,
            icon: Target,
            hint: "Score ≥ 70%",
          },
          {
            label: "Saved opportunities",
            value: savedCount,
            icon: Bookmark,
            hint: "In your current lead set",
          },
          {
            label: "Opportunities stored",
            value: total,
            icon: Radar,
            hint: "Shared hunt inventory",
          },
        ].map((kpi) => (
          <Card key={kpi.label} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium tracking-wide text-[var(--text-muted)] uppercase">
                  {kpi.label}
                </p>
                {loading ? (
                  <Skeleton className="mt-3 h-8 w-16" />
                ) : (
                  <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--text)]">{kpi.value}</p>
                )}
                <p className="mt-1 text-xs text-[var(--text-muted)]">{kpi.hint}</p>
              </div>
              <span className="rounded-md bg-[var(--accent-muted)] p-2 text-[var(--accent)]">
                <kpi.icon className="size-4" />
              </span>
            </div>
          </Card>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text)]">Best matches</h2>
              <p className="text-sm text-[var(--text-muted)]">
                {findingsMeta?.generated_at
                  ? `Updated ${new Date(findingsMeta.generated_at).toLocaleString()}`
                  : "Ranked against your Hunt Rules"}
              </p>
            </div>
            <Link href="/leads" className="text-sm text-[var(--accent)] hover:underline">
              View all
            </Link>
          </div>
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : findings.length === 0 ? (
            <EmptyState
              title="No opportunities yet"
              description="Set Hunt Rules, then refresh inventory. Background hunters also fill the shared pool on a schedule — empty is normal after a pause or a fresh deploy."
              actionHref="/preferences?tab=matching"
              actionLabel="Configure preferences"
              secondaryHref="/leads"
              secondaryLabel="Open Leads"
              className="border-0 bg-transparent px-0 py-2"
            />
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {findings.slice(0, 5).map((item) => (
                <div key={item.job_id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-[var(--text)]">{item.title}</p>
                    <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
                      {[item.company, item.source_label || item.source_name].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="accent">{Math.round(item.score * 100)} fit</Badge>
                    <a
                      href={sanitizeExternalUrl(item.apply_url || item.url) || "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-[var(--accent)] hover:underline"
                    >
                      Open
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="mb-3 flex items-center gap-2 text-[var(--accent)]">
              <CalendarClock className="size-4" />
              <h2 className="text-sm font-semibold tracking-wide text-[var(--text)] uppercase">Digest</h2>
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              Your show clock — separate from the system hunt schedule.
            </p>
            <p className="mt-3 text-sm font-medium text-[var(--text)]">
              {loading ? "Loading schedule…" : digestLine || "Not configured yet — set days and time in Digest settings."}
            </p>
            <Link href="/preferences?tab=alerts" className="mt-4 inline-block text-sm text-[var(--accent)] hover:underline">
              Edit schedule
            </Link>
          </Card>

          <Card className="p-5">
            <div className="mb-3 flex items-center gap-2 text-[var(--accent)]">
              <Radar className="size-4" />
              <h2 className="text-sm font-semibold tracking-wide text-[var(--text)] uppercase">
                Discovery status
              </h2>
            </div>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--text-muted)]">API health</dt>
                <dd className="text-[var(--text)] capitalize">{apiStatus}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--text-muted)]">Inventory</dt>
                <dd className="text-[var(--text)]">{total} stored</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--text-muted)]">Hunt clock</dt>
                <dd className="text-[var(--text)]">System schedule</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-[var(--text-muted)]">
              Hunters fill the shared pool on the server schedule. Refresh inventory runs a manual hunt within your plan limits.
            </p>
          </Card>
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Latest in the desk
            </h2>
            <p className="mt-1 text-sm text-[var(--text-muted)]">{total} opportunities stored</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <Link href="/leads" className="text-[var(--accent)] hover:underline">
              Leads
            </Link>
            <Link href="/preferences" className="text-[var(--accent)] hover:underline">
              Hunt Rules
            </Link>
          </div>
        </div>
        {jobs.length === 0 ? (
          <EmptyState
            title="Inventory is empty right now"
            description="Set Hunt Rules, then Refresh inventory. Background hunters also fill the shared pool on a schedule — this is normal after a pause or a fresh deploy."
            actionHref="/preferences"
            actionLabel="Hunt Rules"
            secondaryHref="/pricing"
            secondaryLabel="Pricing"
          />
        ) : (
          <div className="divide-y divide-[var(--border)] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)]">
            {jobs.map((job) => (
              <a
                key={job.id}
                href={job.url}
                target="_blank"
                rel="noreferrer"
                className="block px-5 py-4 transition-colors hover:bg-[var(--surface-hover)]"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-base font-medium text-[var(--text)]">{job.title}</h3>
                  <span className="text-xs tracking-wide text-[var(--text-muted)] uppercase">
                    {job.source_name}
                  </span>
                </div>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">
                  {[job.company, job.location].filter(Boolean).join(" · ") || "Remote opportunity"}
                </p>
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
