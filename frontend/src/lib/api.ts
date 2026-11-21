const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const TOKEN_KEY = "signal_desk_token";
const REFRESH_KEY = "signal_desk_refresh";

const TOKEN_CHANGE_EVENT = "signal-desk-token-change";



export type Job = {

  id: number;

  source_name: string;

  source_id: string;

  title: string;

  description: string;

  url: string;

  company?: string | null;

  location?: string | null;

  tags?: string[];

  budget_min?: number | null;

  budget_max?: number | null;

  posted_at?: string | null;

  seniority?: string | null;

  analysis_summary?: string | null;

  enrichment?: {

    skills?: string[];

    provider?: string;

    summary?: string;

  };

  match_score?: number;

  matched_keywords?: string[];

  match_reasons?: string[];

  freshness_score?: number;

  client_quality_score?: number;

  red_flags?: string[];

  source_attribution?: string | null;

  source_label?: string | null;

  apply_url?: string | null;

  budget_label?: string | null;

  budget_period?: string | null;

  is_expired?: boolean;

  expired_at?: string | null;

  expired_reason?: string | null;

  description_excerpt?: string | null;

  created_at?: string | null;

};



export type ExperienceLevel = "any" | "junior" | "mid" | "senior" | "lead";



export type Preferences = {

  id?: number;

  user_id?: string;

  keywords: string[];

  exclude_keywords: string[];

  skills?: string[];

  experience_level?: ExperienceLevel | string | null;

  min_budget: number | null;

  max_budget: number | null;

  min_hourly_rate?: number | null;

  sources: string[];

  match_threshold: number;

  notification_channels: string[];

  digest_mode: boolean;

  freelance_focus?: boolean;

  hide_agency_leads?: boolean;

  location?: string | null;

  timezone?: string | null;

  digest_days?: string[] | null;

  digest_time_local?: string | null;

  max_per_digest?: number;

  notes: string | null;

  alert_email?: string | null;

  slack_webhook_url?: string | null;

  telegram_chat_id?: string | null;

  discord_webhook_url?: string | null;

  whatsapp_to?: string | null;

  custom_webhook_url?: string | null;

};



export type User = {

  id: string;

  email: string;

  full_name?: string | null;

  plan?: string;

  subscription_status?: string;

  is_active?: boolean;

  is_verified?: boolean;

  is_superuser?: boolean;

  account_role?: string;

  profile_visibility?: string;

  is_totp_enabled?: boolean;

  google_id?: string | null;

  github_id?: string | null;

  verification_email_sent?: boolean | null;

  detail?: string | null;

  created?: boolean | null;

};

export type RegisterResponse = {
  detail: string;
  created: boolean;
  verification_email_sent?: boolean;
  auto_verified?: boolean;
  verify_url?: string | null;
  user?: User | null;
};



export type BillingStatus = {

  plan: string;

  subscription_status: string;

  is_pro: boolean;

  stripe_enabled: boolean;

  dev_activate_allowed?: boolean;

  limits: {

    scrape_limit: number;

    max_digest?: number;

    daily_scrape_runs?: number;

    marketplace: boolean;

    channels: string[];

    sources: string[];

  };

  features: string[];

};



export type BillingPlan = {

  id: string;

  price_label: string;

  marketplace: boolean;

  scrape_limit: number;

  max_digest?: number;

  daily_scrape_runs?: number;

  channels: string[];

  features: string[];

};



export function getToken(): string | null {

  if (typeof window === "undefined") return null;

  return localStorage.getItem(TOKEN_KEY);

}



export function setToken(token: string | null) {

  if (typeof window === "undefined") return;

  if (token) localStorage.setItem(TOKEN_KEY, token);

  else localStorage.removeItem(TOKEN_KEY);

  window.dispatchEvent(new Event(TOKEN_CHANGE_EVENT));

}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(REFRESH_KEY, token);
  else localStorage.removeItem(REFRESH_KEY);
}

function storeAuthTokens(payload: {
  access_token?: string;
  refresh_token?: string | null;
}) {
  if (payload.access_token) setToken(payload.access_token);
  if (payload.refresh_token) setRefreshToken(payload.refresh_token);
  else if (payload.refresh_token === null) setRefreshToken(null);
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const refresh = getRefreshToken();
    if (!refresh) return false;
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!response.ok) return false;
      const data = (await response.json()) as {
        access_token?: string;
        refresh_token?: string;
      };
      if (!data.access_token) return false;
      storeAuthTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token ?? null,
      });
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}



export function subscribeAuth(onStoreChange: () => void) {

  if (typeof window === "undefined") return () => {};

  const sync = () => onStoreChange();

  window.addEventListener("storage", sync);

  window.addEventListener("focus", sync);

  window.addEventListener(TOKEN_CHANGE_EVENT, sync);

  return () => {

    window.removeEventListener("storage", sync);

    window.removeEventListener("focus", sync);

    window.removeEventListener(TOKEN_CHANGE_EVENT, sync);

  };

}



export function getAuthSnapshot() {

  return Boolean(getToken());

}



export function getAuthServerSnapshot() {

  return false;

}



function formatApiDetail(detail: unknown): string | null {

  if (typeof detail === "string" && detail.trim()) return detail.trim();

  if (detail && typeof detail === "object" && detail !== null && "message" in detail) {

    const message = (detail as { message: unknown }).message;

    if (typeof message === "string" && message.trim()) return message.trim();

  }

  if (Array.isArray(detail)) {

    const parts = detail

      .map((item) => {

        if (typeof item === "string") return item;

        if (item && typeof item === "object" && "msg" in item) {

          return String((item as { msg: unknown }).msg);

        }

        return null;

      })

      .filter((part): part is string => Boolean(part));

    if (parts.length) return parts.join("; ");

  }

  return null;

}



const DEFAULT_TIMEOUT_MS = 25_000;

