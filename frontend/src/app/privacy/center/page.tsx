"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";
import Link from "next/link";
import {
  exportMyData,
  getProfileCompleteness,
  getToken,
  listConsents,
  listMyAudit,
  me,
  upsertConsent,
  type User,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const PURPOSES = [
  {
    id: "analytics",
    label: "Product analytics",
    help: "Anonymous traffic metrics (Plausible) after banner consent.",
  },
  {
    id: "product_email",
    label: "Product email",
    help: "Digest and account alerts to your notification address.",
  },
  {
    id: "marketing_email",
    label: "Occasional product tips",
    help: "Optional tips — off by default. Never sold.",
  },
] as const;

export default function PrivacyCenterPage() {
  const [user, setUser] = useState<User | null>(null);
  const [consents, setConsents] = useState<Record<string, boolean>>({});
  const [completeness, setCompleteness] = useState<{
    score: number;
    checks: Record<string, boolean>;
  } | null>(null);
  const [audit, setAudit] = useState<
    Array<{ action: string; created_at?: string; meta?: unknown }>
  >([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!getToken()) return;
    Promise.all([me(), listConsents(), getProfileCompleteness(), listMyAudit()])
      .then(([u, c, pc, a]) => {
        setUser(u);
        const map: Record<string, boolean> = {};
        for (const item of c.items || []) map[item.purpose] = item.granted;
        setConsents(map);
        setCompleteness(pc);
        setAudit(a.items || []);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load privacy center");
      });
  }, []);

  if (!getToken()) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <Card className="p-8" role="status">
          <h1 className="text-2xl text-[var(--text)]">Privacy center</h1>
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            Sign in to manage consents, export your data, or review recent account activity.
          </p>
          <Link href="/auth" className="mt-6 inline-block text-[var(--signal)] underline">
            Sign in
          </Link>
        </Card>
      </div>
    );
  }

  const onToggle = (purpose: string, granted: boolean) => {
    startTransition(async () => {
      try {
        setError(null);
        await upsertConsent(purpose, granted);
        setConsents((prev) => ({ ...prev, [purpose]: granted }));
        setMessage("Consent updated.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Consent update failed");
      }
    });
  };

  const onExport = (e: FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        const data = await exportMyData();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `signal-desk-export-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        setMessage("Export downloaded. This action was recorded in your access log.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Export failed");
      }
    });
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1
        className="text-3xl text-[var(--text)]"
        style={{ fontFamily: "var(--font-display), Georgia, serif" }}
      >
        Privacy center
      </h1>
      <p className="mt-2 text-sm text-[var(--text-muted)]">
        Preferences, export, deletion path, and auditable sensitive operations. This is not a
        compliance certification.
      </p>

      {message ? (
        <p className="mt-4 text-sm text-[var(--accent)]" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}

      <Card className="mt-6 p-6">
        <h2 className="text-lg text-[var(--text)]">Account</h2>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {user?.email} · role {user?.account_role || "freelancer"} · visibility{" "}
          {user?.profile_visibility || "private"}
        </p>
        {completeness ? (
          <p className="mt-2 text-sm text-[var(--text)]">
            Profile completeness: <strong>{completeness.score}%</strong>
          </p>
        ) : null}
        <form onSubmit={onExport} className="mt-4">
          <Button type="submit" disabled={pending}>
            Download data export
          </Button>
        </form>
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          Deletion is available under{" "}
          <Link href="/preferences?tab=account" className="underline">
            Account settings
          </Link>
          . Policy:{" "}
          <Link href="/privacy" className="underline">
            Privacy
          </Link>
          .
        </p>
      </Card>

      <Card className="mt-6 p-6">
        <h2 className="text-lg text-[var(--text)]">Consents</h2>
        <ul className="mt-4 space-y-4">
          {PURPOSES.map((p) => (
            <li
              key={p.id}
              className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] pb-4 last:border-0"
            >
              <div>
                <p className="text-sm font-medium text-[var(--text)]">{p.label}</p>
                <p className="text-xs text-[var(--text-muted)]">{p.help}</p>
              </div>
              <label className="flex items-center gap-2 text-sm text-[var(--text)]">
                <input
                  type="checkbox"
                  checked={Boolean(consents[p.id])}
                  disabled={pending}
                  onChange={(e) => onToggle(p.id, e.target.checked)}
                />
                Allowed
              </label>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="mt-6 p-6">
        <h2 className="text-lg text-[var(--text)]">Recent sensitive activity</h2>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Login, export, consent, and deletion requests. No passwords or tokens are stored here.
        </p>
        {audit.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--text-muted)]">No recent events yet.</p>
        ) : (
          <ul className="mt-4 space-y-2 text-sm">
            {audit.map((row, idx) => (
              <li key={`${row.action}-${idx}`} className="text-[var(--text-muted)]">
                <span className="text-[var(--text)]">{row.action}</span>
                {row.created_at ? ` · ${row.created_at}` : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
