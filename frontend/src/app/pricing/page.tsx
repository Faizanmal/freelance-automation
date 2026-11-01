"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import {
  activateDevPro,
  getToken,
  listBillingPlans,
  startCheckout,
  type BillingPlan,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export default function PricingPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [devActivateAllowed, setDevActivateAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);

  useEffect(() => {
    startTransition(async () => {
      try {
        const data = await listBillingPlans();
        setPlans(data.plans);
        setStripeEnabled(data.stripe_enabled);
        setDevActivateAllowed(Boolean(data.dev_activate_allowed));
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
    <div className="flex flex-1 flex-col gap-10">
      <PageHeader
        eyebrow="Pricing"
        title="Signal Desk plans"
        description="Start free with Hunt Rules, ranked leads, and an email digest. Pro raises hunt density and digest caps — not marketplace bid bots."
      />

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      ) : (
        <section className="grid gap-4 md:grid-cols-2">
          {plans.map((plan) => {
            const isPro = plan.id === "pro";
            return (
              <Card
                key={plan.id}
                className={cn(
                  "relative flex flex-col p-6 md:p-8",
                  isPro && "border-[var(--accent)]/40 ring-1 ring-[var(--accent)]/20",
                )}
              >
                {isPro ? (
                  <Badge variant="accent" className="absolute top-4 right-4">
                    Recommended
                  </Badge>
                ) : null}
                <div className="flex items-baseline justify-between gap-3">
                  <h2
                    className="text-3xl text-[var(--text)]"
                    style={{ fontFamily: "var(--font-display), Georgia, serif" }}
                  >
                    {plan.id === "pro" ? "Pro" : plan.id === "free" ? "Free" : plan.id}
                  </h2>
                  <p className="text-xl font-semibold text-[var(--accent)]">{plan.price_label}</p>
                </div>
                <ul className="mt-6 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex gap-2 text-sm text-[var(--text-secondary)]">
                      <Check className="mt-0.5 size-4 shrink-0 text-[var(--accent)]" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-8">
                  {isPro ? (
                    proCheckoutReady ? (
                      <Button type="button" onClick={upgrade} disabled={upgrading} className="w-full sm:w-auto">
                        {upgrading
                          ? "Working…"
                          : stripeEnabled
                            ? "Upgrade to Pro"
                            : "Activate Pro (dev)"}
                      </Button>
                    ) : (
                      <div className="space-y-3">
                        <p className="text-sm text-[var(--text-muted)]">
                          Pro checkout opens soon. Start free today — your Hunt Rules and leads stay with you when upgrades unlock.
                        </p>
                        <Link
                          href="/auth"
                          className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-5 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
                        >
                          Start free
                        </Link>
                      </div>
                    )
                  ) : (
                    <Link
                      href="/auth"
                      className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-5 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
                    >
                      Start free
                    </Link>
                  )}
                </div>
              </Card>
            );
          })}
        </section>
      )}

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {!stripeEnabled && devActivateAllowed ? (
        <p className="text-sm text-[var(--text-muted)]">
          Local/dev mode: Pro can be activated without Stripe for testing.
        </p>
      ) : null}
    </div>
  );
}