export async function request<T>(
  path: string,
  init?: RequestInit & { auth?: boolean; timeoutMs?: number; _retried?: boolean },
): Promise<T> {

  const headers: Record<string, string> = {

    "Content-Type": "application/json",

    ...((init?.headers as Record<string, string>) || {}),

  };

  if (init?.auth) {

    const token = getToken();

    if (!token) {

      throw new Error("Not authenticated");

    }

    headers.Authorization = `Bearer ${token}`;

  }

  const timeoutMs = init?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = init?.signal;
  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  let response: Response;

  try {

    response = await fetch(`${API_BASE}${path}`, {

      ...init,

      headers,

      cache: "no-store",

      signal: controller.signal,

    });

  } catch (err) {

    if (err instanceof Error && err.message === "Not authenticated") throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out. Check your connection and try again.");
    }

    throw new Error("Can't reach the API. Check your connection and try again.");

  } finally {
    clearTimeout(timeoutId);
    if (externalSignal) externalSignal.removeEventListener("abort", onExternalAbort);
  }

  if (response.status === 204 || response.status === 205) {

    return undefined as T;

  }

  if (!response.ok) {

    if (response.status === 401 && init?.auth && !init._retried) {
      const refreshed = await tryRefreshSession();
      if (refreshed) {
        return request<T>(path, { ...init, auth: true, _retried: true });
      }
      setToken(null);
      setRefreshToken(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/auth")) {
        window.location.assign("/auth/session-expired");
      }
      throw new Error("Session expired. Please sign in again.");
    }
    if (response.status === 401 && init?.auth) {
      setToken(null);
      setRefreshToken(null);
      throw new Error("Session expired. Please sign in again.");
    }

    const raw = await response.text();

    try {

      const parsed = JSON.parse(raw) as { detail?: unknown; code?: string; request_id?: string };

      const message = formatApiDetail(parsed.detail);

      if (message) {
        const suffix = parsed.request_id ? ` (ref ${parsed.request_id.slice(0, 8)})` : "";
        throw new Error(`${message}${suffix}`);
      }

    } catch (err) {

      if (err instanceof SyntaxError) {

        // fall through to raw text

      } else if (err instanceof Error) {

        throw err;

      }

    }

    throw new Error(raw || `Request failed: ${response.status}`);

  }

  return response.json() as Promise<T>;

}



export function getApiBase() {

  return API_BASE;

}



export async function listJobs(params?: { search?: string; source?: string; limit?: number }) {

  const query = new URLSearchParams();

  if (params?.search) query.set("search", params.search);

  if (params?.source) query.set("source", params.source);

  query.set("limit", String(params?.limit ?? 50));

  return request<{ total: number; items: Job[] }>(`/jobs?${query.toString()}`);

}



export type ScrapeResult = {

  status: string;

  task_id?: string | null;

  message?: string;

  plan?: string;

  scrape_limit?: number;

  daily_scrape_runs?: number;

  daily_scrape_used?: number;

  daily_scrape_remaining?: number;

  total_fetched: number;

  total_ingested: number;

  total_merged: number;

  total_skipped: number;

  alerts_sent?: number;

  sources: Record<string, unknown>;

};



export async function scrapeJobs(

  sources?: string[],

  limit = 40,

  notify_matches = false,

) {

  return request<ScrapeResult>("/jobs/scrape", {

    method: "POST",

    auth: true,

    body: JSON.stringify({

      ...(sources?.length ? { sources } : {}),

      limit,

      notify_matches,

      background: false,

    }),

  });

}



export type ApplyFormFields = {

  proposal: string;

  bid_amount: number | null;

  currency: string;

  delivery_days: number | null;

  milestone_plan: string | null;

  milestone_percentage?: number | null;

  source_name?: string;

  source_id?: string;

  project_url?: string;

  submit_mode?: string;

  apply_email?: string | null;

  email_subject?: string | null;

};



export type ProposalDraftResponse = {

  job_id: number;

  title: string;

  source_name: string;

  source_url: string;

  apply_email?: string | null;

  email_subject?: string | null;

  provider: string;

  kind?: string | null;

  draft: string;

  initial_draft?: string | null;

  followup_draft?: string | null;

  outreach_links?: {
    gmail?: string | null;
    mailto?: string | null;
    gmail_followup?: string | null;
    mailto_followup?: string | null;
  } | null;

  disclaimer: string;

  form_fields: ApplyFormFields;

};



export async function draftProposal(jobId: number, kind: "initial" | "followup" = "initial") {

  return request<ProposalDraftResponse>(`/jobs/${jobId}/proposal-draft?kind=${kind}`, { method: "POST", auth: true });

}



export async function submitApplication(

  jobId: number,

  formFields: ApplyFormFields,

  confirm: boolean,

) {

  return request<{

    application_id: number;

    job_id: number;

    source_name: string;

    submit_mode: string;

    status: string;

    external_id?: string | null;

    detail?: string | null;

    apply_url?: string | null;

  }>(`/jobs/${jobId}/apply`, {

    method: "POST",

    auth: true,

    body: JSON.stringify({

      confirm,

      form_fields: {

        proposal: formFields.proposal,

        bid_amount: formFields.bid_amount,

        currency: formFields.currency,

        delivery_days: formFields.delivery_days,

        milestone_plan: formFields.milestone_plan,

        milestone_percentage: formFields.milestone_percentage ?? 100,

      },

    }),

  });

}



export async function getDemoMatches(keywords: string) {

  const query = new URLSearchParams({ keywords, limit: "50" });

  return request<{ total: number; keywords: string[]; items: Job[] }>(`/preferences/demo-matches?${query}`);

}



export type LeadApplication = {

  id: number;

  proposal: string;

  bid_amount?: number | null;

  currency?: string | null;

  delivery_days?: number | null;

  milestone_plan?: string | null;

  status: string;

  created_at?: string | null;

};



export type LeadFinding = {

  job_id: number;

  title: string;

  company?: string | null;

  source_name: string;

  source_label?: string | null;

  source_attribution?: string | null;

  url: string;

  apply_url?: string | null;

  apply_email?: string | null;

  description_excerpt?: string | null;

  score: number;

  fit_score?: number;

  score_version?: string;

  why_shown?: string | null;

  eligibility?: string | null;

  explanation?: {
    score_version?: string;
    fit_score?: number;
    components?: Array<{
      name: string;
      weight: number;
      contribution: number;
      evidence?: string | null;
    }>;
    matched_keywords?: string[];
    missing_qualifications?: string[];
    mismatches?: string[];
    reasons?: string[];
    why_shown?: string;
    retrieval_path?: string;
    confidence_band?: string;
    confidence_note?: string;
    calibrated_probability?: null;
    eligibility?: string;
  } | null;

  why: string;

  signals: string[];

  risks: string[];

  action: "draft_bid" | "watch" | "skip";

  matched_keywords: string[];

  freshness_score: number;

  client_quality_score: number;

  red_flags: string[];

  posted_at?: string | null;

  budget_label?: string | null;

  budget_period?: string | null;

  freelance_fit?: number;

  freelance_benefits?: string[];

  freelance_benefits_line?: string | null;

  employment_risks?: string[];

  client_signal?: {
    poster_type?: string;
    poster_label?: string;
    poster_badge?: string;
    urgency?: string;
    urgency_label?: string | null;
    is_agency?: boolean;
    score?: number;
    reasons?: string[];
  } | null;

  smart_match?: {
    is_boosted: boolean;
    is_penalized: boolean;
    reason?: string | null;
  } | null;

  user_status?: "save" | "skip" | "pitched" | "won" | null;

  application?: LeadApplication | null;

  trust?: {
    risk_indicators?: Array<{
      code: string;
      label: string;
      severity: string;
      observation: string;
      why_it_matters: string;
      what_to_verify: string;
      is_verdict?: boolean;
      abstain?: boolean;
      disclaimer?: string;
    }>;
    risk_high_count?: number;
    requires_human_review?: boolean;
    verdict?: null;
    disclaimer?: string;
    extraction?: {
      work_type?: string;
      ambiguous_or_missing?: string[];
      required_skills?: string[];
      budget_structure?: string | null;
      provider?: string;
      extraction_version?: string;
    };
    employer?: {
      company_name?: string | null;
      company_identity_status?: string;
      domain?: string | null;
      public_hiring_page?: string | null;
    };
    due_diligence?: Array<{
      id: string;
      title: string;
      why_it_matters: string;
      what_to_verify: string;
      severity: string;
      is_verdict?: boolean;
    }>;
    evidence?: {
      count?: number;
      by_semantics?: Record<string, number>;
      note?: string;
    };
    policy?: Record<string, boolean | string>;
  } | null;

};



