"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { useIsAuthenticated } from "@/lib/auth-state";
import {
  activateDevPro,
  getBillingUsage,
  getProviderEligibility,
  getToken,
  getUnitEconomics,
  listBillingPlans,
  startCheckout,
  type BillingPlan,
  type UserUsageStatus,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/cn";

export default function PricingPage() {
  const router = useRouter();
  const authed = useIsAuthenticated();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [devActivateAllowed, setDevActivateAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [userUsage, setUserUsage] = useState<UserUsageStatus | null>(null);
  const [, setUnitEconomics] = useState<Awaited<ReturnType<typeof getUnitEconomics>> | null>(null);
  const [, setProviderEligibility] = useState<Awaited<ReturnType<typeof getProviderEligibility>> | null>(null);

  useEffect(() => {
    const token = getToken();

    startTransition(async () => {
      try {
        const data = await listBillingPlans();
        setPlans(data.plans);
        setStripeEnabled(data.stripe_enabled);
        setDevActivateAllowed(Boolean(data.dev_activate_allowed));

        if (token) {
          getBillingUsage()
            .then(setUserUsage)
            .catch(() => {});
        }

        getUnitEconomics()
          .then(setUnitEconomics)
          .catch(() => {});

        getProviderEligibility()
          .then(setProviderEligibility)
          .catch(() => {});
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load plans");
      } finally {
        setLoading(false);
      }
    });
  }, []);

  const upgrade = () => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    setUpgrading(true);
    startTransition(async () => {
      try {
        setError(null);
        if (stripeEnabled) {
          const checkout = await startCheckout();
          window.location.href = checkout.url;
          return;
        }
        if (!devActivateAllowed) {
          setError("Pro checkout is not open yet. Start free — we’ll enable upgrades soon.");
          return;
        }
        await activateDevPro();
        router.push("/preferences?billing=dev-pro");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upgrade failed");
      } finally {
        setUpgrading(false);
      }
    });
  };

  const proCheckoutReady = stripeEnabled || devActivateAllowed;

  return (
    <div className="flex flex-1 flex-col gap-10 max-w-6xl mx-auto px-4 py-8">
      <PageHeader
        eyebrow="Transparent Pricing & Plans"
        title="Predictable tools, honest subscriptions"
        description="Core discovery, save/skip, and basic matching are included in the Free plan. Pro raises AI copilot quotas and multichannel alerts; paying never boosts a match score or ranking position."
      />

      {/* Ranking policy */}
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-xs text-emerald-900 dark:text-emerald-100 flex items-start gap-3">
        <ShieldCheck className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
        <div>
          <span className="font-semibold text-emerald-800 dark:text-emerald-300">
            Ranking policy:
          </span>
          <p className="mt-0.5 opacity-90">
            Pro does not change match scores or ranking position. Lead ordering uses relevance to your Hunt Rules. Current plan limits and included features are listed below.
          </p>
        </div>
      </div>

      {/* Current User Quota & Usage Meter (if signed in) */}
      {userUsage && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">
                Active Plan Usage
              </span>
              <h3 className="text-base font-bold text-[var(--text)]">
                Current Plan: {userUsage.plan.toUpperCase()} ({userUsage.subscription_status})
              </h3>
            </div>
            <Link
              href="/preferences"
              className="text-xs text-[var(--accent)] underline hover:opacity-85 font-medium"
            >
              Manage Preferences ↗
            </Link>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            {Object.entries(userUsage.features).map(([feat, info]) => (
              <div key={feat} className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
                <span className="text-xs font-medium text-[var(--text-muted)] uppercase">
                  {feat.replace("_", " ")}
                </span>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className="text-lg font-bold text-[var(--text)]">
                    {info.units_used} / {info.limit}
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">{info.units_remaining} left</span>
                </div>
                <div className="mt-2 h-1.5 w-full rounded-full bg-[var(--border)] overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      info.pct_used > 85 ? "bg-amber-500" : "bg-[var(--accent)]",
                    )}
                    style={{ width: `${Math.min(100, info.pct_used)}%` }}
                  />
                </div>
                <span className="mt-1.5 block text-[10px] text-[var(--text-muted)]">
                  Resets: {new Date(info.reset_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plans Grid */}
      {loading ? (
        <div className="grid gap-6 md:grid-cols-2">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      ) : (
        <section className="grid gap-6 md:grid-cols-2">
          {plans.map((plan) => {
            const isPro = plan.id === "pro";
            return (
              <Card
                key={plan.id}
                className={cn(
                  "relative flex flex-col p-6 md:p-8",
                  isPro && "border-[var(--accent)]/50 ring-2 ring-[var(--accent)]/20 shadow-sm",
                )}
              >
                {isPro ? (
                  <Badge variant="accent" className="absolute top-4 right-4">
                    Pro
                  </Badge>
                ) : (
                  <span className="absolute top-4 right-4 rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                    Free plan
                  </span>
                )}
                <div className="flex items-baseline justify-between gap-3">
                  <h2
                    className="text-3xl text-[var(--text)]"
                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}
                  >
                    {plan.id === "pro" ? "Pro Subscription" : "Free Plan"}
                  </h2>
                  <p className="text-2xl font-bold text-[var(--accent)]">{plan.price_label}</p>
                </div>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {isPro
                    ? "Higher hunt density, AI copilot budgets, and multi-channel conveniences. Cancel anytime."
                    : "Core discovery, ranked leads, save/skip, and native proposal starter."}
                </p>

                <ul className="mt-6 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex gap-2 text-sm text-[var(--text-secondary)]">
                      <Check className="mt-0.5 size-4 shrink-0 text-[var(--accent)]" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8 pt-4 border-t border-[var(--border)]">
                  {isPro ? (
                    proCheckoutReady ? (
                      <Button type="button" onClick={upgrade} disabled={upgrading} className="w-full">
                        {upgrading
                          ? "Working…"
                          : stripeEnabled
                            ? `Upgrade to Pro (${plan.price_label})`
                            : "Activate Pro (Local Sandbox)"}
                      </Button>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-xs text-[var(--text-muted)]">
                          Pro checkout opens soon. Start free today — your Hunt Rules and leads stay with you when upgrades unlock.
                        </p>
                        <Button disabled variant="outline" className="w-full opacity-70">
                          Pro coming soon
                        </Button>
                      </div>
                    )
                  ) : (
                    <Link
                      href={authed ? "/preferences" : "/auth?mode=register"}
                      className="inline-flex h-10 w-full items-center justify-center rounded-[var(--radius)] border border-[var(--border)] px-5 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
                    >
                      {authed ? "Current Plan (Free)" : "Get Started Free"}
                    </Link>
                  )}
                </div>
              </Card>
            );
          })}
        </section>
      )}

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
    </div>
  );
}
