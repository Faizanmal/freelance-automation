"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState, useTransition } from "react";
import {
  activateDevPro,
  getAuthMatches,
  getBilling,
  getPreferences,
  getToken,
  logout,
  me,
  openBillingPortal,
  startCheckout,
  updatePreferences,
  type BillingStatus,
  type Job,
  type Preferences,
  type User,
} from "@/lib/api";

const emptyPrefs: Preferences = {
  keywords: ["python", "fastapi", "react", "typescript"],
  exclude_keywords: [],
  min_budget: null,
  max_budget: null,
  sources: [],
  match_threshold: 0.35,
  notification_channels: ["email"],
  digest_mode: false,
  notes: null,
  alert_email: "",
  slack_webhook_url: "",
  telegram_chat_id: "",
  discord_webhook_url: "",
  whatsapp_to: "",
};

export default function PreferencesPage() {
  const router = useRouter();
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
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load preferences");
        logout();
        router.push("/auth");
      }
    });
  }, [router]);

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
        setMessage("Preferences saved");
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
          return;
        }
        const response = action === "checkout" ? await startCheckout() : await openBillingPortal();
        window.location.href = response.url;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Billing action failed");
      }
    });
  };

  return (
    <main className="flex flex-1 flex-col gap-10">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Preferences
          </h1>
          <p className="mt-2 text-[var(--fog)]">
            {user ? `Signed in as ${user.email}` : "Loading…"}
            {billing ? ` · ${billing.is_pro ? "Pro" : "Free"} plan` : ""}
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/pricing" className="text-[var(--signal)]">
            Pricing
          </Link>
          <Link href="/matches" className="text-[var(--signal)]">
            Matches
          </Link>
          <button
            type="button"
            className="text-[var(--mute)]"
            onClick={() => {
              logout();
              router.push("/auth");
            }}
          >
            Sign out
          </button>
        </div>
      </section>

      <section className="max-w-2xl border-b border-white/10 pb-8">
        <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Billing
        </h2>
        <p className="mt-2 text-sm text-[var(--mute)]">
          Free covers public boards and email alerts. Pro unlocks marketplaces and multi-channel delivery.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          {!billing?.is_pro ? (
            <button
              type="button"
              onClick={() => runBillingAction(billing?.stripe_enabled ? "checkout" : "dev")}
              disabled={pending}
              className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
            >
              {billing?.stripe_enabled ? "Upgrade to Pro" : "Activate Pro (dev)"}
            </button>
          ) : billing.stripe_enabled ? (
            <button
              type="button"
              onClick={() => runBillingAction("portal")}
              disabled={pending}
              className="rounded-full border border-white/20 px-5 py-2.5 disabled:opacity-60"
            >
              Manage subscription
            </button>
          ) : (
            <p className="text-sm text-[var(--signal)]">Pro active (local/dev)</p>
          )}
        </div>
      </section>

      <form onSubmit={onSave} className="grid max-w-2xl gap-4">
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Keywords</span>
          <input
            value={keywordsText}
            onChange={(event) => setKeywordsText(event.target.value)}
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Exclude keywords</span>
          <input
            value={excludeText}
            onChange={(event) => setExcludeText(event.target.value)}
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Profile notes (used in apply forms)</span>
          <textarea
            value={prefs.notes || ""}
            onChange={(event) => setPrefs((current) => ({ ...current, notes: event.target.value }))}
            rows={4}
            placeholder="Years of experience, stack, tone, proof points…"
            className="rounded-2xl border border-white/15 bg-black/20 px-4 py-3 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="grid gap-1 text-sm">
            <span className="text-[var(--mute)]">Min budget</span>
            <input
              type="number"
              value={prefs.min_budget ?? ""}
              onChange={(event) =>
                setPrefs((current) => ({
                  ...current,
                  min_budget: event.target.value === "" ? null : Number(event.target.value),
                }))
              }
              className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-[var(--mute)]">Max budget</span>
            <input
              type="number"
              value={prefs.max_budget ?? ""}
              onChange={(event) =>
                setPrefs((current) => ({
                  ...current,
                  max_budget: event.target.value === "" ? null : Number(event.target.value),
                }))
              }
              className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
            />
          </label>
        </div>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Notification channels</span>
          <input
            value={channelsText}
            onChange={(event) => setChannelsText(event.target.value)}
            placeholder="email, slack, telegram"
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Alert email</span>
          <input
            type="email"
            value={prefs.alert_email || ""}
            onChange={(event) => setPrefs((current) => ({ ...current, alert_email: event.target.value }))}
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Slack webhook URL (Pro)</span>
          <input
            value={prefs.slack_webhook_url || ""}
            onChange={(event) => setPrefs((current) => ({ ...current, slack_webhook_url: event.target.value }))}
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Telegram chat ID (Pro)</span>
          <input
            value={prefs.telegram_chat_id || ""}
            onChange={(event) => setPrefs((current) => ({ ...current, telegram_chat_id: event.target.value }))}
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Discord webhook URL (Pro)</span>
          <input
            value={prefs.discord_webhook_url || ""}
            onChange={(event) => setPrefs((current) => ({ ...current, discord_webhook_url: event.target.value }))}
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">WhatsApp number (Pro)</span>
          <input
            value={prefs.whatsapp_to || ""}
            onChange={(event) => setPrefs((current) => ({ ...current, whatsapp_to: event.target.value }))}
            placeholder="+15551234567"
            className="rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--mute)]">Match threshold ({prefs.match_threshold})</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={prefs.match_threshold}
            onChange={(event) => setPrefs((current) => ({ ...current, match_threshold: Number(event.target.value) }))}
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-[var(--mute)]">
          <input
            type="checkbox"
            checked={prefs.digest_mode}
            onChange={(event) => setPrefs((current) => ({ ...current, digest_mode: event.target.checked }))}
          />
          Digest mode
        </label>
        <button
          type="submit"
          disabled={pending}
          className="w-fit rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
        >
          {pending ? "Saving…" : "Save preferences"}
        </button>
        {message ? <p className="text-sm text-[var(--signal)]">{message}</p> : null}
        {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      </form>

      <section>
        <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Your matches
        </h2>
        <div className="mt-4 space-y-3">
          {matches.map((job) => (
            <a key={job.id} href={job.url} target="_blank" rel="noreferrer" className="block border-b border-white/10 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-lg">{job.title}</h3>
                <span className="text-sm text-[var(--signal)]">{Math.round((job.match_score || 0) * 100)}%</span>
              </div>
              <p className="text-sm text-[var(--mute)]">
                {[job.company, job.seniority, job.source_name].filter(Boolean).join(" · ")}
              </p>
            </a>
          ))}
          {!pending && matches.length === 0 ? (
            <p className="text-[var(--mute)]">No matches yet. Pull jobs from the desk, then save keywords.</p>
          ) : null}
        </div>
      </section>
    </main>
  );
}