export type LeadFindingsResponse = {

  generated_at: string;

  total_scanned: number;

  total_indexed?: number;

  total_matched: number;

  total_findings: number;

  skipped_count?: number;

  freelance_focus?: boolean;

  action_counts: {

    draft_bid: number;

    watch: number;

    skip: number;

  };

  keywords: string[];

  score_version?: string;

  learning_enabled?: boolean;

  subscription_affects_organic_rank?: boolean;

  candidate_stage?: string;

  retrieval_mode?: string;

  cache_hit?: boolean;

  ineligible_samples?: Array<{
    job_id?: number;
    eligibility?: string;
    hard_filters_failed?: string[];
    evidence?: string[];
    title?: string;
    source_name?: string;
  }>;

  items: LeadFinding[];

};



export async function getDemoFindings(keywords: string, limit = 10, freelanceFocus = true) {

  const query = new URLSearchParams({

    keywords,

    limit: String(limit),

    freelance_focus: String(freelanceFocus),

  });

  return request<LeadFindingsResponse>(`/preferences/demo-findings?${query}`);

}



export async function getAuthFindings(
  limit = 10,
  freelanceFocus?: boolean,
  includeSkipped = false,
) {
  const query = new URLSearchParams({
    limit: String(limit),
  });
  if (freelanceFocus !== undefined) {
    query.set("freelance_focus", String(freelanceFocus));
  }
  if (includeSkipped) {
    query.set("include_skipped", "true");
  }
  return request<LeadFindingsResponse>(`/preferences/findings?${query}`, { auth: true });
}



export async function setLeadAction(
  jobId: number,
  status: "save" | "skip" | "pitched" | "won" | "clear",
  opts?: { reason?: string; feedback_kind?: string },
) {

  return request<{
    job_id: number;
    status: "save" | "skip" | "pitched" | "won" | null;
    reason?: string | null;
    feedback_kind?: string | null;
  }>(

    `/preferences/leads/${jobId}/action`,

    {

      method: "PUT",

      auth: true,

      body: JSON.stringify({
        status,
        reason: opts?.reason,
        feedback_kind: opts?.feedback_kind,
      }),

    },

  );

}

export type PipelineStats = {
  saved_count: number;
  pitched_count: number;
  won_count: number;
  skipped_count: number;
  total_engaged: number;
  pitch_rate: number;
  win_rate: number;
  saved_value: number;
  pitched_value: number;
  won_value: number;
  active_pipeline_value: number;
};

export async function getPipelineStats() {
  return request<PipelineStats>("/preferences/pipeline-stats", { auth: true });
}

export type SeoSkillCategory = {
  slug: string;
  label: string;
  headline: string;
  description: string;
  job_count: number;
};

export type SeoJobTeaser = {
  id: number;
  title: string;
  company_masked: string;
  location: string;
  source_name: string;
  source_attribution: string;
  tags: string[];
  budget_label?: string | null;
  posted_at?: string | null;
  description_excerpt: string;
};

export type SeoDirectoryIndexResponse = {
  total_active: number;
  categories: SeoSkillCategory[];
  recent: SeoJobTeaser[];
};

export type SeoSkillDirectoryResponse = {
  slug: string;
  label: string;
  headline: string;
  description: string;
  total_matched: number;
  items: SeoJobTeaser[];
  related_skills: { slug: string; label: string }[];
};

export async function getSeoDirectory() {
  return request<SeoDirectoryIndexResponse>("/jobs/directory");
}

export async function getSeoSkillDirectory(skillSlug: string, limit = 24) {
  return request<SeoSkillDirectoryResponse>(
    `/jobs/directory/${encodeURIComponent(skillSlug)}?limit=${limit}`,
  );
}



export async function sendNotification(payload: {

  title: string;

  body: string;

  channels: string[];

  priority: string;

  digest?: boolean;

}) {

  return request<Record<string, unknown>>("/notifications/send", {

    method: "POST",

    auth: true,

    body: JSON.stringify(payload),

  });

}



export async function getNotificationHistory() {
  return request<{ items: Array<Record<string, unknown>> }>("/notifications/history", { auth: true });
}

export async function getInbox(params?: {
  unread_only?: boolean;
  event_type?: string;
  group_key?: string;
}) {
  const q = new URLSearchParams();
  if (params?.unread_only) q.set("unread_only", "true");
  if (params?.event_type) q.set("event_type", params.event_type);
  if (params?.group_key) q.set("group_key", params.group_key);
  const qs = q.toString() ? `?${q.toString()}` : "";
  return request<{
    items: Array<Record<string, unknown>>;
    unread_count: number;
    offset: number;
    limit: number;
  }>(`/notifications/inbox${qs}`, { auth: true });
}

export async function markNotificationRead(id: number) {
  return request<{ id: number; is_read: boolean; read_at: string }>(
    `/notifications/inbox/${id}/read`,
    { method: "POST", auth: true },
  );
}

export async function markAllNotificationsRead() {
  return request<{ marked_read: number; read_at: string }>(
    "/notifications/inbox/read-all",
    { method: "POST", auth: true },
  );
}

export async function archiveNotification(id: number) {
  return request<{ id: number; archived: boolean }>(
    `/notifications/inbox/${id}`,
    { method: "DELETE", auth: true },
  );
}

export async function getUnreadNotificationCount() {
  return request<{ unread_count: number }>(
    "/notifications/inbox/unread-count",
    { auth: true },
  );
}

export async function previewDigest() {
  return request<{
    title: string;
    leads: Array<Record<string, unknown>>;
    count: number;
    text_body: string;
    html_preview: string;
    generated_at: string;
    local_date: string;
    schedule: Record<string, unknown>;
  }>("/notifications/digest/preview", { auth: true });
}

export async function sendTestDigest() {
  return request<{
    status: string;
    recipient: string;
    lead_count: number;
    delivered_count: number;
    sent_at: string;
  }>("/notifications/digest/test", { method: "POST", auth: true });
}

