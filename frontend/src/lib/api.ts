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



export async function setLeadAction(jobId: number, status: "save" | "skip" | "pitched" | "won" | "clear") {

  return request<{ job_id: number; status: "save" | "skip" | "pitched" | "won" | null }>(

    `/preferences/leads/${jobId}/action`,

    {

      method: "PUT",

      auth: true,

      body: JSON.stringify({ status }),

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

export async function getLearnedAffinities() {
  return request<LearnedAffinitiesResponse>("/preferences/learned-affinities", { auth: true });
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
