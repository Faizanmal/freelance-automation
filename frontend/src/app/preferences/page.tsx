"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState, useTransition } from "react";
import {
  activateDevPro,
  devVerifyEmail,
  getAuthMatches,
  getBilling,
  getPreferences,
  getToken,
  logout,
  me,
  openBillingPortal,
  resendVerification,
  sendNotification,
  startCheckout,
  updatePreferences,
  type BillingStatus,
  type Job,
  type Preferences,
  type User,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { sanitizeExternalUrl } from "@/lib/security";
import { Button } from "@/components/ui/button";
import { SecuritySettings } from "@/components/security-settings";
import { AccountSettings } from "@/components/account-settings";

const emptyPrefs: Preferences = {
  keywords: [],
  exclude_keywords: [],
  skills: ["python", "fastapi", "react", "typescript"],
  experience_level: "any",
  min_budget: null,
  max_budget: null,
  min_hourly_rate: null,
  sources: [],
  match_threshold: 0.35,
  notification_channels: ["email"],
  digest_mode: true,
  freelance_focus: true,
  location: "",
  timezone: "",
  digest_days: ["mon", "tue", "wed", "thu", "fri"],
  digest_time_local: "09:00",
  max_per_digest: 5,
  notes: null,
  alert_email: "",
  slack_webhook_url: "",
  telegram_chat_id: "",
  discord_webhook_url: "",
  whatsapp_to: "",
};

type PrefTab = "matching" | "alerts" | "billing" | "security";

const TABS: { id: PrefTab; label: string }[] = [
  { id: "matching", label: "Hunt Rules" },
  { id: "alerts", label: "Digest" },
  { id: "billing", label: "Billing" },
  { id: "security", label: "Security" },
];

function parseTab(value: string | null): PrefTab {
  if (value === "alerts" || value === "billing" || value === "security" || value === "matching") {
    return value;
  }
  return "matching";
}

function PreferencesPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));
  const [user, setUser] = useState<User | null>(null);
  const [prefs, setPrefs] = useState<Preferences>(emptyPrefs);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [matches, setMatches] = useState<Job[]>([]);
  const [skillsText, setSkillsText] = useState((emptyPrefs.skills || []).join(", "));
  const [keywordsText, setKeywordsText] = useState("");
  const [excludeText, setExcludeText] = useState("");
  const [channelsText, setChannelsText] = useState("email");
  const [message, setMessage] = useState<string | null>(null);
  const [emailWarning, setEmailWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const allowDevVerify = process.env.NEXT_PUBLIC_ALLOW_DEV_VERIFY === "true";

  const verifyParam = searchParams.get("verify");
  const needsVerify = Boolean(user && user.is_verified === false);
  const verifyBanner =
    verifyParam === "auto"
      ? "Account ready — local auto-verify applied. You can hunt and open leads now."
      : verifyParam === "smtp" || (needsVerify && verifyParam !== "needed")
        ? null
        : verifyParam === "needed"
          ? "Check your inbox to verify email — digests and automated hunts stay locked until then. You can still browse leads, save, and draft bids."
          : null;

  useEffect(() => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    startTransition(async () => {
      try {
        const [currentUser, currentPrefs, authMatches, currentBilling] = await Promise.all([
          me(),
          getPreferences(),
          getAuthMatches(),
          getBilling(),
        ]);
        setUser(currentUser);
        setPrefs(currentPrefs);
        setBilling(currentBilling);
        const skills =
          currentPrefs.skills?.length
            ? currentPrefs.skills
            : currentPrefs.keywords || [];
        setSkillsText(skills.join(", "));
        // Extra requirements = keywords that are not already listed as skills.
        const skillSet = new Set(skills.map((s) => s.toLowerCase()));
        const extra = (currentPrefs.keywords || []).filter(
          (k) => !skillSet.has(k.toLowerCase()),
        );
        setKeywordsText(extra.join(", "));
        setExcludeText((currentPrefs.exclude_keywords || []).join(", "));
        setChannelsText((currentPrefs.notification_channels || ["email"]).join(", "));
        setMatches(authMatches.items);
      } catch {
        setError("Failed to load preferences");
        logout();
        router.push("/auth");
      }
    });
  }, [router]);

  const selectTab = (next: PrefTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", next);
    router.replace(`/preferences?${params.toString()}`);
  };

  const onSave = (event: FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        setEmailWarning(null);
        const payload: Preferences = {
          ...prefs,
          skills: skillsText.split(",").map((part) => part.trim()).filter(Boolean),
          keywords: keywordsText.split(",").map((part) => part.trim()).filter(Boolean),
          exclude_keywords: excludeText.split(",").map((part) => part.trim()).filter(Boolean),
          experience_level: prefs.experience_level || "any",
          notification_channels: channelsText.split(",").map((part) => part.trim()).filter(Boolean),
          alert_email: prefs.alert_email || null,
          slack_webhook_url: prefs.slack_webhook_url || null,
          telegram_chat_id: prefs.telegram_chat_id || null,
          discord_webhook_url: prefs.discord_webhook_url || null,
          whatsapp_to: prefs.whatsapp_to || null,
        };
        const saved = await updatePreferences(payload);
        setPrefs(saved);
        try {
          const authMatches = await getAuthMatches();
          setMatches(authMatches.items);
        } catch {
          // Matches are optional after save — do not surface as a save failure.
        }
        const params = new URLSearchParams(searchParams.toString());
        if (params.has("verify")) {
          params.delete("verify");
          const qs = params.toString();
          router.replace(qs ? `/preferences?${qs}` : "/preferences");
        }
        setMessage(tab === "alerts" ? "Digest settings saved" : "Hunt Rules saved");
        setTimeout(() => setMessage(null), 3000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    });
  };

  const runBillingAction = (action: "checkout" | "portal" | "dev") => {
    startTransition(async () => {
      try {
        setError(null);
        if (action === "dev") {
          const next = await activateDevPro();
          setBilling(next);
          setMessage("Pro activated for local development");
          setTimeout(() => setMessage(null), 3000);
          return;
        }
        const response = action === "checkout" ? await startCheckout() : await openBillingPortal();
        window.location.href = response.url;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Billing action failed");
      }
    });
  };

  const inputClass = "sd-input";

  return (
    <div className="flex flex-1 flex-col gap-8">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl tracking-tight md:text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Hunt Rules
          </h1>
          <p className="mt-2 text-[var(--text-secondary)]">
            {user
              ? `Configure your discovery engine · ${user.email}`
              : "Loading…"}
            {billing ? (
              <span className="ml-2 inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--accent-muted)] px-2 py-0.5 text-xs font-semibold tracking-wide text-[var(--accent)] uppercase">
                {billing.is_pro ? "PRO" : "FREE"}
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/leads" className="text-[var(--accent)] hover:underline">
            Leads
          </Link>
          <button
            type="button"
            className="text-[var(--text-muted)] transition hover:text-[var(--danger)]"
            onClick={() => {
              logout();
              router.push("/auth");
            }}
          >
            Sign out
          </button>
        </div>
      </section>

      {message || verifyBanner ? (
        <p className="rounded-[var(--radius)] border border-[var(--accent)]/25 bg-[var(--accent-muted)] px-4 py-3 text-sm text-[var(--accent)]">
          {message ?? verifyBanner}
        </p>
      ) : null}
      {emailWarning ? (
        <p className="rounded-[var(--radius)] border border-[var(--warning)]/30 bg-[var(--warning-muted)] px-4 py-3 text-sm text-[var(--warning)]">
          {emailWarning}
        </p>
      ) : null}
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}

      {needsVerify ? (
        <Card className="border-[var(--ember)]/30 p-6 md:p-8">
          <h2 className="mb-2 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Verify your email
          </h2>
          <p className="mb-4 text-sm text-[var(--mute)]">
            {verifyParam === "smtp"
              ? "We couldn't send the verification email. Please try again later."
              : "Digests and automated hunts stay locked until your email is verified. You can still browse leads, save, and draft bids. Check your inbox, or resend a fresh link."}
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="outline"
              disabled={pending || !user?.email}
              onClick={() =>
                startTransition(async () => {
                  try {
                    setError(null);
                    setEmailWarning(null);
                    const res = await resendVerification(user!.email);
                    if (res.auto_verified) {
                      setMessage(res.detail);
                      setUser(await me());
                    } else if (res.email_delivered === false) {
                      setEmailWarning(
                        "Verification email could not be delivered. Check server mail settings, then try Resend again.",
                      );
                      setMessage(res.detail);
                    } else {
                      setMessage(res.detail);
                    }
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Resend failed");
                  }
                })
              }
            >
              Resend verification
            </Button>
            {allowDevVerify ? (
              <Button
                type="button"
                disabled={pending}
                onClick={() =>
                  startTransition(async () => {
                    try {
                      setError(null);
                      const res = await devVerifyEmail();
                      setMessage(res.detail);
                      setUser(await me());
                    } catch (err) {
                      setError(
                        err instanceof Error
                          ? err.message
                          : "Local verify is not available on this server",
                      );
                    }
                  })
                }
              >
                Verify for local dev
              </Button>
            ) : null}
            <Link href="/auth/verify" className="self-center text-sm text-[var(--signal)] hover:underline">
              Open verify page
            </Link>
          </div>
        </Card>
      ) : null}

      <nav className="flex flex-wrap gap-1 border-b border-[var(--border)] pb-3" aria-label="Hunt Rules sections">
        {TABS.map((item) => {
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => selectTab(item.id)}
              className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      {tab === "matching" ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px] items-start">
          <Card className="p-6 md:p-8">
            <h2 className="mb-1 text-xl font-semibold text-[var(--text)]">
              Professional profile & opportunity preferences
            </h2>
            <p className="mb-6 text-sm text-[var(--text-muted)]">
              Shared hunters fill one job pool. Your skills and experience rank which leads you see
              and get in your digest. You pitch on the original listing. Digest delivery uses a separate show clock under the Digest tab.
            </p>
            <form onSubmit={onSave} className="grid gap-6">
              <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                <p className="mb-3 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">Professional profile</p>
              <label className="sd-label">
                <span>Skills</span>
                <input
                  value={skillsText}
                  onChange={(e) => setSkillsText(e.target.value)}
                  placeholder="python, fastapi, react, typescript"
                  className={inputClass}
                />
                <span className="text-xs text-[var(--text-muted)]">
                  Primary match signal — stack and tools you want work for.
                </span>
              </label>
              <label className="sd-label mt-4">
                <span>Experience level</span>
                <select
                  value={prefs.experience_level || "any"}
                  onChange={(e) =>
                    setPrefs((current) => ({
                      ...current,
                      experience_level: e.target.value as Preferences["experience_level"],
                    }))
                  }
                  className={inputClass}
                >
                  <option value="any">Any</option>
                  <option value="junior">Junior / entry</option>
                  <option value="mid">Mid-level</option>
                  <option value="senior">Senior</option>
                  <option value="lead">Lead / principal</option>
                </select>
                <span className="text-xs text-[var(--text-muted)]">
                  Soft preference — boosts fit, does not hide the whole pool.
                </span>
              </label>
              </div>
              <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                <p className="mb-3 text-xs font-semibold tracking-wide text-[var(--text-muted)] uppercase">Opportunity preferences</p>
              <label className="sd-label">
                <span>Extra requirements (optional)</span>
                <input
                  value={keywordsText}
                  onChange={(e) => setKeywordsText(e.target.value)}
                  placeholder="graphql, saas, fintech…"
                  className={inputClass}
                />
              </label>
              <label className="sd-label mt-4">
                <span>Exclude</span>
                <input
                  value={excludeText}
                  onChange={(e) => setExcludeText(e.target.value)}
                  placeholder="unpaid, wordpress, agency"
                  className={inputClass}
                />
              </label>
              <label className="sd-label mt-4">
                <span>Location / region</span>
                <input
                  value={prefs.location || ""}
                  onChange={(e) => setPrefs((current) => ({ ...current, location: e.target.value }))}
                  placeholder="Remote, US, EU…"
                  className={inputClass}
                />
              </label>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <label className="sd-label">
                  <span>Min project budget</span>
                  <input
                    type="number"
                    value={prefs.min_budget ?? ""}
                    onChange={(e) =>
                      setPrefs((current) => ({
                        ...current,
                        min_budget: e.target.value === "" ? null : Number(e.target.value),
                      }))
                    }
                    placeholder="e.g. 1500"
                    className={inputClass}
                  />
                </label>
                <label className="sd-label">
                  <span>Max project budget</span>
                  <input
                    type="number"
                    value={prefs.max_budget ?? ""}
                    onChange={(e) =>
                      setPrefs((current) => ({
                        ...current,
                        max_budget: e.target.value === "" ? null : Number(e.target.value),
                      }))
                    }
                    placeholder="e.g. 10000"
                    className={inputClass}
                  />
                </label>
                <label className="sd-label">
                  <span>Min hourly rate ($/hr)</span>
                  <input
                    type="number"
                    value={prefs.min_hourly_rate ?? ""}
                    onChange={(e) =>
                      setPrefs((current) => ({
                        ...current,
                        min_hourly_rate: e.target.value === "" ? null : Number(e.target.value),
                      }))
                    }
                    placeholder="e.g. 50"
                    className={inputClass}
                  />
                </label>
              </div>
              <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--text)]">
                <input
                  type="checkbox"
                  checked={prefs.freelance_focus !== false}
                  onChange={(e) =>
                    setPrefs((current) => ({ ...current, freelance_focus: e.target.checked }))
                  }
                  className="size-4 rounded accent-[var(--accent)]"
                />
                Freelance focus (prefer contract / freelance; downrank full-time W2)
              </label>
              </div>
              <Button type="submit" disabled={pending}>
                {pending ? "Saving…" : "Save Hunt Rules"}
              </Button>
            </form>
          </Card>
          <div>
            <h2 className="mb-4 text-lg font-semibold text-[var(--text)]">
              Recent matches
            </h2>
            <div className="space-y-3">
              {matches.map((job) => (
                <a key={job.id} href={sanitizeExternalUrl(job.url) || "#"} target="_blank" rel="noopener noreferrer" className="block">
                  <Card interactive className="p-4">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <h3 className="text-sm font-medium leading-tight">{job.title}</h3>
                      <span className="shrink-0 rounded-md bg-[var(--accent-muted)] px-1.5 py-0.5 text-xs text-[var(--accent)]">
                        {Math.round((job.match_score || 0) * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)]">
                      {[job.company, job.source_name].filter(Boolean).join(" · ")}
                    </p>
                  </Card>
                </a>
              ))}
              {!pending && matches.length === 0 ? (
                <p className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4 text-sm text-[var(--text-muted)]">
                  No matches yet. Save skills, then open{" "}
                  <Link href="/leads" className="text-[var(--accent)] hover:underline">
                    Leads
                  </Link>
                  .
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {tab === "alerts" ? (
        <Card className="p-6 md:p-8">
          <h2 className="mb-1 text-xl font-semibold text-[var(--text)]">
            Digest schedule
          </h2>
          <p className="mb-6 text-sm text-[var(--text-muted)]">
            Your show clock — email delivery days and time. This is separate from the system hunt schedule that fills the shared opportunity pool.
          </p>
          <form onSubmit={onSave} className="grid gap-6">
            <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--text)]">
              <input
                type="checkbox"
                checked={prefs.digest_mode !== false}
                onChange={(e) => setPrefs((current) => ({ ...current, digest_mode: e.target.checked }))}
                className="size-4 rounded accent-[var(--accent)]"
              />
              Send email digest
            </label>
            <label className="sd-label">
              <span>Alert email</span>
              <input
                type="email"
                value={prefs.alert_email || ""}
                onChange={(e) => setPrefs((current) => ({ ...current, alert_email: e.target.value }))}
                className={inputClass}
              />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="sd-label">
                <span>Timezone</span>
                <input
                  value={prefs.timezone || ""}
                  onChange={(e) => setPrefs((current) => ({ ...current, timezone: e.target.value }))}
                  placeholder="America/New_York"
                  className={inputClass}
                />
              </label>
              <label className="sd-label">
                <span>Digest time (local HH:MM)</span>
                <input
                  value={prefs.digest_time_local || ""}
                  onChange={(e) => setPrefs((current) => ({ ...current, digest_time_local: e.target.value }))}
                  placeholder="09:00"
                  className={inputClass}
                />
              </label>
            </div>
            <label className="sd-label">
              <span>Digest days (comma separated)</span>
              <input
                value={(prefs.digest_days || []).join(", ")}
                onChange={(e) =>
                  setPrefs((current) => ({
                    ...current,
                    digest_days: e.target.value
                      .split(",")
                      .map((part) => part.trim().toLowerCase())
                      .filter(Boolean),
                  }))
                }
                placeholder="mon, tue, wed, thu, fri"
                className={inputClass}
              />
            </label>
            <label className="sd-label">
              <span>
                Max leads per digest
                {billing?.limits.max_digest
                  ? ` (plan cap ${billing.limits.max_digest})`
                  : ""}
              </span>
              <input
                type="number"
                min={1}
                max={billing?.limits.max_digest ?? 25}
                value={prefs.max_per_digest ?? 5}
                onChange={(e) => {
                  const planCap = billing?.limits.max_digest ?? 25;
                  const next =
                    e.target.value === "" ? 5 : Math.min(planCap, Math.max(1, Number(e.target.value)));
                  setPrefs((current) => ({
                    ...current,
                    max_per_digest: next,
                  }));
                }}
                className={inputClass}
              />
              {billing && !billing.is_pro ? (
                <span className="text-xs text-[var(--text-muted)]">
                  Free digests cap at {billing.limits.max_digest ?? 5}.{" "}
                  <Link href="/pricing" className="text-[var(--accent)]">
                    Upgrade for higher caps
                  </Link>
                  .
                </span>
              ) : null}
            </label>
            <details className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
              <summary className="cursor-pointer text-sm text-[var(--text-muted)]">
                Advanced channels (Pro, optional)
              </summary>
              <div className="mt-4 grid gap-4">
                <label className="sd-label">
                  <span>Notification channels</span>
                  <input
                    value={channelsText}
                    onChange={(e) => setChannelsText(e.target.value)}
                    placeholder="email"
                    className={inputClass}
                  />
                </label>
                <label className="sd-label">
                  <span className="text-[var(--accent)]">Slack webhook</span>
                  <input
                    value={prefs.slack_webhook_url || ""}
                    onChange={(e) => setPrefs((current) => ({ ...current, slack_webhook_url: e.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className="sd-label">
                  <span className="text-[var(--accent)]">Telegram chat ID</span>
                  <input
                    value={prefs.telegram_chat_id || ""}
                    onChange={(e) => setPrefs((current) => ({ ...current, telegram_chat_id: e.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className="sd-label">
                  <span className="text-[var(--accent)]">Discord webhook</span>
                  <input
                    value={prefs.discord_webhook_url || ""}
                    onChange={(e) => setPrefs((current) => ({ ...current, discord_webhook_url: e.target.value }))}
                    className={inputClass}
                  />
                </label>
              </div>
            </details>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={pending}>
                {pending ? "Saving…" : "Save digest"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() =>
                  startTransition(async () => {
                    try {
                      setError(null);
                      setEmailWarning(null);
                      const response = await sendNotification({
                        title: "Signal Desk test alert",
                        body: "This is a test from Digest settings. If you received it, outbound email is working.",
                        channels: ["email"],
                        priority: "normal",
                        digest: false,
                      });
                      if (response.status === "failed" || response.status === "partial") {
                        setEmailWarning(
                          "Settings are saved separately — this test alert could not be delivered. Check EMAIL_SMTP_* on the API.",
                        );
                      } else {
                        setMessage("Test alert sent");
                        setTimeout(() => setMessage(null), 3000);
                      }
                    } catch (err) {
                      setEmailWarning(
                        err instanceof Error
                          ? `Test alert failed: ${err.message}`
                          : "Test alert failed — settings were not changed.",
                      );
                    }
                  })
                }
              >
                Send test email
              </Button>
              <Link href="/notifications" className="self-center text-sm text-[var(--accent)] hover:underline">
                Alert history
              </Link>
            </div>
          </form>
        </Card>
      ) : null}

      {tab === "billing" ? (
        <div className="space-y-6">
          <Card className="p-6 md:p-8">
            <h2 className="mb-1 text-xl font-semibold text-[var(--text)]">
              Billing
            </h2>
            <p className="mb-6 text-sm text-[var(--text-muted)]">
              Free covers matched leads and email digest. Pro raises hunt density and digest caps — not marketplace bid bots.
            </p>
            <div className="flex flex-wrap gap-3">
              {!billing?.is_pro ? (
                billing?.stripe_enabled ? (
                  <Button type="button" onClick={() => runBillingAction("checkout")} disabled={pending}>
                    Upgrade to Pro
                  </Button>
                ) : billing?.dev_activate_allowed ? (
                  <Button type="button" onClick={() => runBillingAction("dev")} disabled={pending}>
                    Activate Pro (dev)
                  </Button>
                ) : (
                  <p className="text-sm text-[var(--text-muted)]">
                    Pro checkout opens soon. Your free Hunt Rules and leads stay with you when upgrades unlock.
                  </p>
                )
              ) : billing.stripe_enabled ? (
                <Button type="button" variant="outline" onClick={() => runBillingAction("portal")} disabled={pending}>
                  Manage subscription
                </Button>
              ) : (
                <div className="rounded-md border border-[var(--accent)]/30 bg-[var(--accent-muted)] px-4 py-2 text-sm text-[var(--accent)]">
                  Pro active (local/dev)
                </div>
              )}
              <Link href="/pricing" className="self-center text-sm text-[var(--accent)] hover:underline">
                Compare plans
              </Link>
            </div>
          </Card>
        </div>
      ) : null}

      {tab === "security" && user ? (
        <div className="space-y-6">
          <SecuritySettings
            user={user}
            onUpdate={() =>
              startTransition(async () => {
                try {
                  setUser(await me());
                } catch {
                  /* ignore */
                }
              })
            }
          />
          <AccountSettings user={user} />
        </div>
      ) : null}
    </div>
  );
}

export default function PreferencesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-[var(--text-muted)]">Loading Hunt Rules…</div>}>
      <PreferencesPageInner />
    </Suspense>
  );
}