export async function getTimezonePreview() {
  return request<Record<string, unknown>>("/notifications/timezone-preview", {
    auth: true,
  });
}

export async function getProviderStatus() {
  return request<Record<string, unknown>>("/notifications/providers/status", {
    auth: true,
  });
}

export async function getProviderCapabilities() {
  return request<Record<string, unknown>>(
    "/notifications/providers/capabilities",
    { auth: true },
  );
}

export async function pauseNotifications() {
  return request<Preferences>("/preferences/pause", {
    method: "POST",
    auth: true,
  });
}

export async function resumeNotifications() {
  return request<Preferences>("/preferences/resume", {
    method: "POST",
    auth: true,
  });
}

export async function unsubscribeNotifications() {
  return request<Preferences>("/preferences/unsubscribe", {
    method: "POST",
    auth: true,
  });
}



export async function healthLive() {

  return request<{ status: string }>("/health/live");

}



export type IntegrationsStatus = {

  public_sources: string[];

  marketplace_sources: string[];

  discovery_sources?: string[];

  commercial_free_sources?: string[];

  commercial_pro_sources?: string[];

  restricted_sources?: string[];

  registered: string[];

  notes?: {

    restricted?: string;

    discovery?: string;

    attribution?: string;

  };

  upwork: {

    configured: boolean;

    client_id_set: boolean;

    authorize_path: string;

    search_query: string;

  };

  freelancer: {

    configured: boolean;

    search_query: string;

  };

  peopleperhour: {

    configured: boolean;

    provider: string;

    search_query: string;

  };

  guru: {

    configured: boolean;

    provider: string;

    search_query: string;

  };

  serpapi?: {

    configured: boolean;

    freelance_query: string;

    jobs_query: string;

    companies_query?: string;

    company_sites?: string[];

    company_site_batches?: string[];

    maps_query?: string;

    maps_ll?: string;

    sources: string[];

    primary?: string | null;

    fallback?: string | null;

    tavily_configured?: boolean;

    serpapi_configured?: boolean;

    ready?: boolean;

  };

  tavily?: {

    configured: boolean;

    search_depth: string;

    role: string;

    fallback: string;

  };

  unsupported: {

    fiverr: string;

    contra: string;

  };

};



export async function getIntegrationsStatus() {

  return request<IntegrationsStatus>("/integrations/status");

}



export async function register(email: string, password: string, full_name?: string) {
  return request<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name }),
  });
}



function friendlyAuthError(status: number, detail: string): string {

  const normalized = detail.trim();

  if (normalized === "TOTP_REQUIRED") return normalized;

  if (status === 401 || /invalid credentials/i.test(normalized)) {

    return "Invalid email or password.";

  }

  if (status >= 500 || /internal server error/i.test(normalized)) {

    return "Sign-in is temporarily unavailable. Try again in a moment.";

  }

  return normalized || `Sign-in failed (${status}).`;

}



export async function login(email: string, password: string, totp_code?: string) {

  const body = new URLSearchParams({ username: email, password });

  if (totp_code) {

    body.append("totp_code", totp_code);

  }

  let response: Response;

  try {

    response = await fetch(`${API_BASE}/auth/login`, {

      method: "POST",

      headers: { "Content-Type": "application/x-www-form-urlencoded" },

      credentials: "include",

      body,

    });

  } catch {

    throw new Error("Can't reach the API. Check that the backend is running.");

  }

  if (!response.ok) {

    let detail = await response.text();

    try {

      const parsed = JSON.parse(detail);

      if (parsed.detail) detail = String(parsed.detail);

    } catch {

      // keep raw text

    }

    throw new Error(friendlyAuthError(response.status, detail));

  }

  const data = (await response.json()) as {
    access_token: string;
    refresh_token?: string;
  };

  storeAuthTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token ?? null,
  });

  return data;

}



export async function getGoogleAuthUrl(redirect_uri?: string): Promise<{ url: string; state: string }> {

  const query = redirect_uri ? `?redirect_uri=${encodeURIComponent(redirect_uri)}` : "";

  return request<{ url: string; state: string }>(`/auth/google/url${query}`);

}



export async function loginWithGoogle(payload: {

  code?: string;

  state?: string;

  redirect_uri?: string;

  id_token?: string;

  totp_code?: string;

}): Promise<{ access_token: string }> {

  let response: Response;

  try {

    response = await fetch(`${API_BASE}/auth/google`, {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      credentials: "include",

      body: JSON.stringify(payload),

    });

  } catch {

    throw new Error("Can't reach the API. Check that the backend is running.");

  }



  if (!response.ok) {

    let detail = await response.text();

    try {

      const parsed = JSON.parse(detail);

      if (parsed.detail) detail = String(parsed.detail);

    } catch {

      // keep raw text

    }

    throw new Error(friendlyAuthError(response.status, detail));

  }



  const data = (await response.json()) as {
    access_token: string;
    refresh_token?: string;
  };

  storeAuthTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token ?? null,
  });

  return data;

}



export async function getGitHubAuthUrl(redirect_uri?: string): Promise<{ url: string; state: string }> {

  const query = redirect_uri ? `?redirect_uri=${encodeURIComponent(redirect_uri)}` : "";

  return request<{ url: string; state: string }>(`/auth/github/url${query}`);

}



export async function loginWithGitHub(payload: {

  code: string;

  state?: string;

  redirect_uri?: string;

  totp_code?: string;

}): Promise<{ access_token: string }> {

  let response: Response;

  try {

    response = await fetch(`${API_BASE}/auth/github`, {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      credentials: "include",

      body: JSON.stringify(payload),

    });

  } catch {

    throw new Error("Can't reach the API. Check that the backend is running.");

  }



  if (!response.ok) {

    let detail = await response.text();

    try {

      const parsed = JSON.parse(detail);

      if (parsed.detail) detail = String(parsed.detail);

    } catch {

      // keep raw text

    }

    throw new Error(friendlyAuthError(response.status, detail));

  }



  const data = (await response.json()) as {
    access_token: string;
    refresh_token?: string;
  };

  storeAuthTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token ?? null,
  });

  return data;

}



export async function me() {

  return request<User>("/users/me", { auth: true });

}



export async function updateProfile(fullName: string) {

  return request<User>("/users/me", {

    method: "PATCH",

    body: JSON.stringify({ full_name: fullName }),

    auth: true,

  });

}



export async function getPreferences() {

  return request<Preferences>("/preferences/me", { auth: true });

}



export async function updatePreferences(payload: Preferences) {

  return request<Preferences>("/preferences/me", {

    method: "PUT",

    auth: true,

    body: JSON.stringify(payload),

  });

}



