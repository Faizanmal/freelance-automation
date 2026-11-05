"use client";



import Link from "next/link";

import { useRouter, useSearchParams } from "next/navigation";

import { Suspense, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import {

  draftProposal,
  reportJobExpired,

  getAuthFindings,

  getDemoFindings,

  getToken,

  setLeadAction,

  submitApplication,

  type ApplyFormFields,

  type LeadFinding,

  type LeadFindingsResponse,

  type ProposalDraftResponse,

} from "@/lib/api";

import { motion, AnimatePresence } from "framer-motion";

import { Card } from "@/components/ui/card";

import { Button } from "@/components/ui/button";

import { Badge } from "@/components/ui/badge";

import { EmptyState } from "@/components/ui/empty-state";

import { MatchScore, MatchScoreBar } from "@/components/ui/match-score";

import { PageHeader } from "@/components/ui/page-header";

import { Skeleton } from "@/components/ui/skeleton";

import { ExternalLink, Filter } from "lucide-react";

import { cn } from "@/lib/cn";

import { openSafeExternalUrl } from "@/lib/security";



const DEFAULT_KEYWORDS = "python,react,fastapi,typescript,remote";



const ACTION_LABEL: Record<LeadFinding["action"], string> = {

  draft_bid: "Draft",

  watch: "Watch",

  skip: "Skip",

};



type StatusFilter = "all" | "new" | "high" | "saved" | "pitched" | "skipped";



const emptyForm = (): ApplyFormFields => ({

  proposal: "",

  bid_amount: null,

  currency: "USD",

  delivery_days: 7,

  milestone_plan: "",

  milestone_percentage: 100,

  submit_mode: "unsupported",

});



function LeadsPageInner() {

  const router = useRouter();

  const searchParams = useSearchParams();

  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);

  const [freelanceFocus, setFreelanceFocus] = useState(true);

  const [sourceFilter, setSourceFilter] = useState("all");

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(() => {

    const raw = searchParams.get("filter");

    if (raw === "saved" || raw === "pitched" || raw === "skipped" || raw === "new" || raw === "high" || raw === "all") {

      return raw;

    }

    return "all";

  });

  const [search, setSearch] = useState("");

  const [data, setData] = useState<LeadFindingsResponse | null>(null);

  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [draftMeta, setDraftMeta] = useState<ProposalDraftResponse | null>(null);

  const [form, setForm] = useState<ApplyFormFields>(emptyForm());

  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [pending, startTransition] = useTransition();

  const [authed, setAuthed] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(getToken());
  });



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

        const message = err instanceof Error ? err.message : "Failed to load leads";

        if (/no jobs in the database/i.test(message) || /call post \/jobs\/scrape/i.test(message)) {

          setError(null);

          setData({

            generated_at: new Date().toISOString(),

            total_scanned: 0,

            total_matched: 0,

            total_findings: 0,

            freelance_focus: focus,

            action_counts: { draft_bid: 0, watch: 0, skip: 0 },

            keywords: value.split(",").map((part) => part.trim()).filter(Boolean),

            items: [],

          });

          return;

        }

        setError(message);

        setData(null);

      }

    });

  }, []);



  useEffect(() => {

    load(DEFAULT_KEYWORDS, true);

  }, [load]);



  const filterParam = searchParams.get("filter");
  const [prevFilterParam, setPrevFilterParam] = useState(filterParam);
  if (prevFilterParam !== filterParam) {
    setPrevFilterParam(filterParam);
    if (
      filterParam === "saved" ||
      filterParam === "pitched" ||
      filterParam === "skipped" ||
      filterParam === "new" ||
      filterParam === "high" ||
      filterParam === "all"
    ) {
      setStatusFilter(filterParam);
    }
  }



  const makeDraft = useCallback(

    (jobId: number) => {

      if (!getToken()) {

        router.push("/auth");

        return;

      }

      startTransition(async () => {

        try {

          setError(null);

          setSubmitMessage(null);

          const response = await draftProposal(jobId);

          setActiveJobId(jobId);

          setDraftMeta(response);

          setForm({

            proposal: response.form_fields.proposal || response.draft,

            bid_amount: response.form_fields.bid_amount ?? null,

            currency: response.form_fields.currency || "USD",

            delivery_days: response.form_fields.delivery_days ?? 7,

            milestone_plan: response.form_fields.milestone_plan || "",

            milestone_percentage: response.form_fields.milestone_percentage ?? 100,

            source_name: response.form_fields.source_name || response.source_name,

            source_id: response.form_fields.source_id,

            project_url: response.form_fields.project_url || response.source_url,

            submit_mode: response.form_fields.submit_mode || "unsupported",

          });

        } catch (err) {

          setError(err instanceof Error ? err.message : "Draft failed");

        }

      });

    },

    [router],

  );



  useEffect(() => {

    const jobParam = searchParams.get("job");

    if (!jobParam) return;

    const jobId = Number(jobParam);

    if (!Number.isFinite(jobId) || jobId <= 0) return;

    if (!getToken()) {

      router.push("/auth");

      return;

    }

    makeDraft(jobId);

  }, [searchParams, router, makeDraft]);



  useEffect(() => {

    if (!draftMeta || !activeJobId) return;

    const onKey = (event: KeyboardEvent) => {

      if (event.key === "Escape") {

        setActiveJobId(null);

        setDraftMeta(null);

        setForm(emptyForm());

        setSubmitMessage(null);

      }

    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);

  }, [draftMeta, activeJobId]);



  const confirmSubmit = () => {

    if (!activeJobId) return;

    if (!getToken()) {

      router.push("/auth");

      return;

    }

    startTransition(async () => {

      try {

        setError(null);

        setSubmitMessage(null);

        const result = await submitApplication(activeJobId, form, true);

        setSubmitMessage(

          result.detail ||

            `${result.status} via ${result.submit_mode}${

              result.external_id ? ` (id ${result.external_id})` : ""

            }`,

        );

        if (result.apply_url && (result.submit_mode === "external_apply" || result.status === "prepared")) {

          openSafeExternalUrl(result.apply_url);

        }

      } catch (err) {

        setError(err instanceof Error ? err.message : "Submit failed");

      }

    });

  };



  const closeDraft = () => {

    setActiveJobId(null);

    setDraftMeta(null);

    setForm(emptyForm());

    setSubmitMessage(null);

  };



  const handleReportExpired = (jobId: number) => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        await reportJobExpired(jobId, "dead_link");
        await load(keywords, freelanceFocus);
        setSubmitMessage("Reported as dead/closed link. It will be pruned.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not report link");
      }
    });
  };

  const updateLeadStatus = (jobId: number, status: "save" | "skip" | "pitched" | "won" | "clear") => {

    if (!getToken()) {

      router.push("/auth");

      return;

    }

    // Optimistic local update

    setData((current) => {

      if (!current) return current;

      return {

        ...current,

        items: current.items.map((item) =>

          item.job_id === jobId

            ? { ...item, user_status: status === "clear" ? null : status }

            : item,

        ),

      };

    });

    startTransition(async () => {

      try {

        setError(null);

        await setLeadAction(jobId, status);

        await load(keywords, freelanceFocus);

        setSubmitMessage(

          status === "save"

            ? "Lead saved"

            : status === "pitched"

              ? "Lead marked as pitched"

              : status === "won"

                ? "Lead marked as won"

                : status === "skip"

                  ? "Lead skipped — hidden from default list"

                  : "Lead status cleared",

        );

      } catch (err) {

        setError(err instanceof Error ? err.message : "Could not update lead");

        await load(keywords, freelanceFocus);

      }

    });

  };



  const sources = useMemo(() => {

    const names = new Set<string>();

    for (const item of data?.items || []) {

      if (item.source_name) names.add(item.source_name);

    }

    return Array.from(names).sort();

  }, [data]);



  const visibleItems = useMemo(() => {

    const query = search.trim().toLowerCase();

    const items = [...(data?.items || [])].sort((a, b) => {

      const aScore = a.score * 0.7 + (a.freshness_score || 0) * 0.3;

      const bScore = b.score * 0.7 + (b.freshness_score || 0) * 0.3;

      return bScore - aScore;

    });

    return items.filter((item) => {

      if (sourceFilter !== "all" && item.source_name !== sourceFilter) return false;

      if (statusFilter === "saved" && item.user_status !== "save") return false;

      if (statusFilter === "pitched" && item.user_status !== "pitched" && item.user_status !== "won") return false;

      if (statusFilter === "skipped" && item.user_status !== "skip") return false;

      if (statusFilter === "high" && item.score < 0.7) return false;

      if (statusFilter === "new" && item.user_status) return false;

      if (query) {

        const haystack = [item.title, item.company, item.source_name, item.why, ...(item.matched_keywords || [])]

          .filter(Boolean)

          .join(" ")

          .toLowerCase();

        if (!haystack.includes(query)) return false;

      }

      return true;

    });

  }, [data, sourceFilter, statusFilter, search]);



  const selected = useMemo(

    () => visibleItems.find((item) => item.job_id === selectedId) || null,

    [visibleItems, selectedId],

  );



  const isExternalApply = form.submit_mode === "external_apply";

  const canDirectSubmit = form.submit_mode === "api_bid" || form.submit_mode === "email_apply";

  const drawerOpen = Boolean(draftMeta && activeJobId);



  const statusTabs: { id: StatusFilter; label: string }[] = [

    { id: "all", label: "All" },

    { id: "new", label: "New" },

    { id: "high", label: "High match" },

    { id: "saved", label: "Saved" },

    { id: "pitched", label: "Pitched" },

    { id: "skipped", label: "Skipped" },

  ];



  return (

    <div className="flex flex-1 flex-col gap-6">

      <PageHeader

        title={authed ? "Your Opportunities" : "Sample leads"}

        description={

          authed

            ? "Relevant freelance and contract work, ranked for you."

            : "Preview of how ranking works. Sign in to use your Hunt Rules, Save/Skip, and digests."

        }

        actions={

          <>

            <Button type="button" variant="outline" onClick={() => load(keywords, freelanceFocus)} disabled={pending}>

              {pending ? "Working…" : "Refresh leads"}

            </Button>

            {authed ? (

              <Link

                href="/preferences?tab=matching"

                className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"

              >

                Edit Hunt Rules

              </Link>

            ) : (

              <Link

                href="/auth"

                className="inline-flex h-10 items-center rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)]"

              >

                Sign in

              </Link>

            )}

          </>

        }

      />



      {!authed && !pending && data !== null ? (

        <p className="text-sm text-[var(--text-muted)]">

          <Link href="/auth" className="text-[var(--accent)] hover:underline">

            Sign in

          </Link>{" "}

          to unlock your personal lead desk.

        </p>

      ) : null}



      <div className="flex flex-col gap-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-3">

        <div className="flex flex-wrap items-center gap-2">

          <Filter className="size-4 text-[var(--text-muted)]" />

          {statusTabs.map((tab) => (

            <button

              key={tab.id}

              type="button"

              onClick={() => setStatusFilter(tab.id)}

              className={cn(

                "rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",

                statusFilter === tab.id

                  ? "bg-[var(--accent-muted)] text-[var(--accent)]"

                  : "text-[var(--text-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]",

              )}

            >

              {tab.label}

            </button>

          ))}

        </div>

        <div className="flex flex-wrap items-center gap-3">

          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--text)]">

            <input

              type="checkbox"

              checked={freelanceFocus}

              onChange={(event) => {

                const next = event.target.checked;

                setFreelanceFocus(next);

                load(keywords, next);

              }}

              className="size-4 rounded accent-[var(--accent)]"

            />

            Freelance focus

          </label>

          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">

            Source

            <select

              value={sourceFilter}

              onChange={(event) => setSourceFilter(event.target.value)}

              className="sd-input w-auto py-1.5"

            >

              <option value="all">All sources</option>

              {sources.map((name) => (

                <option key={name} value={name}>

                  {name}

                </option>

              ))}

            </select>

          </label>

          <input

            value={search}

            onChange={(event) => setSearch(event.target.value)}

            placeholder="Search title, company, skills…"

            className="sd-input max-w-sm flex-1"

            aria-label="Search opportunities"

          />

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

              className="sd-input min-w-[260px] flex-1"

              placeholder="python, fastapi, next.js"

            />

            <Button type="submit" disabled={pending}>

              {pending ? "Working…" : "Refresh leads"}

            </Button>

          </form>

        ) : (

          <p className="text-sm text-[var(--text-muted)]">Using your saved preferences</p>

        )}

      </div>



      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}

      {submitMessage ? <p className="text-sm text-[var(--success)]">{submitMessage}</p> : null}



      {data ? (

        <section className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-3 text-sm text-[var(--text-secondary)]">

          {!authed ? (

            <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--warning)] uppercase">

              Sample leads — not your Hunt Rules

            </p>

          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3">

            <p>

              <span className="text-[var(--text)]">Scanned {data.total_scanned}</span> · matched {data.total_matched} ·

              showing {visibleItems.length}

              {data.freelance_focus ? " · freelance focus on" : " · all matches"}

              {data.generated_at ? ` · updated ${new Date(data.generated_at).toLocaleString()}` : ""}

            </p>

            <div className="flex flex-wrap gap-2">

              <Badge variant="outline">Draft: {data.action_counts.draft_bid}</Badge>

              <Badge variant="accent">Watch: {data.action_counts.watch}</Badge>

              <Badge variant="danger">Skip: {data.action_counts.skip}</Badge>

            </div>

          </div>

        </section>

      ) : null}



      {pending && !data ? (

        <div className="grid gap-3">

          <Skeleton className="h-40 w-full" />

          <Skeleton className="h-40 w-full" />

        </div>

      ) : null}



      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">

        <div className="grid gap-3">

          {visibleItems.map((finding) => (

            <Card

              key={finding.job_id}

              interactive

              className={cn(

                "flex cursor-pointer flex-col p-5",

                selectedId === finding.job_id && "border-[var(--accent)]/50 ring-1 ring-[var(--accent)]/30",

              )}

              onClick={() => setSelectedId(finding.job_id)}

            >

              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">

                <div className="min-w-0">

                  <h2 className="text-lg font-medium text-[var(--text)]">{finding.title}</h2>

                  <p className="mt-1 text-sm text-[var(--text-secondary)]">

                    {[finding.company, finding.source_label || finding.source_attribution || finding.source_name]

                      .filter(Boolean)

                      .join(" · ")}

                  </p>

                </div>

                <div className="flex flex-wrap items-center gap-2">

                  <MatchScore score={finding.score} />

                  {finding.budget_label ? (

                    <Badge variant="outline">{finding.budget_label}</Badge>

                  ) : null}

                  {finding.freelance_benefits?.length ? (

                    <Badge variant="muted">{finding.freelance_benefits[0]}</Badge>

                  ) : typeof finding.freelance_fit === "number" && finding.freelance_fit >= 0.7 ? (

                    <Badge variant="muted">Contract / Freelance</Badge>

                  ) : null}

                  <Badge

                    variant={

                      finding.action === "draft_bid"

                        ? "accent"

                        : finding.action === "watch"

                          ? "outline"

                          : "danger"

                    }

                  >

                    {ACTION_LABEL[finding.action]}

                  </Badge>

                  {finding.user_status === "save" ? <Badge variant="success">Saved</Badge> : null}

                  {finding.user_status === "pitched" ? <Badge variant="accent">Pitched</Badge> : null}

                  {finding.user_status === "won" ? <Badge variant="success">Won</Badge> : null}

                </div>

              </div>



              <p className="mb-3 text-sm leading-relaxed text-[var(--text)]">{finding.why}</p>

              {finding.freelance_benefits_line ? (

                <p className="mb-3 text-sm text-[var(--accent)]">{finding.freelance_benefits_line}</p>

              ) : null}



              <div className="mb-4 grid gap-3 md:grid-cols-2">

                {finding.signals.length > 0 ? (

                  <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-3">

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">

                      Signals

                    </p>

                    <ul className="space-y-1 text-sm text-[var(--text-secondary)]">

                      {finding.signals.slice(0, 4).map((signal) => (

                        <li key={signal}>+ {signal}</li>

                      ))}

                    </ul>

                  </div>

                ) : null}

                {finding.risks.length > 0 ? (

                  <div className="rounded-md border border-[var(--danger)]/20 bg-[var(--danger-muted)] p-3">

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">

                      Watchouts

                    </p>

                    <ul className="space-y-1 text-sm text-[var(--danger)]">

                      {finding.risks.slice(0, 4).map((risk) => (

                        <li key={risk}>! {risk}</li>

                      ))}

                    </ul>

                  </div>

                ) : null}

              </div>



              <div

                className="mt-auto flex flex-wrap gap-2 border-t border-[var(--border)] pt-4"

                onClick={(event) => event.stopPropagation()}

              >

                <Button

                  variant="default"

                  size="sm"

                  onClick={() => openSafeExternalUrl(finding.apply_url || finding.url)}

                >

                  <ExternalLink className="size-3.5" />

                  Open original

                </Button>

                {authed ? (

                  <>

                    <Button

                      variant="outline"

                      size="sm"

                      onClick={() =>

                        updateLeadStatus(

                          finding.job_id,

                          finding.user_status === "save" ? "clear" : "save",

                        )

                      }

                    >

                      {finding.user_status === "save" ? "Unsave" : "Save"}

                    </Button>

                    <Button

                      variant={finding.user_status === "pitched" ? "default" : "outline"}

                      size="sm"

                      onClick={() =>

                        updateLeadStatus(

                          finding.job_id,

                          finding.user_status === "pitched" ? "clear" : "pitched",

                        )

                      }

                    >

                      {finding.user_status === "pitched" ? "Pitched ✓" : "Mark pitched"}

                    </Button>

                    <Button variant="ghost" size="sm" onClick={() => updateLeadStatus(finding.job_id, "skip")}>

                      Skip

                    </Button>

                    <Button

                      variant="ghost"

                      size="sm"

                      className="text-[var(--text-muted)] hover:text-[var(--danger)]"

                      title="Report listing as closed or dead link"

                      onClick={() => handleReportExpired(finding.job_id)}

                    >

                      Dead link

                    </Button>

                  </>

                ) : null}

                {finding.action === "draft_bid" ? (

                  <Button variant="secondary" size="sm" onClick={() => makeDraft(finding.job_id)}>

                    Draft bid

                  </Button>

                ) : null}

              </div>

            </Card>

          ))}



          {!pending && data && visibleItems.length === 0 && !error ? (

            <EmptyState

              title={data.total_scanned === 0 ? "No opportunities yet" : "No leads in this view"}

              description={

                data.total_scanned === 0

                  ? "Hunters are still filling the pool (or the backend was paused). Set Hunt Rules and refresh inventory from the Desk — empty is expected until the first successful hunt."

                  : sourceFilter !== "all" || statusFilter !== "all" || search

                    ? "Try clearing filters or search."

                    : "Widen Hunt Rules keywords, or turn off Freelance focus."

              }

              actionHref="/preferences?tab=matching"

              actionLabel="Edit Hunt Rules"

              secondaryHref="/"

              secondaryLabel="Desk"

            />

          ) : null}

        </div>



        <aside className="hidden xl:block">

          <div className="sticky top-20 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-5">

            {selected ? (

              <div className="space-y-4">

                <div>

                  <h3

                    className="text-xl text-[var(--text)]"

                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}

                  >

                    {selected.title}

                  </h3>

                  <p className="mt-1 text-sm text-[var(--text-secondary)]">

                    {[selected.company, selected.source_label || selected.source_name].filter(Boolean).join(" · ")}

                  </p>

                </div>

                <MatchScoreBar score={selected.score} />

                <p className="text-xs text-[var(--text-muted)]">

                  Match scores are estimates from your Hunt Rules — not verified guarantees.

                </p>

                {selected.description_excerpt ? (

                  <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{selected.description_excerpt}</p>

                ) : (

                  <p className="text-sm text-[var(--text-muted)]">Full description lives on the original listing.</p>

                )}

                {selected.matched_keywords?.length ? (

                  <div>

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">

                      Matched skills

                    </p>

                    <div className="flex flex-wrap gap-1.5">

                      {selected.matched_keywords.map((kw) => (

                        <Badge key={kw} variant="outline">

                          {kw}

                        </Badge>

                      ))}

                    </div>

                  </div>

                ) : null}

                {selected.red_flags?.length ? (

                  <div>

                    <p className="mb-2 text-xs font-semibold tracking-wide text-[var(--danger)] uppercase">Risks</p>

                    <ul className="space-y-1 text-sm text-[var(--danger)]">

                      {selected.red_flags.map((flag) => (

                        <li key={flag}>{flag}</li>

                      ))}

                    </ul>

                  </div>

                ) : null}

                {selected.application ? (

                  <div className="rounded-md border border-[var(--accent)]/30 bg-[var(--accent-muted)] p-3">

                    <div className="flex items-center justify-between">

                      <p className="text-xs font-semibold tracking-wide text-[var(--accent)] uppercase">

                        Your Pitch ({selected.application.status})

                      </p>

                      {selected.application.bid_amount ? (

                        <span className="text-xs font-semibold text-[var(--text)]">

                          ${selected.application.bid_amount.toLocaleString()} {selected.application.currency || "USD"}

                        </span>

                      ) : null}

                    </div>

                    <p className="mt-2 text-xs text-[var(--text-secondary)] whitespace-pre-line line-clamp-4">

                      {selected.application.proposal}

                    </p>

                  </div>

                ) : null}

                <Button

                  className="w-full"

                  onClick={() => openSafeExternalUrl(selected.apply_url || selected.url)}

                >

                  Open original

                </Button>

              </div>

            ) : (

              <div>

                <h3 className="text-lg font-semibold text-[var(--text)]">Opportunity detail</h3>

                <p className="mt-2 text-sm text-[var(--text-muted)]">

                  Select a lead to inspect match signals, risks, and source attribution.

                </p>

              </div>

            )}

          </div>

        </aside>

      </div>



      <AnimatePresence>

        {drawerOpen ? (

          <>

            <motion.button

              type="button"

              aria-label="Close draft drawer"

              initial={{ opacity: 0 }}

              animate={{ opacity: 1 }}

              exit={{ opacity: 0 }}

              className="fixed inset-0 z-40 bg-black/60"

              onClick={closeDraft}

            />

            <motion.aside

              role="dialog"

              aria-modal="true"

              aria-labelledby="draft-drawer-title"

              initial={{ x: "100%" }}

              animate={{ x: 0 }}

              exit={{ x: "100%" }}

              transition={{ type: "spring", stiffness: 320, damping: 32 }}

              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-md)]"

            >

              <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-6 py-5">

                <div>

                  <h2

                    id="draft-drawer-title"

                    className="text-2xl"

                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}

                  >

                    Draft bid

                  </h2>

                  <p className="mt-1 text-sm text-[var(--text-muted)]">

                    {draftMeta?.title} · {draftMeta?.source_name} · {form.submit_mode}

                  </p>

                </div>

                <Button type="button" variant="ghost" onClick={closeDraft}>

                  Close

                </Button>

              </div>

              <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">

                <p className="text-sm text-[var(--text-secondary)]">{draftMeta?.disclaimer}</p>

                <label className="sd-label">

                  <span>Proposal</span>

                  <textarea

                    value={form.proposal}

                    onChange={(event) => setForm((current) => ({ ...current, proposal: event.target.value }))}

                    rows={10}

                    className="sd-input"

                  />

                </label>

                <div className="grid gap-4 sm:grid-cols-3">

                  <label className="sd-label">

                    <span>Bid amount</span>

                    <input

                      type="number"

                      value={form.bid_amount ?? ""}

                      onChange={(event) =>

                        setForm((current) => ({

                          ...current,

                          bid_amount: event.target.value === "" ? null : Number(event.target.value),

                        }))

                      }

                      className="sd-input"

                    />

                  </label>

                  <label className="sd-label">

                    <span>Currency</span>

                    <input

                      value={form.currency}

                      onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))}

                      className="sd-input"

                    />

                  </label>

                  <label className="sd-label">

                    <span>Delivery days</span>

                    <input

                      type="number"

                      value={form.delivery_days ?? ""}

                      onChange={(event) =>

                        setForm((current) => ({

                          ...current,

                          delivery_days: event.target.value === "" ? null : Number(event.target.value),

                        }))

                      }

                      className="sd-input"

                    />

                  </label>

                </div>

                <label className="sd-label">

                  <span>Milestone plan</span>

                  <textarea

                    value={form.milestone_plan || ""}

                    onChange={(event) => setForm((current) => ({ ...current, milestone_plan: event.target.value }))}

                    rows={3}

                    className="sd-input"

                  />

                </label>

                <p className="text-sm text-[var(--text-muted)]">

                  {isExternalApply

                    ? "Confirm saves your draft and opens the listing. You stay in control."

                    : canDirectSubmit

                      ? "Review the draft, then confirm. Signal Desk only sends after this click."

                      : "Direct submit is unavailable for this source. Open the listing to apply."}

                </p>

              </div>

              <div className="flex flex-wrap gap-3 border-t border-[var(--border)] px-6 py-4">

                {canDirectSubmit || isExternalApply ? (

                  <Button type="button" disabled={pending} onClick={confirmSubmit}>

                    {pending

                      ? "Working…"

                      : isExternalApply

                        ? "Confirm draft & open listing"

                        : "Confirm & submit"}

                  </Button>

                ) : null}

                {form.project_url ? (

                  <Button variant="outline" onClick={() => openSafeExternalUrl(form.project_url)}>

                    Open listing

                  </Button>

                ) : null}

              </div>

            </motion.aside>

          </>

        ) : null}

      </AnimatePresence>

    </div>

  );

}



export default function LeadsPage() {

  return (

    <Suspense

      fallback={

        <div className="flex flex-1 flex-col gap-6">

          <Skeleton className="h-10 w-64" />

          <Skeleton className="h-40 w-full" />

          <p className="text-[var(--text-muted)]">Loading leads…</p>

        </div>

      }

    >

      <LeadsPageInner />

    </Suspense>

  );

}

