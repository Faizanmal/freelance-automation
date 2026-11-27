"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore, useTransition } from "react";
import {
  getAuthFindings,
  getAuthServerSnapshot,
  getAuthSnapshot,
  getPipelineStats,
  getPreferences,
  getToken,
  healthLive,
  listJobs,
  me,
  prefetchInbox,
  scrapeJobs,
  subscribeAuth,
  type Job,
  type LeadFinding,
  type PipelineStats,
  type Preferences,
  type User,
} from "@/lib/api";
import {
  applyLeadOverridesToItems,
  subscribeLeadActions,
} from "@/lib/lead-action-store";
import { sanitizeExternalUrl } from "@/lib/security";
import { ActivationChecklist } from "@/components/activation-checklist";
import { EarningsCalculator } from "@/components/earnings-calculator";
import { HuntRulesPreview } from "@/components/hunt-rules-preview";
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
    total_scanned?: number;
    total_indexed?: number;
    generated_at?: string;
  } | null>(null);
  const [pipelineStats, setPipelineStats] = useState<PipelineStats | null>(null);
  const [greeting] = useState(() => greetingForHour());
  const [, startTransition] = useTransition();

  const refresh = (isAuthed: boolean) => {
    startTransition(async () => {
      try {
        setLoading(true);
        setError(null);
        if (isAuthed) {
          const [health, data, currentUser, currentPrefs, leadData, pStats] = await Promise.all([
            healthLive(),
            listJobs({ limit: 8 }),
            me().catch(() => null),
            getPreferences().catch(() => null),
            // Same include_skipped + limit as /leads so Desk Saved/Pitched match tabs.
            getAuthFindings(25, undefined, true).catch(() => null),
            Promise.resolve(typeof getPipelineStats === "function" ? getPipelineStats() : null).catch(
              () => null,
            ),
          ]);
          setApiStatus(health.status);
          setJobs(data.items);
          // Prefer findings total_indexed (post-purge count_jobs) so Desk matches /leads.
          setTotal(
            typeof leadData?.total_indexed === "number"
              ? leadData.total_indexed
              : typeof data.total === "number"
                ? data.total
                : data.items.length,
          );
          setUser(currentUser);
          setPrefs(currentPrefs);
          setFindings(applyLeadOverridesToItems(leadData?.items || []));
          setFindingsMeta(
            leadData
              ? {
                  total_findings: leadData.total_findings,
                  total_scanned: leadData.total_scanned,
                  total_indexed: leadData.total_indexed,
                  generated_at: leadData.generated_at,
                }
              : null,
          );
          setPipelineStats(pStats);
          // Warm inbox so /notifications can paint from session cache under 2s.
          prefetchInbox();
          return;
        }
        const data = await listJobs({ limit: 8 });
        setJobs(data.items);
        setTotal(typeof data.total === "number" ? data.total : data.items.length);
        setApiStatus("ok");
        setUser(null);
        setPrefs(null);
        setFindings([]);
        setFindingsMeta(null);
        setPipelineStats(null);
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

  // Re-apply cross-route lead overrides when /leads writes while Desk is mounted
  // (or after client navigates back without a full remount).
  useEffect(() => {
    return subscribeLeadActions(() => {
      setFindings((prev) => applyLeadOverridesToItems(prev));
    });
  }, []);

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
          getAuthFindings(8).catch(() => null),
        ]);
        setJobs(data.items);
        setTotal(
          typeof leadData?.total_indexed === "number"
            ? leadData.total_indexed
            : typeof data.total === "number"
              ? data.total
              : data.items.length,
        );
        setFindings(applyLeadOverridesToItems(leadData?.items || []));
        setFindingsMeta(
          leadData
            ? {
                total_findings: leadData.total_findings,
                total_scanned: leadData.total_scanned,
                total_indexed: leadData.total_indexed,
                generated_at: leadData.generated_at,
              }
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

  // Same query as /leads tabs: counts from findings rows (not a lagging pipeline-stats GET).
  const savedCount = findings.filter((item) => item.user_status === "save").length;
  const pitchedCount = findings.filter(
    (item) => item.user_status === "pitched" || item.user_status === "won",
  ).length;
  const wonCount = findings.filter((item) => item.user_status === "won").length;
  const highFitCount = useMemo(
    () => findings.filter((item) => item.score >= 0.7 && item.user_status !== "skip").length,
    [findings],
  );
  const visibleJobs = useMemo(() => {
    const marketplacePattern = /(freelancer|upwork|fiverr|peopleperhour|guru\.com|truelancer)/i;
    const nonOpportunityUrlPattern =
      /(\/blogs?\/|\/articles?\/|\/guides?\/|\/tutorials?\/|\/tenders?\/|\/procurement\/|\/rfp\/|tendersontime\.com|tendertiger\.com|biddetail\.com|globaltenders\.com|dgmarket\.com|unjobsapp\.org|hays\.co\.uk|hays\.com|djangojob\.com|jobgether\.com|twine\.net|contractoruk\.com|jobs\.ac\.uk|pinpointhq\.com|search-careers\.gm\.com|nyscr\.ny\.gov|jobserve\.com|notify\.careers|jobmail\.co\.za|itjobboard\.co\.uk|vollna\.com|upwork\.com|freelancer\.com|peopleperhour\.com)/i;
    const nonOpportunityTextPattern =
      /(\btop\s+\d+\b|\b\d+\s+best\b|\bbest\s+(?:freelance|remote)\b|\bhow\s+to\s+(?:become|hire|find|get)\b|\b(?:ultimate|complete)\s+guide\b|\be-?tenders?\b|\btender\s+(?:notice|no\.?|number|id|document|for)\b|\binvitation\s+(?:to|for)\s+(?:tender|bids?)\b|\brequest\s+for\s+(?:proposals?|quotations?|tenders?)\b|\bpublic\s+procurement\b|\bgovernment\s+tender\b)/i;
    const excludes = (prefs?.exclude_keywords || [])
      .map((kw) => kw.trim().toLowerCase())
      .filter(Boolean);
    const allowedSources = (prefs?.sources || [])
      .map((src) => src.trim().toLowerCase())
      .filter(Boolean);

    return jobs.filter((job) => {
      const source = (job.source_name || "").toLowerCase();
      const company = (job.company || "").toLowerCase();
      const url = (job.url || "").toLowerCase();
      const title = (job.title || "").toLowerCase();
      const description = (job.description || "").toLowerCase();

      if (
        marketplacePattern.test(source) ||
        marketplacePattern.test(company) ||
        marketplacePattern.test(url)
      ) {
        return false;
      }

      if (
        nonOpportunityUrlPattern.test(url) ||
        nonOpportunityTextPattern.test(`${title} ${description}`)
      ) {
        return false;
      }

      if (allowedSources.length > 0 && source && !allowedSources.includes(source)) {
        return false;
      }

      if (excludes.length > 0) {
        const haystack = `${title} ${description} ${company} ${source} ${url}`;
        if (excludes.some((kw) => haystack.includes(kw))) {
          return false;
        }
      }

      return true;
    });
  }, [jobs, prefs]);
  const firstName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "there";
  const digestLine = formatDigestSummary(prefs);

  if (!authed) {
    return (
      <div className="flex flex-1 flex-col gap-14">
        <section className="rounded-[1.25rem] border border-[var(--border)] bg-[var(--surface)] px-6 py-14 md:px-12 md:py-20">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold tracking-[0.22em] text-[var(--accent)] uppercase">
              Signal Desk
            </p>
            <h1
              className="mt-3 text-4xl leading-[1.08] tracking-tight text-[var(--text)] md:text-6xl"
              style={{ fontFamily: "var(--font-display), Georgia, serif" }}
            >
              Find actionable freelance work outside bid wars
            </h1>
            <p className="mt-5 max-w-xl text-lg text-[var(--text-secondary)]">
              Set Hunt Rules once. We surface public contract posts from the open web and company boards, rank them for
              fit, and email a short digest. You pitch on the original listing — we never invent jobs or auto-apply.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/auth?mode=register"
                className="inline-flex h-10 items-center rounded-[var(--radius)] bg-[var(--accent)] px-5 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
              >
                Start free
              </Link>
              <Link
                href="/pricing"
                className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-5 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
              >
                See pricing
              </Link>
            </div>
          </div>
        </section>

        <section className="grid gap-8 md:grid-cols-2" aria-labelledby="discovery-heading">
          <div className="border-t border-[var(--border)] pt-5">
            <h2 id="discovery-heading" className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              External discovery
            </h2>
            <p className="mt-3 text-[var(--text-secondary)]">
              Default product: hunters fill a shared pool from public sources (search, ATS-style company pages,
              communities). You open the original link. Application fees on third-party boards — if known — are labeled;
              unknowns stay unknown.
            </p>
          </div>
          <div className="border-t border-[var(--border)] pt-5">
            <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Native marketplace
            </h2>
            <p className="mt-3 text-[var(--text-secondary)]">
              Opt-in native jobs, mutual matching, and provider-backed payments are a separate track — not required to use
              the discovery desk. Marketplace nav stays feature-flagged until enabled.
            </p>
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

        <section className="border-t border-[var(--border)] pt-8" aria-labelledby="fees-heading">
          <h2 id="fees-heading" className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Fees, clearly
          </h2>
          <ul className="mt-4 space-y-2 text-sm text-[var(--text-secondary)]">
            <li>Signal Desk subscriptions sell productivity tools — never paid visibility on native jobs.</li>
            <li>We do not charge pay-per-application for native listings.</li>
            <li>External boards may charge their own apply fees; we show them when known and label unknowns.</li>
            <li>Subscription price and applicable taxes are shown at checkout when it is enabled. Signal Desk does not currently collect marketplace payments or provide escrow.</li>
          </ul>
          <Link href="/pricing" className="mt-4 inline-block text-sm font-semibold text-[var(--accent)] hover:underline">
            Compare Free vs Pro →
          </Link>
        </section>

        <section className="border-t border-[var(--border)] pt-8" aria-labelledby="faq-heading">
          <h2 id="faq-heading" className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            FAQ
          </h2>
          <dl className="mt-4 space-y-5 text-sm">
            {[
              {
                q: "Do you auto-apply for me?",
                a: "No. Leads open the original listing. Drafts stay in your control.",
              },
              {
                q: "Are jobs synthetic?",
                a: "Inventory is collected through the source adapters enabled for the service. Availability and freshness vary; verify each opportunity on its original listing before applying.",
              },
              {
                q: "What does Free include?",
                a: "Hunt Rules, ranked Leads from the shared pool, and a capped digest. Pro raises limits and unlocks premium source options when configured.",
              },
            ].map((item) => (
              <div key={item.q}>
                <dt className="font-semibold text-[var(--text)]">{item.q}</dt>
                <dd className="mt-1 text-[var(--text-secondary)]">{item.a}</dd>
              </div>
            ))}
          </dl>
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
                {loading
                  ? "Loading live contract opportunities from our shared hunt pool…"
                  : total > 0
                    ? `${total} contract opportunities indexed in the shared pool (latest ${Math.min(total, 300)} scanned per hunt) across direct client posts, ATS boards, and developer communities.`
                    : "Contract opportunities sourced across direct client posts, ATS boards, and developer communities."}
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

          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : visibleJobs.length === 0 ? (
            <EmptyState
              title="No public sample listings yet"
              description="Start free, verify email, set Hunt Rules — then open Leads when the desk has fits."
              actionHref="/help"
              actionLabel="How it works"
            />
          ) : (
            <div className="divide-y divide-[var(--border)] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-sm">
              {visibleJobs.map((job) => (
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
                  href="/auth?mode=register"
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

          <div className="mt-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold tracking-wider text-[var(--accent)] uppercase">
                  Contract Directory by Skill
                </p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text)]">
                  Explore live freelance & contract roles by specialty
                </h3>
              </div>
              <Link
                href="/freelance-jobs"
                className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--accent)] hover:underline"
              >
                All skill directories
                <ArrowRight className="size-3.5" />
              </Link>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                { slug: "python", label: "Python Contracts" },
                { slug: "react", label: "React & Next.js" },
                { slug: "fastapi", label: "FastAPI" },
                { slug: "typescript", label: "TypeScript" },
                { slug: "ai-ml", label: "AI & LLM Engineering" },
                { slug: "devops", label: "DevOps & Cloud" },
                { slug: "golang", label: "Golang" },
                { slug: "nodejs", label: "Node.js" },
              ].map((cat) => (
                <Link
                  key={cat.slug}
                  href={`/freelance-jobs/${cat.slug}`}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-3.5 py-2 text-xs font-medium text-[var(--text)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                >
                  {cat.label}
                </Link>
              ))}
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

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2
            className="text-lg text-[var(--text)]"
            style={{ fontFamily: "var(--font-display), Georgia, serif" }}
          >
            Your Hunt Rules
          </h2>
          <div className="mt-3">
            <HuntRulesPreview prefs={prefs} />
          </div>
          <Link
            href="/preferences?tab=matching"
            className="mt-4 inline-block text-sm font-semibold text-[var(--accent)] hover:underline"
          >
            Edit Hunt Rules →
          </Link>
        </Card>
        <EarningsCalculator />
      </div>

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
            hint: "Saved across Desk, Leads, and Pipeline",
          },
          {
            label: "Opportunities stored",
            value: total,
            icon: Radar,
            hint: findingsMeta?.total_scanned
              ? `Shared pool (${findingsMeta.total_scanned} recent scanned)`
              : "Shared hunt inventory",
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
        <Card className="p-5 lg:col-span-3" data-testid="pipeline-analytics-card">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-[var(--text)]">Pipeline & Win-Rate Analytics</h2>
              <p className="text-xs text-[var(--text-muted)]">
                Your conversion funnel from saved opportunities to pitched and won contracts
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <Link
                href="/pipeline"
                className="rounded-md border border-[var(--accent)]/40 bg-[var(--accent-muted)] px-2.5 py-1 text-[var(--accent)] hover:border-[var(--accent)]"
              >
                Open Pipeline workspace
              </Link>
              {loading ? (
                <>
                  <Skeleton className="h-7 w-20" />
                  <Skeleton className="h-7 w-20" />
                  <Skeleton className="h-7 w-16" />
                </>
              ) : (
                <>
                  <Link
                    href="/leads?filter=saved"
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                  >
                    Saved ({savedCount})
                  </Link>
                  <Link
                    href="/leads?filter=pitched"
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                  >
                    Pitched ({pitchedCount})
                  </Link>
                  <Link
                    href="/leads?filter=won"
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                  >
                    Won ({wonCount})
                  </Link>
                </>
              )}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {loading ? (
              <>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className="mt-3 h-8 w-16" />
                  <Skeleton className="mt-2 h-3 w-36" />
                </div>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="mt-3 h-8 w-16" />
                  <Skeleton className="mt-2 h-3 w-32" />
                </div>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="mt-3 h-8 w-24" />
                  <Skeleton className="mt-2 h-3 w-40" />
                </div>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className="mt-3 h-8 w-24" />
                  <Skeleton className="mt-2 h-3 w-36" />
                </div>
              </>
            ) : (
              <>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <p className="text-xs text-[var(--text-muted)]">Pitch conversion rate</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--text)]">
                    {Math.round((pipelineStats?.pitch_rate ?? 0) * 100)}%
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                    {pitchedCount} pitched of {savedCount} saved
                  </p>
                </div>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <p className="text-xs text-[var(--text-muted)]">Win rate</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--success)]">
                    {Math.round((pipelineStats?.win_rate ?? 0) * 100)}%
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                    {wonCount} won of {pitchedCount} pitched
                  </p>
                </div>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <p className="text-xs text-[var(--text-muted)]">Active pipeline value</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--text)]">
                    ${(pipelineStats?.active_pipeline_value ?? 0).toLocaleString()}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">Estimated across saved & pitched</p>
                </div>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3.5">
                  <p className="text-xs text-[var(--text-muted)]">Won contract value</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--accent)]">
                    ${(pipelineStats?.won_value ?? 0).toLocaleString()}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">Closed freelance revenue</p>
                </div>
              </>
            )}
          </div>
        </Card>

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
          {loading || scraping ? (
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
                    <Badge variant="accent">{Math.round(item.score * 100)}% fit</Badge>
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
                <dt className="text-[var(--text-muted)]">Shared pool</dt>
                <dd className="text-[var(--text)]">
                  {loading ? (
                    <Skeleton className="inline-block h-4 w-20 align-middle" />
                  ) : (
                    `${total} indexed`
                  )}
                </dd>
              </div>
              {findingsMeta?.total_scanned ? (
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">Recent scan window</dt>
                  <dd className="text-[var(--text)]">{findingsMeta.total_scanned} scanned</dd>
                </div>
              ) : null}
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
            <p className="mt-1 text-sm text-[var(--text-muted)]">
              {loading ? "Loading inventory…" : `${total} opportunities stored`}
            </p>
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
        {loading ? (
          <div className="divide-y divide-[var(--border)] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)]">
            <Skeleton className="h-16 w-full rounded-none" />
            <Skeleton className="h-16 w-full rounded-none" />
            <Skeleton className="h-16 w-full rounded-none" />
          </div>
        ) : visibleJobs.length === 0 ? (
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
            {visibleJobs.map((job) => (
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