export async function getAuthMatches() {
  const findings = await getAuthFindings(25);
  const items: Job[] = (findings.items || []).map((item) => ({
    id: item.job_id,
    source_name: item.source_name,
    source_id: String(item.job_id),
    title: item.title,
    description: item.description_excerpt || "",
    url: item.apply_url || item.url,
    company: item.company ?? null,
    posted_at: item.posted_at ?? null,
    match_score: item.score,
    matched_keywords: item.matched_keywords || [],
    match_reasons: item.signals || [],
  }));
  return { total: items.length, items };
}



export async function getBilling() {

  return request<BillingStatus>("/billing/me", { auth: true });

}



export async function listBillingPlans() {

  return request<{

    stripe_enabled: boolean;

    dev_activate_allowed?: boolean;

    plans: BillingPlan[];

  }>("/billing/plans");

}



export async function startCheckout() {

  return request<{ url: string; mode: string }>("/billing/checkout", { method: "POST", auth: true });

}



export async function openBillingPortal() {

  return request<{ url: string; mode: string }>("/billing/portal", { method: "POST", auth: true });

}



export async function activateDevPro() {
  return request<BillingStatus>("/billing/dev-activate-pro", { method: "POST", auth: true });
}

export type UserUsageStatus = {
  user_id: string;
  plan: string;
  subscription_status: string;
  features: Record<
    string,
    {
      units_used: number;
      units_pending: number;
      units_remaining: number;
      limit: number;
      pct_used: number;
      period_key: string;
      reset_at: string;
    }
  >;
};

export async function getBillingUsage() {
  return request<UserUsageStatus>("/billing/usage", { auth: true });
}

export async function getUnitEconomics() {
  return request<{
    pricing_hypothesis: string;
    scenarios: Array<{
      name: string;
      description: string;
      monthly_price: number;
      monthly_hunts: number;
      monthly_copilot_runs: number;
      avg_tokens_per_run: number;
      monthly_digests: number;
      search_api_cost: number;
      llm_tokens_cost: number;
      notification_cost: number;
      infra_cost: number;
      support_cost: number;
      payment_processor_fee: number;
      total_cogs: number;
      gross_profit: number;
      gross_margin_pct: number;
      breakeven_price: number;
    }>;
    measured_telemetry: {
      period: string;
      user_id: string;
      total_measured_cost_usd: number;
      measured_features: Record<string, { units_used: number; measured_cost_usd: number }>;
      operator_hard_cap_usd: number;
    };
  }>("/billing/unit-economics");
}

export async function getProviderEligibility() {
  return request<{
    environment: string;
    stripe_configured: boolean;
    sandbox_mode: boolean;
    card_storage_policy: string;
    checklist: Array<{
      area: string;
      requirement: string;
      status: string;
      details: string;
      official_source: string;
    }>;
    readiness_summary: string;
  }>("/billing/provider-eligibility");
}



export async function logout() {
  try {
    if (getToken()) {
      await request("/auth/logout", {
        method: "POST",
        auth: true,
        credentials: "include",
      } as RequestInit & { auth?: boolean });
    }
  } catch {
    // Always clear local session even if revoke fails (offline / expired).
  }
  setToken(null);
  setRefreshToken(null);
}

export async function exportMyData() {
  return request<Record<string, unknown>>("/users/me/export", { auth: true });
}

export async function getProfileCompleteness() {
  return request<{ score: number; checks: Record<string, boolean> }>(
    "/users/me/profile-completeness",
    { auth: true },
  );
}

export async function upsertConsent(purpose: string, granted: boolean) {
  return request<{ purpose: string; granted: boolean }>("/users/me/consents", {
    method: "PUT",
    auth: true,
    body: JSON.stringify({ purpose, granted, source: "privacy_center" }),
  });
}

export async function listConsents() {
  return request<{ items: Array<{ purpose: string; granted: boolean }> }>(
    "/users/me/consents",
    { auth: true },
  );
}

export async function listMyAudit() {
  return request<{ items: Array<{ action: string; created_at?: string; meta?: unknown }> }>(
    "/users/me/audit",
    { auth: true },
  );
}



export async function setup2fa() {

  return request<{ secret: string; provisioning_uri: string }>("/auth/2fa/setup", { method: "POST", auth: true });

}



export async function enable2fa(code: string) {

  return request<{ detail: string }>("/auth/2fa/enable", { method: "POST", auth: true, body: JSON.stringify({ code }) });

}



export async function disable2fa(code: string) {

  return request<{ detail: string }>("/auth/2fa/disable", { method: "POST", auth: true, body: JSON.stringify({ code }) });

}



export async function forgotPassword(email: string) {

  return request<{ detail: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });

}



export async function resetPassword(token: string, new_password: string) {

  return request<{ detail: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) });

}



export async function verifyEmail(token: string) {

  return request<{ detail: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) });

}



export async function resendVerification(email: string) {

  return request<{

    detail: string;

    email_delivered?: boolean | null;

    auto_verified?: boolean;

    verify_url?: string;

  }>("/auth/resend-verification", {
    method: "POST",
    auth: Boolean(getToken()),
    body: JSON.stringify({ email }),
  });

}



export async function devVerifyEmail() {

  return request<{ detail: string; is_verified: boolean }>("/auth/dev-verify", {

    method: "POST",

    auth: true,

  });

}



export async function adminListUsers(skip = 0, limit = 100) {

  return request<User[]>(`/admin/users?skip=${skip}&limit=${limit}`, { auth: true });

}



export async function adminUpdateUser(

  userId: string,

  data: { is_active?: boolean; is_superuser?: boolean; is_verified?: boolean; plan?: string },

) {

  return request<User>(`/admin/users/${userId}`, { method: "PATCH", auth: true, body: JSON.stringify(data) });

}



export type RoadmapItem = {

  key: string;

  title: string;

  description: string;

  status: string;

  votes: number;

  voted: boolean;

};



export async function listRoadmap(voterId?: string) {

  const query = voterId ? `?voter_id=${encodeURIComponent(voterId)}` : "";

  return request<RoadmapItem[]>(`/roadmap${query}`);

}



export async function voteRoadmap(featureKey: string, voterId: string) {

  return request<RoadmapItem>("/roadmap/votes", {

    method: "POST",

    body: JSON.stringify({ feature_key: featureKey, voter_id: voterId }),

  });

}



export async function submitCancellationFeedback(payload: { reason: string; details?: string; email?: string }) {

  return request<{ detail: string }>("/feedback/cancellation", {

    method: "POST",

    body: JSON.stringify(payload),

  });

}



export async function reportJobExpired(jobId: number, reason: string = "dead_link") {

  return request<{ status: string; job_id: number; is_expired: boolean; expired_reason?: string | null }>(

    `/jobs/${jobId}/report-expired`,

    {

      method: "POST",

      auth: true,

      body: JSON.stringify({ reason }),

    }

  );

}



