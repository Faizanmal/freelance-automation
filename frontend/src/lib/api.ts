const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "signal_desk_token";
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
  freelance_focus?: boolean;
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
  is_totp_enabled?: boolean;
  verification_email_sent?: boolean | null;
  detail?: string | null;
};

export type BillingStatus = {
  plan: string;
  subscription_status: string;
  is_pro: boolean;
  stripe_enabled: boolean;
  dev_activate_allowed?: boolean;
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
  window.dispatchEvent(new Event(TOKEN_CHANGE_EVENT));
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

export async function request<T>(path: string, init?: RequestInit & { auth?: boolean }): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (init?.auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new Error("Can't reach the API. Check your connection and try again.");
  }
  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }
  if (!response.ok) {
    const raw = await response.text();
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      const message = formatApiDetail(parsed.detail);
      if (message) throw new Error(message);
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
  user_status?: "save" | "skip" | null;
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

export async function setLeadAction(jobId: number, status: "save" | "skip" | "clear") {
  return request<{ job_id: number; status: "save" | "skip" | null }>(
    `/preferences/leads/${jobId}/action`,
    {
      method: "PUT",
      auth: true,
      body: JSON.stringify({ status }),
    },
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
  return request<
    User & {
      verification_email_sent?: boolean | null;
      auto_verified?: boolean | null;
      verify_url?: string | null;
      detail?: string | null;
    }
  >("/auth/register", {
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

export function logout() {
  setToken(null);
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
  }>("/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) });
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
