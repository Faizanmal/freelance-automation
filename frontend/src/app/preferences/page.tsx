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
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
        setMessage("Preferences saved successfully!");
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

  const inputClass = "w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60 shadow-inner";

  return (
    <motion.main 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-10"
    >
      <section className="flex flex-wrap items-end justify-between gap-4">
        <motion.div initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }}>
          <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Preferences
          </h1>
          <p className="mt-2 text-[var(--fog)]">
            {user ? `Signed in as ${user.email}` : "Loading…"}
            {billing ? <span className="ml-2 inline-flex items-center rounded-full bg-white/10 px-2 py-0.5 text-xs text-[var(--signal)]">{billing.is_pro ? "PRO" : "FREE"}</span> : ""}
          </p>
        </motion.div>
        <motion.div initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="flex gap-3 text-sm">
          <Link href="/pricing" className="text-[var(--signal)] hover:underline">
            Pricing
          </Link>
          <Link href="/matches" className="text-[var(--signal)] hover:underline">
            Matches
          </Link>
          <button
            type="button"
            className="text-[var(--mute)] hover:text-[var(--ember)] transition"
            onClick={() => {
              logout();
              router.push("/auth");
            }}
          >
            Sign out
          </button>
        </motion.div>
      </section>

      <div className="grid gap-10 lg:grid-cols-[1fr_400px] items-start">
        <div className="space-y-10">
          <Card className="p-8">
            <h2 className="text-2xl mb-2" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Billing
            </h2>
            <p className="text-sm text-[var(--mute)] mb-6">
              Free covers public boards and email alerts. Pro unlocks marketplaces and multi-channel delivery.
            </p>
            <div className="flex flex-wrap gap-3">
              {!billing?.is_pro ? (
                <Button
                  type="button"
                  onClick={() => runBillingAction(billing?.stripe_enabled ? "checkout" : "dev")}
                  disabled={pending}
                >
                  {billing?.stripe_enabled ? "Upgrade to Pro" : "Activate Pro (dev)"}
                </Button>
              ) : billing.stripe_enabled ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => runBillingAction("portal")}
                  disabled={pending}
                >
                  Manage subscription
                </Button>
              ) : (
                <div className="rounded-full bg-[var(--signal)]/10 px-4 py-2 text-sm text-[var(--signal)] border border-[var(--signal)]/30">
                  Pro active (local/dev)
                </div>
              )}
            </div>
          </Card>

          <Card className="p-8">
            <h2 className="text-2xl mb-6" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Matching Criteria
            </h2>
            <form onSubmit={onSave} className="grid gap-6">
              <label className="grid gap-2 text-sm">
                <span className="text-[var(--fog)] font-medium">Keywords (comma separated)</span>
                <input
                  value={keywordsText}
                  onChange={(event) => setKeywordsText(event.target.value)}
                  className={inputClass}
                />
              </label>
              <label className="grid gap-2 text-sm">
                <span className="text-[var(--fog)] font-medium">Exclude keywords</span>
                <input
                  value={excludeText}
                  onChange={(event) => setExcludeText(event.target.value)}
                  className={inputClass}
                />
              </label>
              
              <div className="grid gap-6 md:grid-cols-2">
                <label className="grid gap-2 text-sm">
                  <span className="text-[var(--fog)] font-medium">Min budget</span>
                  <input
                    type="number"
                    value={prefs.min_budget ?? ""}
                    onChange={(event) =>
                      setPrefs((current) => ({
                        ...current,
                        min_budget: event.target.value === "" ? null : Number(event.target.value),
                      }))
                    }
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-2 text-sm">
                  <span className="text-[var(--fog)] font-medium">Max budget</span>
                  <input
                    type="number"
                    value={prefs.max_budget ?? ""}
                    onChange={(event) =>
                      setPrefs((current) => ({
                        ...current,
                        max_budget: event.target.value === "" ? null : Number(event.target.value),
                      }))
                    }
                    className={inputClass}
                  />
                </label>
              </div>

              <div className="pt-6 border-t border-white/10">
                <h3 className="text-xl mb-4" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
                  Delivery Channels
                </h3>
                <label className="grid gap-2 text-sm mb-4">
                  <span className="text-[var(--fog)] font-medium">Notification channels</span>
                  <input
                    value={channelsText}
                    onChange={(event) => setChannelsText(event.target.value)}
                    placeholder="email, slack, telegram"
                    className={inputClass}
                  />
                </label>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="grid gap-2 text-sm">
                    <span className="text-[var(--fog)] font-medium">Alert email</span>
                    <input
                      type="email"
                      value={prefs.alert_email || ""}
                      onChange={(event) => setPrefs((current) => ({ ...current, alert_email: event.target.value }))}
                      className={inputClass}
                    />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span className="text-[var(--fog)] font-medium text-[var(--signal)]">Slack webhook URL (Pro)</span>
                    <input
                      value={prefs.slack_webhook_url || ""}
                      onChange={(event) => setPrefs((current) => ({ ...current, slack_webhook_url: event.target.value }))}
                      className={inputClass}
                    />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span className="text-[var(--fog)] font-medium text-[var(--signal)]">Telegram chat ID (Pro)</span>
                    <input
                      value={prefs.telegram_chat_id || ""}
                      onChange={(event) => setPrefs((current) => ({ ...current, telegram_chat_id: event.target.value }))}
                      className={inputClass}
                    />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span className="text-[var(--fog)] font-medium text-[var(--signal)]">Discord webhook (Pro)</span>
                    <input
                      value={prefs.discord_webhook_url || ""}
                      onChange={(event) => setPrefs((current) => ({ ...current, discord_webhook_url: event.target.value }))}
                      className={inputClass}
                    />
                  </label>
                </div>
              </div>

              <div className="flex items-center justify-between pt-6 border-t border-white/10">
                <Button type="submit" disabled={pending}>
                  {pending ? "Saving…" : "Save all preferences"}
                </Button>
                
                <AnimatePresence>
                  {message && (
                    <motion.p 
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="text-sm font-medium text-[var(--signal)]"
                    >
                      {message}
                    </motion.p>
                  )}
                </AnimatePresence>
                {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
              </div>
            </form>
          </Card>
        </div>

        <div className="sticky top-10">
          <h2 className="text-2xl mb-4" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Recent Matches
          </h2>
          <div className="space-y-4">
            <AnimatePresence mode="popLayout">
              {matches.map((job, i) => (
                <motion.a 
                  key={job.id} 
                  href={job.url} 
                  target="_blank" 
                  rel="noreferrer" 
                  className="block group"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <Card className="p-4 transition-transform group-hover:-translate-y-1 group-hover:border-[var(--signal)]/40">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h3 className="text-sm font-medium leading-tight group-hover:text-[var(--signal)] transition-colors">{job.title}</h3>
                      <span className="text-xs shrink-0 rounded bg-[var(--signal)]/10 text-[var(--signal)] px-1.5 py-0.5 border border-[var(--signal)]/20">
                        {Math.round((job.match_score || 0) * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-[var(--mute)]">
                      {[job.company, job.source_name].filter(Boolean).join(" · ")}
                    </p>
                  </Card>
                </motion.a>
              ))}
            </AnimatePresence>
            {!pending && matches.length === 0 ? (
              <p className="text-sm text-[var(--mute)] bg-black/20 p-4 rounded-xl border border-white/5">
                No matches yet. Save your keywords and wait for the next scrape cycle.
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </motion.main>
  );
}