export type AdminSystemTelemetry = {
  total_jobs: number;
  active_jobs: number;
  expired_jobs: number;
  jobs_by_source: Record<string, number>;
  total_users: number;
  pro_users: number;
};

export async function adminGetSystemTelemetry() {
  return request<AdminSystemTelemetry>("/admin/telemetry/system", { auth: true });
}

export async function adminTriggerStaleSweep() {
  return request<{ status: string; expired_count: number }>("/admin/trigger-sweep", {
    method: "POST",
    auth: true,
  });
}

export type AdminSourcePolicy = {
  key: string;
  display_name: string;
  category: string;
  permission: string;
  enabled_by_default: boolean;
  attribution: string;
  rate_limit_per_hour: number | null;
  daily_budget_usd: number | null;
  ttl_days: number;
  health: string;
  operator_disabled: boolean;
  notes: string;
  circuit_open?: boolean;
};

export async function adminListSources() {
  return request<{
    sources: AdminSourcePolicy[];
    audit: Record<string, unknown>;
    spend_today_usd: Record<string, number>;
    quarantine_open: number;
  }>("/admin/sources", { auth: true });
}

export async function adminSourceHealth() {
  return request<{
    sources: AdminSourcePolicy[];
    spend_today_usd: Record<string, number>;
  }>("/admin/sources/health", { auth: true });
}

export async function adminSourceQuarantine(limit = 50) {
  return request<{ items: Array<Record<string, unknown>>; total: number }>(
    `/admin/sources/quarantine?limit=${limit}`,
    { auth: true },
  );
}

export async function adminDisableSource(sourceKey: string, disabled: boolean) {
  return request<{ status: string; source: string; operator_disabled: boolean }>(
    `/admin/sources/${encodeURIComponent(sourceKey)}/disable`,
    {
      method: "POST",
      auth: true,
      body: JSON.stringify({ disabled }),
    },
  );
}

export async function adminInventoryQuality() {
  return request<{
    quality: Record<string, number>;
    coverage: Record<string, { count: number; attribution: string }>;
    sample_size: number;
  }>("/admin/inventory/quality", { auth: true });
}

export async function adminHuntRunStatus() {
  return request<{
    audit: Record<string, unknown>;
    enabled_sources: string[];
    spend_today_usd: Record<string, number>;
    quarantine: Array<Record<string, unknown>>;
    note: string;
  }>("/admin/hunt-runs/status", { auth: true });
}

export async function getJobTrust(jobId: number, includeEvidence = true) {
  return request<Record<string, unknown>>(
    `/trust/jobs/${jobId}?include_evidence=${includeEvidence ? "true" : "false"}`,
    { auth: true },
  );
}

export async function reportListingTrust(
  jobId: number,
  body: {
    reason_code: string;
    details?: string;
    correction_requested?: boolean;
  },
) {
  return request<{ ok: boolean; report?: Record<string, unknown>; message?: string }>(
    `/trust/jobs/${jobId}/report`,
    { method: "POST", auth: true, body: JSON.stringify(body) },
  );
}

export async function adminModerationQueue(status = "open", limit = 50) {
  return request<{ items: Array<Record<string, unknown>>; total: number }>(
    `/trust/moderation/queue?status=${encodeURIComponent(status)}&limit=${limit}`,
    { auth: true },
  );
}

export async function adminReviewListingReport(
  reportId: number,
  body: { outcome: string; notes?: string; status?: string },
) {
  return request<{ ok: boolean; report?: Record<string, unknown> }>(
    `/trust/moderation/reports/${reportId}/review`,
    { method: "POST", auth: true, body: JSON.stringify(body) },
  );
}

export type LearnedAffinitiesResponse = {
  total_actions: number;
  saved_count: number;
  pitched_count: number;
  skipped_count: number;
  learning_active: boolean;
  learning_consent?: boolean;
  consent_purpose?: string;
  can_reset?: boolean;
  positive_skills: Array<{
    skill: string;
    weight: number;
    saved_count: number;
    pitched_count: number;
  }>;
  negative_skills: Array<{
    skill: string;
    weight: number;
    skipped_count: number;
  }>;
  summary: string;
};

export type MatchProfileResponse = {
  user_id?: string | null;
  skills: string[];
  keywords: string[];
  exclude_keywords: string[];
  experience_level: string;
  cold_start: boolean;
  learning_enabled: boolean;
  score_version: string;
  retrieval_mode: string;
  hard: Array<{ key: string; value: unknown; kind: string; source: string; evidence?: string | null }>;
  soft: Array<{ key: string; value: unknown; kind: string; source: string; evidence?: string | null }>;
  unknowns: Array<{ key: string; value: unknown; kind: string; source: string; evidence?: string | null }>;
  sensitive_traits_inferred: boolean;
};

export async function getLearnedAffinities() {
  return request<LearnedAffinitiesResponse>("/preferences/learned-affinities", { auth: true });
}

export async function resetLearnedAffinities() {
  return request<{ reset: boolean; deleted_actions: number; summary: string }>(
    "/preferences/learned-affinities/reset",
    { method: "POST", auth: true },
  );
}

export async function getMatchProfile() {
  return request<MatchProfileResponse>("/preferences/match-profile", { auth: true });
}

export async function getRecommendationMeta() {
  return request<{
    score_version: string;
    retrieval_mode: string;
    semantic_enabled: boolean;
    learning_enabled: boolean;
    subscription_affects_organic_rank: boolean;
    cache_key: string;
    consent_purpose: string;
  }>("/preferences/recommendation-meta", { auth: true });
}

export async function postMatchFeedback(body: {
  job_id: number;
  kind: "save" | "skip" | "hide_source" | "apply_click" | "outcome" | "clear";
  reason?: string;
  outcome?: "interview" | "contract" | "rejected" | "none";
}) {
  return request<{
    job_id: number;
    status: string | null;
    feedback_kind?: string;
    counts_as_success?: boolean;
  }>("/preferences/match-feedback", {
    method: "POST",
    auth: true,
    body: JSON.stringify(body),
  });
}

export async function testWebhook(webhookUrl?: string) {
  return request<{ success: boolean; message?: string; error?: string; status_code?: string }>(
    "/preferences/test-webhook",
    {
      method: "POST",
      auth: true,
      body: JSON.stringify({ webhook_url: webhookUrl }),
    }
  );
}

/* ── Phase 08: Pipeline CRM + Copilot ─────────────────────────────── */

export type PipelineStage =
  | "discovered"
  | "saved"
  | "researching"
  | "ready"
  | "applied"
  | "interview"
  | "negotiating"
  | "won"
  | "lost"
  | "archived";

