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
  startCheckout,
  updatePreferences,
  type BillingStatus,
  type Job,
  type Preferences,
  type User,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SecuritySettings } from "@/components/security-settings";

const emptyPrefs: Preferences = {
  keywords: ["python", "fastapi", "react", "typescript"],
  exclude_keywords: [],
  min_budget: null,
  max_budget: null,
  sources: [],
  match_threshold: 0.35,
  notification_channels: ["email"],
  digest_mode: true,
  freelance_focus: true,
  location: "",
  timezone: "",
  digest_days: ["mon", "tue", "wed", "thu", "fri"],
  digest_time_local: "09:00",
  max_per_digest: 10,
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
  const [keywordsText, setKeywordsText] = useState(emptyPrefs.keywords.join(", "));
  const [excludeText, setExcludeText] = useState("");
  const [channelsText, setChannelsText] = useState("email");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const verifyParam = searchParams.get("verify");
  const verifyBanner =
    verifyParam === "auto"
      ? "Account ready — local auto-verify applied (SMTP not configured). You can hunt and open leads now."
      : verifyParam === "smtp"
        ? "Verification email was not delivered. Use “Verify for local dev” below, or configure EMAIL_SMTP_* and resend."
        : verifyParam === "needed"
          ? "Check your inbox to verify email — hunts and digests stay locked until then."
          : user && user.is_verified === false
            ? "Email not verified yet. Hunts stay locked until you verify — use the controls below or open /auth/verify."
            : null;
  const statusMessage = message ?? verifyBanner;

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
        setKeywordsText((currentPrefs.keywords || []).join(", "));
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
        const payload: Preferences = {
          ...prefs,
          keywords: keywordsText.split(",").map((part) => part.trim()).filter(Boolean),
          exclude_keywords: excludeText.split(",").map((part) => part.trim()).filter(Boolean),
          notification_channels: channelsText.split(",").map((part) => part.trim()).filter(Boolean),
          alert_email: prefs.alert_email || null,
          slack_webhook_url: prefs.slack_webhook_url || null,
          telegram_chat_id: prefs.telegram_chat_id || null,
          discord_webhook_url: prefs.discord_webhook_url || null,
          whatsapp_to: prefs.whatsapp_to || null,
        };
        const saved = await updatePreferences(payload);
        setPrefs(saved);
        const authMatches = await getAuthMatches();
        setMatches(authMatches.items);
        setMessage("Hunt Rules saved");
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

  const inputClass =
    "w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60";

  return (
    <main className="flex flex-1 flex-col gap-8">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Hunt Rules
          </h1>
          <p className="mt-2 text-[var(--fog)]">
            {user
              ? `Set what to hunt for · ${user.email}`
              : "Loading…"}
            {billing ? (
              <span className="ml-2 inline-flex items-center rounded-full bg-white/10 px-2 py-0.5 text-xs text-[var(--signal)]">
                {billing.is_pro ? "PRO" : "FREE"}
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/leads" className="text-[var(--signal)] hover:underline">
            Leads
          </Link>
          <button
            type="button"
            className="text-[var(--mute)] transition hover:text-[var(--ember)]"
            onClick={() => {
              logout();
              router.push("/auth");
            }}
          >
            Sign out
          </button>
        </div>
      </section>

      {statusMessage ? (
        <p className="rounded-xl border border-[var(--signal)]/20 bg-[var(--signal)]/10 px-4 py-3 text-sm text-[var(--signal)]">
          {statusMessage}
        </p>
      ) : null}
      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}

      <nav className="flex flex-wrap gap-2 border-b border-white/10 pb-4" aria-label="Hunt Rules sections">
        {TABS.map((item) => {
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => selectTab(item.id)}
              className={`rounded-full px-4 py-1.5 text-sm transition ${
                active
                  ? "border border-[var(--signal)]/60 bg-[var(--signal)]/10 text-[var(--signal)]"
                  : "border border-[var(--mute)]/30 text-[var(--fog)] hover:border-[var(--signal)]/40"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      {tab === "matching" ? (
        <div className="grid gap-10 lg:grid-cols-[1fr_320px] items-start">
          <Card className="p-8">
            <h2 className="mb-2 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Hunt Rules
            </h2>
            <p className="mb-6 text-sm text-[var(--mute)]">
              Background hunters use these rules. You pitch on the original listing.
            </p>
            <form onSubmit={onSave} className="grid gap-6">
              <label className="grid gap-2 text-sm">
                <span className="font-medium text-[var(--fog)]">Keywords (comma separated)</span>
                <input value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} className={inputClass} />
              </label>
              <label className="grid gap-2 text-sm">
                <span className="font-medium text-[var(--fog)]">Exclude keywords</span>
                <input value={excludeText} onChange={(e) => setExcludeText(e.target.value)} className={inputClass} />
              </label>
              <label className="grid gap-2 text-sm">
                <span className="font-medium text-[var(--fog)]">Location / region</span>
                <input
                  value={prefs.location || ""}
                  onChange={(e) => setPrefs((current) => ({ ...current, location: e.target.value }))}
                  placeholder="Remote, US, EU…"
                  className={inputClass}
                />
              </label>
              <div className="grid gap-6 md:grid-cols-2">
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--fog)]">Min budget</span>
                  <input
                    type="number"
                    value={prefs.min_budget ?? ""}
                    onChange={(e) =>
                      setPrefs((current) => ({
                        ...current,
                        min_budget: e.target.value === "" ? null : Number(e.target.value),
                      }))
                    }
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--fog)]">Max budget</span>
                  <input
                    type="number"
                    value={prefs.max_budget ?? ""}
                    onChange={(e) =>
                      setPrefs((current) => ({
                        ...current,
                        max_budget: e.target.value === "" ? null : Number(e.target.value),
                      }))
                    }
                    className={inputClass}
                  />
                </label>
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--paper)]">
                <input
                  type="checkbox"
                  checked={prefs.freelance_focus !== false}
                  onChange={(e) =>
                    setPrefs((current) => ({ ...current, freelance_focus: e.target.checked }))
                  }
                  className="size-4 rounded accent-[var(--signal)]"
                />
                Freelance focus (prefer contract / freelance; downrank full-time W2)
              </label>
              <Button type="submit" disabled={pending}>
                {pending ? "Saving…" : "Save Hunt Rules"}
              </Button>
            </form>
          </Card>
          <div>
            <h2 className="mb-4 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Recent matches
            </h2>
            <div className="space-y-3">
              {matches.map((job) => (
                <a key={job.id} href={job.url} target="_blank" rel="noreferrer" className="block">
                  <Card className="p-4 hover:border-[var(--signal)]/40">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <h3 className="text-sm font-medium leading-tight">{job.title}</h3>
                      <span className="shrink-0 rounded bg-[var(--signal)]/10 px-1.5 py-0.5 text-xs text-[var(--signal)]">
                        {Math.round((job.match_score || 0) * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-[var(--mute)]">
                      {[job.company, job.source_name].filter(Boolean).join(" · ")}
                    </p>
                  </Card>
                </a>
              ))}
              {!pending && matches.length === 0 ? (
                <p className="rounded-xl border border-white/5 bg-black/20 p-4 text-sm text-[var(--mute)]">
                  No matches yet. Save keywords, then open{" "}
                  <Link href="/leads" className="text-[var(--signal)] hover:underline">
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
        <Card className="p-8">
          <h2 className="mb-2 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Email digest
          </h2>
          <p className="mb-6 text-sm text-[var(--mute)]">
            V1 delivers matched leads by email on your show schedule. Multi-channel webhooks stay Pro-only and optional.
          </p>
          <form onSubmit={onSave} className="grid gap-6">
            <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-[var(--paper)]">
              <input
                type="checkbox"
                checked={prefs.digest_mode !== false}
                onChange={(e) => setPrefs((current) => ({ ...current, digest_mode: e.target.checked }))}
                className="size-4 rounded accent-[var(--signal)]"
              />
              Send email digest
            </label>
            <label className="grid gap-2 text-sm">
              <span className="font-medium text-[var(--fog)]">Alert email</span>
              <input
                type="email"
                value={prefs.alert_email || ""}
                onChange={(e) => setPrefs((current) => ({ ...current, alert_email: e.target.value }))}
                className={inputClass}
              />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm">
                <span className="font-medium text-[var(--fog)]">Timezone</span>
                <input
                  value={prefs.timezone || ""}
                  onChange={(e) => setPrefs((current) => ({ ...current, timezone: e.target.value }))}
                  placeholder="America/New_York"
                  className={inputClass}
                />
              </label>
              <label className="grid gap-2 text-sm">
                <span className="font-medium text-[var(--fog)]">Digest time (local HH:MM)</span>
                <input
                  value={prefs.digest_time_local || ""}
                  onChange={(e) => setPrefs((current) => ({ ...current, digest_time_local: e.target.value }))}
                  placeholder="09:00"
                  className={inputClass}
                />
              </label>
            </div>
            <label className="grid gap-2 text-sm">
              <span className="font-medium text-[var(--fog)]">Digest days (comma separated)</span>
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
            <label className="grid gap-2 text-sm">
              <span className="font-medium text-[var(--fog)]">Max leads per digest</span>
              <input
                type="number"
                min={1}
                max={50}
                value={prefs.max_per_digest ?? 10}
                onChange={(e) =>
                  setPrefs((current) => ({
                    ...current,
                    max_per_digest: e.target.value === "" ? 10 : Number(e.target.value),
                  }))
                }
                className={inputClass}
              />
            </label>
            <details className="rounded-xl border border-white/10 bg-black/20 p-4">
              <summary className="cursor-pointer text-sm text-[var(--mute)]">
                Advanced channels (Pro, optional)
              </summary>
              <div className="mt-4 grid gap-4">
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--fog)]">Notification channels</span>
                  <input
                    value={channelsText}
                    onChange={(e) => setChannelsText(e.target.value)}
                    placeholder="email"
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--signal)]">Slack webhook</span>
                  <input
                    value={prefs.slack_webhook_url || ""}
                    onChange={(e) => setPrefs((current) => ({ ...current, slack_webhook_url: e.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--signal)]">Telegram chat ID</span>
                  <input
                    value={prefs.telegram_chat_id || ""}
                    onChange={(e) => setPrefs((current) => ({ ...current, telegram_chat_id: e.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-[var(--signal)]">Discord webhook</span>
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
              <Link href="/notifications" className="self-center text-sm text-[var(--signal)] hover:underline">
                Alert history
              </Link>
            </div>
          </form>
        </Card>
      ) : null}

      {tab === "billing" ? (
        <div className="space-y-6">
          {user && user.is_verified === false ? (
            <Card className="border-[var(--ember)]/30 p-8">
              <h2 className="mb-2 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
                Email verification
              </h2>
              <p className="mb-4 text-sm text-[var(--mute)]">Hunts stay locked until your email is verified.</p>
              <div className="flex flex-wrap gap-3">
                <Button
                  type="button"
                  variant="outline"
                  disabled={pending || !user.email}
                  onClick={() =>
                    startTransition(async () => {
                      try {
                        setError(null);
                        const res = await resendVerification(user.email);
                        setMessage(res.detail);
                        if (res.auto_verified) setUser(await me());
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Resend failed");
                      }
                    })
                  }
                >
                  Resend verification
                </Button>
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
                            : "Dev verify is only available outside production",
                        );
                      }
                    })
                  }
                >
                  Verify for local dev
                </Button>
              </div>
            </Card>
          ) : null}
          <Card className="p-8">
            <h2 className="mb-2 text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Billing
            </h2>
            <p className="mb-6 text-sm text-[var(--mute)]">
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
                  <p className="text-sm text-[var(--mute)]">
                    Billing is not configured. Set Stripe keys to enable upgrades.
                  </p>
                )
              ) : billing.stripe_enabled ? (
                <Button type="button" variant="outline" onClick={() => runBillingAction("portal")} disabled={pending}>
                  Manage subscription
                </Button>
              ) : (
                <div className="rounded-full border border-[var(--signal)]/30 bg-[var(--signal)]/10 px-4 py-2 text-sm text-[var(--signal)]">
                  Pro active (local/dev)
                </div>
              )}
              <Link href="/pricing" className="self-center text-sm text-[var(--signal)] hover:underline">
                Compare plans
              </Link>
            </div>
          </Card>
        </div>
      ) : null}

      {tab === "security" && user ? (
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
      ) : null}
    </main>
  );
}

export default function PreferencesPage() {
  return (
    <Suspense fallback={<main className="p-8 text-[var(--mute)]">Loading Hunt Rules…</main>}>
      <PreferencesPageInner />
    </Suspense>
  );
}
