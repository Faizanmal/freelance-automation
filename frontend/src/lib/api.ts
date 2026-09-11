const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "signal_desk_token";

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
  description_excerpt?: string | null;
  created_at?: string | null;
};

export type Preferences = {
  id?: number;
  user_id?: string;
  keywords: string[];
  exclude_keywords: string[];
  min_budget: number | null;
  max_budget: number | null;
  sources: string[];
  match_threshold: number;
  notification_channels: string[];
  digest_mode: boolean;
  notes: string | null;
  alert_email?: string | null;
  slack_webhook_url?: string | null;
  telegram_chat_id?: string | null;
  discord_webhook_url?: string | null;
  whatsapp_to?: string | null;
};

export type User = {
  id: string;
  email: string;
  full_name?: string | null;
  plan?: string;
  subscription_status?: string;
};

export type BillingStatus = {
  plan: string;
  subscription_status: string;
  is_pro: boolean;
  stripe_enabled: boolean;
  limits: {
    scrape_limit: number;
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
}

async function request<T>(path: string, init?: RequestInit & { auth?: boolean }): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (init?.auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const raw = await response.text();
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (parsed.detail && typeof parsed.detail === "object" && parsed.detail !== null && "message" in parsed.detail) {
        throw new Error(String((parsed.detail as { message: string }).message));
      }
      if (typeof parsed.detail === "string") throw new Error(parsed.detail);
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

export async function scrapeJobs(
  sources: string[] = ["remoteok", "arbeitnow", "himalayas", "jobicy"],
  limit = 40,
  notify_matches = false,
) {
  return request<{
    total_fetched: number;
    total_ingested: number;
    total_merged: number;
    total_skipped: number;
    alerts_sent?: number;
    sources: Record<string, unknown>;
  }>("/jobs/scrape", {
    method: "POST",
    auth: true,
    body: JSON.stringify({ sources, limit, notify_matches }),
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
};

export type ProposalDraftResponse = {
  job_id: number;
  title: string;
  source_name: string;
  source_url: string;
  provider: string;
  draft: string;
  disclaimer: string;
  form_fields: ApplyFormFields;
};

export async function draftProposal(jobId: number) {
  return request<ProposalDraftResponse>(`/jobs/${jobId}/proposal-draft`, { method: "POST", auth: true });
}

export async function submitApplication(
  jobId: number,
  formFields: ApplyFormFields,
  confirm = true,
) {
  return request<{
    application_id: number;
    job_id: number;
    source_name: string;
    submit_mode: string;
    status: string;
    external_id?: string | null;
    detail?: string | null;
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

export type LeadFinding = {
  job_id: number;
  title: string;
  company?: string | null;
  source_name: string;
  source_label?: string | null;
  source_attribution?: string | null;
  url: string;
  apply_url?: string | null;
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
  freelance_fit?: number;
  freelance_benefits?: string[];
  freelance_benefits_line?: string | null;
  employment_risks?: string[];
};

export type LeadFindingsResponse = {
  generated_at: string;
  total_scanned: number;
  total_matched: number;
  total_findings: number;
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

export async function getAuthFindings(limit = 10, freelanceFocus = true) {
  const query = new URLSearchParams({
    limit: String(limit),
    freelance_focus: String(freelanceFocus),
  });
  return request<LeadFindingsResponse>(`/preferences/findings?${query}`, { auth: true });
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
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name }),
  });
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = (await response.json()) as { access_token: string };
  setToken(data.access_token);
  return data;
}

export async function me() {
  return request<User>("/users/me", { auth: true });
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
  return request<{ total: number; items: Job[] }>("/preferences/matches", { auth: true });
}

export async function getBilling() {
  return request<BillingStatus>("/billing/me", { auth: true });
}

export async function listBillingPlans() {
  return request<{ stripe_enabled: boolean; plans: BillingPlan[] }>("/billing/plans");
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

export function logout() {
  setToken(null);
}