export type PipelineLead = {
  id: number;
  job_id: number;
  status: string;
  pipeline_stage: PipelineStage;
  follow_up_at?: string | null;
  apply_clicked_at?: string | null;
  applied_confirmed_at?: string | null;
  tags?: string[];
  employer_name?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  won_value?: number | null;
  lost_reason?: string | null;
  time_spent_seconds?: number;
  job?: {
    id: number;
    title: string;
    company?: string | null;
    source_name?: string;
    url?: string;
    budget_min?: number | null;
    budget_max?: number | null;
    location?: string | null;
  };
};

export type WorkspaceDashboard = {
  demo: boolean;
  follow_ups_due: number;
  qualified_leads: number;
  active_opportunities: number;
  stage_counts: Record<string, number>;
  stage_conversion: {
    saved_to_applied: number;
    applied_to_interview: number;
    interview_to_won: number;
  };
  time_spent_seconds: number;
  won_revenue: number;
  notes?: string | null;
};

export type CopilotIntent =
  | "lead_brief"
  | "requirements_gap"
  | "portfolio_selection"
  | "proposal_draft"
  | "interview_prep"
  | "scope_clarification"
  | "negotiation_scenario";

export type CopilotDraft = {
  id: number;
  job_id: number;
  intent: string;
  version: number;
  title?: string | null;
  body: string;
  evidence?: Array<{ claim: string; source: string }> | null;
  unverified_claims?: string[] | null;
  provider?: string | null;
  model?: string | null;
  sent_at?: string | null;
  never_auto_sends?: boolean;
};

export type AgentRunResult = {
  id: string;
  intent: string;
  state: string;
  job_id?: number | null;
  output?: {
    title?: string;
    body?: string;
    evidence?: unknown;
    unverified_claims?: string[];
    listing_url?: string;
    duration_ms?: number;
    auto_sent?: boolean;
    fallback?: boolean;
  } | null;
  error?: string | null;
  tokens_used?: number;
  cost_usd?: number;
  tool_calls?: Array<{ tool_name: string; ok: boolean }>;
  draft?: CopilotDraft;
  never_auto_sends?: boolean;
  audit_receipt?: Record<string, unknown>;
};

export async function getPipelineLeads(opts?: {
  stage?: string;
  q?: string;
  tag?: string;
  follow_up_due?: boolean;
  include_archived?: boolean;
}) {
  const query = new URLSearchParams();
  if (opts?.stage) query.set("stage", opts.stage);
  if (opts?.q) query.set("q", opts.q);
  if (opts?.tag) query.set("tag", opts.tag);
  if (opts?.follow_up_due) query.set("follow_up_due", "true");
  if (opts?.include_archived) query.set("include_archived", "true");
  return request<{ items: PipelineLead[]; count: number; stages: PipelineStage[] }>(
    `/pipeline/leads?${query}`,
    { auth: true },
  );
}

export async function getPipelineBoard() {
  return request<{
    columns: Record<string, PipelineLead[]>;
    stages: PipelineStage[];
  }>("/pipeline/board", { auth: true });
}

export async function getWorkspaceDashboard(demo = false) {
  return request<WorkspaceDashboard>(
    `/pipeline/dashboard${demo ? "?demo=true" : ""}`,
    { auth: true },
  );
}

export async function setPipelineStage(
  jobId: number,
  stage: PipelineStage,
  opts?: {
    reason?: string;
    lost_reason?: string;
    won_value?: number;
    confirm_applied?: boolean;
  },
) {
  return request<{ lead: PipelineLead }>(`/pipeline/leads/${jobId}/stage`, {
    method: "PUT",
    auth: true,
    body: JSON.stringify({
      stage,
      reason: opts?.reason,
      lost_reason: opts?.lost_reason,
      won_value: opts?.won_value,
      confirm_applied: opts?.confirm_applied ?? false,
    }),
  });
}

export async function updatePipelineLead(
  jobId: number,
  fields: Partial<{
    follow_up_at: string | null;
    tags: string[];
    employer_name: string | null;
    contact_name: string | null;
    contact_email: string | null;
    contact_url: string | null;
    contact_notes: string | null;
    won_value: number | null;
    lost_reason: string | null;
  }>,
) {
  return request<{ lead: PipelineLead }>(`/pipeline/leads/${jobId}`, {
    method: "PATCH",
    auth: true,
    body: JSON.stringify(fields),
  });
}

export async function addLeadNote(
  jobId: number,
  body: string,
  kind: "note" | "negotiation" | "research" = "note",
) {
  return request<{ note: { id: number; body: string; kind: string } }>(
    `/pipeline/leads/${jobId}/notes`,
    { method: "POST", auth: true, body: JSON.stringify({ body, kind }) },
  );
}

export async function listLeadNotes(jobId: number) {
  return request<{ notes: Array<{ id: number; body: string; kind: string; created_at?: string }> }>(
    `/pipeline/leads/${jobId}/notes`,
    { auth: true },
  );
}

export async function addLeadReminder(
  jobId: number,
  remindAt: string,
  message?: string,
) {
  return request<{ reminder: { id: number; remind_at: string } }>(
    `/pipeline/leads/${jobId}/reminders`,
    {
      method: "POST",
      auth: true,
      body: JSON.stringify({ remind_at: remindAt, message, kind: "follow_up" }),
    },
  );
}

export async function bulkSetPipelineStage(jobIds: number[], stage: PipelineStage) {
  return request<{ updated: Array<{ job_id: number }>; undo_id: string }>(
    "/pipeline/leads/bulk-stage",
    {
      method: "POST",
      auth: true,
      body: JSON.stringify({ job_ids: jobIds, stage }),
    },
  );
}

export async function undoPipelineAction(undoId: string) {
  return request<{ restored: unknown[] }>(`/pipeline/undo/${undoId}`, {
    method: "POST",
    auth: true,
  });
}

export async function startCopilotRun(
  jobId: number,
  intent: CopilotIntent,
  opts?: { idempotency_key?: string },
) {
  return request<AgentRunResult>("/copilot/runs", {
    method: "POST",
    auth: true,
    body: JSON.stringify({
      job_id: jobId,
      intent,
      idempotency_key: opts?.idempotency_key,
      confirm_side_effect: false,
    }),
  });
}

export async function getCopilotRun(runId: string) {
  return request<AgentRunResult>(`/copilot/runs/${runId}`, { auth: true });
}

export async function cancelCopilotRun(runId: string) {
  return request<AgentRunResult>(`/copilot/runs/${runId}/cancel`, {
    method: "POST",
    auth: true,
  });
}

export async function retryCopilotRun(runId: string) {
  return request<AgentRunResult>(`/copilot/runs/${runId}/retry`, {
    method: "POST",
    auth: true,
  });
}

export async function updateCopilotDraft(
  draftId: number,
  body: string,
  title?: string,
) {
  return request<{ draft: CopilotDraft }>(`/copilot/drafts/${draftId}`, {
    method: "PATCH",
    auth: true,
    body: JSON.stringify({ body, title }),
  });
}

