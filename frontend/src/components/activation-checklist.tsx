"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getAuthFindings, getPreferences, getToken, me } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckCircle2, Circle } from "lucide-react";

const READY_KEY = "signaldesk_ready";

type ChecklistState = {
  keywords: boolean;
  verified: boolean;
  leads: boolean;
};

export function ActivationChecklist() {
  const [visible, setVisible] = useState(false);
  const [state, setState] = useState<ChecklistState>({
    keywords: false,
    verified: false,
    leads: false,
  });

  useEffect(() => {
    if (!getToken()) return;
    if (localStorage.getItem(READY_KEY) === "true") return;

    let cancelled = false;
    (async () => {
      try {
        const [user, prefs, findings] = await Promise.all([
          me(),
          getPreferences(),
          getAuthFindings(5).catch(() => null),
        ]);
        if (cancelled) return;
        const next: ChecklistState = {
          keywords:
            (prefs.skills || []).length > 0 || (prefs.keywords || []).length > 0,
          verified: Boolean(user.is_verified),
          leads: Boolean(findings && findings.total_findings > 0),
        };
        setState(next);
        if (next.keywords && next.verified && next.leads) {
          localStorage.setItem(READY_KEY, "true");
          setVisible(false);
          return;
        }
        setVisible(true);
      } catch {
        if (!cancelled) setVisible(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (!visible) return null;

  const items = [
    {
      done: state.keywords,
      label: "Set Hunt Rules",
      href: "/preferences?tab=matching",
      cta: "Hunt Rules",
    },
    {
      done: state.verified,
      label: "Verify your email",
      href: "/preferences?tab=billing",
      cta: "Verify",
    },
    {
      done: state.leads,
      label: "Review your first leads",
      href: "/leads",
      cta: "Open Leads",
    },
  ];

  const dismiss = () => {
    localStorage.setItem(READY_KEY, "true");
    setVisible(false);
  };

  return (
    <Card
      className="border-[var(--accent)]/25 bg-[var(--accent-muted)]/40 p-6"
      data-testid="activation-checklist"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-[var(--text)]">Get ready</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Finish these once — then the desk stays out of your way.
          </p>
        </div>
        <Button type="button" variant="ghost" onClick={dismiss}>
          Dismiss
        </Button>
      </div>
      <ul className="mt-5 space-y-1">
        {items.map((item) => (
          <li
            key={item.label}
            className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] py-3 text-sm"
          >
            <span className="inline-flex items-center gap-2 text-[var(--text)]">
              {item.done ? (
                <CheckCircle2 className="size-4 text-[var(--success)]" />
              ) : (
                <Circle className="size-4 text-[var(--text-muted)]" />
              )}
              {item.done ? "Done — " : "Todo — "}
              {item.label}
            </span>
            {!item.done ? (
              <Link href={item.href} className="text-[var(--accent)] hover:underline">
                {item.cta}
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}
