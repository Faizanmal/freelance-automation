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

export default function PricingPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [devActivateAllowed, setDevActivateAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const data = await listBillingPlans();
        setPlans(data.plans);
        setStripeEnabled(data.stripe_enabled);
        setDevActivateAllowed(Boolean(data.dev_activate_allowed));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load plans");
      }
    });
  }, []);

  const upgrade = () => {
    if (!getToken()) {
      router.push("/auth");
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        if (stripeEnabled) {
          const checkout = await startCheckout();
          window.location.href = checkout.url;
          return;
        }
        if (!devActivateAllowed) {
          setError("Live billing is not configured yet. Set Stripe keys to enable upgrades.");
          return;
        }
        await activateDevPro();
        router.push("/preferences?billing=dev-pro");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upgrade failed");
      }
    });
  };

  return (
    <main className="flex flex-1 flex-col gap-12">
      <section className="max-w-3xl">
        <p className="text-sm tracking-[0.28em] text-[var(--signal)] uppercase">Pricing</p>
        <h1
          className="mt-3 text-5xl leading-[1.05] tracking-tight md:text-6xl"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Signal Desk plans
        </h1>
        <p className="mt-4 max-w-xl text-lg text-[var(--fog)]">
          Start free with Hunt Rules, ranked leads, and an email digest. Pro raises hunt density and digest caps — not marketplace bid bots.
        </p>
      </section>

      <section className="grid gap-8 md:grid-cols-2">
        {plans.map((plan) => (
          <article key={plan.id} className="border-t border-white/15 pt-6">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-3xl capitalize" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
                {plan.id}
              </h2>
              <p className="text-xl text-[var(--signal)]">{plan.price_label}</p>
            </div>
            <ul className="mt-6 space-y-3 text-[var(--fog)]">
              {plan.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
            {plan.id === "pro" ? (
              stripeEnabled || devActivateAllowed ? (
                <button
                  type="button"
                  onClick={upgrade}
                  disabled={pending}
                  className="mt-8 rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
                >
                  {pending
                    ? "Working…"
                    : stripeEnabled
                      ? "Upgrade with Stripe"
                      : "Activate Pro (dev)"}
                </button>
              ) : (
                <p className="mt-8 text-sm text-[var(--mute)]">
                  Billing is not configured in this environment. Contact support to upgrade.
                </p>
              )
            ) : (
              <Link
                href="/auth"
                className="mt-8 inline-block rounded-full border border-white/20 px-5 py-2.5 text-[var(--paper)]"
              >
                Start free
              </Link>
            )}
          </article>
        ))}
      </section>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {!stripeEnabled && devActivateAllowed ? (
        <p className="text-sm text-[var(--mute)]">
          Stripe keys are optional in development. Set `STRIPE_SECRET_KEY` and `STRIPE_PRICE_PRO` for live checkout.
        </p>
      ) : null}
    </main>
  );
}