export async function listCopilotDrafts(jobId?: number) {
  const q = jobId != null ? `?job_id=${jobId}` : "";
  return request<{ drafts: CopilotDraft[]; never_auto_sends: boolean }>(
    `/copilot/drafts${q}`,
    { auth: true },
  );
}

// ---------------------------------------------------------------------------
// Financial Intelligence & Earnings Calculator (Phase 10)
// ---------------------------------------------------------------------------

export type GrossToNetPayload = {
  gross_amount: number;
  currency?: string;
  target_currency?: string;
  template_id?: string;
  contract_service_fee_pct?: number;
  contract_service_fee_fixed?: number;
  fee_tax_pct?: number;
  withholding_tax_pct?: number;
  withholding_tax_base?: "gross" | "fee";
  withdrawal_fee?: number;
  withdrawal_count?: number;
  processor_fee_pct?: number;
  processor_fee_fixed?: number;
  other_expenses?: number;
  benchmark_fx_rate?: number;
  actual_fx_rate?: number;
  reported_bank_quote?: number;
};

export type NetToGrossPayload = {
  target_net_amount: number;
  currency?: string;
  target_currency?: string;
  hourly_hours?: number;
  contract_service_fee_pct?: number;
  contract_service_fee_fixed?: number;
  fee_tax_pct?: number;
  withholding_tax_pct?: number;
  withholding_tax_base?: "gross" | "fee";
  withdrawal_fee?: number;
  withdrawal_count?: number;
  processor_fee_pct?: number;
  processor_fee_fixed?: number;
  other_expenses?: number;
  actual_fx_rate?: number;
};

export type CalculationBreakdownResponse = {
  disclaimer: string;
  calculation: {
    gross_amount: number;
    currency: string;
    target_currency: string;
    contract_service_fee: number;
    fee_tax: number;
    withholding_tax: number;
    withdrawal_fee_total: number;
    processor_fee_total: number;
    other_expenses: number;
    total_deductions_base: number;
    permanent_costs: number;
    recoverable_credits: number;
    net_payout_amount: number;
    bank_deposit_amount: number;
    benchmark_bank_deposit?: number;
    fx_spread_cost_total?: number;
    reported_bank_quote?: number;
    reconciliation_discrepancy?: number;
    reconciliation_status: string;
    effective_take_home_rate_pct: number;
    effective_total_cost_pct: number;
    itemized_deductions: Array<{
      name: string;
      code: string;
      amount_base: number;
      amount_target: number;
      pct_of_gross: number;
      category: "permanent_cost" | "recoverable_credit" | "payout";
      notes: string;
    }>;
  };
  fx_metadata?: {
    from_currency: string;
    to_currency: string;
    benchmark_rate: number;
    offered_rate: number;
    spread_pct: number;
    spread_cost_per_unit: number;
    rate_type: string;
    provider: string;
    is_outage: boolean;
    is_stale: boolean;
    timestamp: string;
  };
};

export type InverseQuoteResponse = {
  disclaimer: string;
  quote: {
    target_net_amount: number;
    required_gross_amount: number;
    currency: string;
    target_currency: string;
    hourly_hours?: number;
    suggested_hourly_rate?: number;
    verification_net_deposit: number;
    rounding_discrepancy: number;
    meets_target: boolean;
    deduction_breakdown: {
      contract_service_fee: number;
      fee_tax: number;
      withholding_tax: number;
      withdrawal_fee_total: number;
      processor_fee_total: number;
      other_expenses: number;
      total_deductions_base: number;
    };
  };
};

export async function calculateGrossToNet(payload: GrossToNetPayload) {
  return request<CalculationBreakdownResponse>("/finance/calculate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function calculateNetToGross(payload: NetToGrossPayload) {
  return request<InverseQuoteResponse>("/finance/calculate/inverse", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listFeeTemplates() {
  return request<{
    disclaimer: string;
    templates: Array<{
      id: string;
      template_name: string;
      platform: string;
      region: string;
      currency: string;
      contract_service_fee_pct: number;
      contract_service_fee_fixed: number;
      fee_tax_pct: number;
      withholding_tax_pct: number;
      withholding_tax_base: "gross" | "fee";
      withdrawal_fee: number;
      processor_fee_pct: number;
      processor_fee_fixed: number;
      source_url: string;
      effective_date: string;
      eligibility_notes: string;
      is_system: boolean;
    }>;
  }>("/finance/templates");
}

export async function getFxRates(fromCurr = "USD", toCurr = "INR", manualRate?: number) {
  const q = new URLSearchParams({ from_currency: fromCurr, to_currency: toCurr });
  if (manualRate != null) q.set("manual_rate", String(manualRate));
  return request<{
    disclaimer: string;
    rate: {
      from_currency: string;
      to_currency: string;
      benchmark_rate: number;
      offered_rate: number;
      spread_pct: number;
      spread_cost_per_unit: number;
      rate_type: string;
      provider: string;
      is_outage: boolean;
      is_stale: boolean;
      timestamp: string;
    };
  }>(`/finance/fx-rates?${q.toString()}`);
}

export async function listUserEarnings(statusFilter?: string) {
  const q = statusFilter ? `?status_filter=${statusFilter}` : "";
  return request<{
    disclaimer: string;
    summary: {
      cash_received: number;
      gross_paid: number;
      pipeline_estimated_gross: number;
      platform_fees_paid: number;
      withholding_tax_credits: number;
      effective_take_home_rate_pct: number;
      monthly_summary: Array<{
        month: string;
        gross: number;
        net_cash: number;
        fees: number;
        withholding_credits: number;
      }>;
    };
    earnings: Array<{
      id: string;
      project_title: string;
      client_name: string | null;
      platform: string;
      contract_id: string | null;
      currency: string;
      gross_amount: number;
      contract_service_fee: number;
      fee_tax: number;
      withholding_tax: number;
      withdrawal_fee: number;
      processor_fee: number;
      other_expenses: number;
      actual_fx_rate: number | null;
      net_payout_amount: number;
      net_received_in_bank: number;
      invoice_status: "draft" | "invoiced" | "paid" | "cancelled";
      payment_date: string | null;
      notes: string | null;
      created_at: string;
    }>;
  }>(`/finance/earnings${q}`, { auth: true });
}

export async function createUserEarning(payload: Record<string, unknown>) {
  return request<{
    disclaimer: string;
    earning: {
      id: string;
      project_title: string;
      gross_amount: number;
      net_received_in_bank: number;
      invoice_status: string;
    };
  }>("/finance/earnings", {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });
}

export async function deleteUserEarning(id: string) {
  return request<{ status: string; earning_id: string }>(`/finance/earnings/${id}`, {
    method: "DELETE",
    auth: true,
  });
}
