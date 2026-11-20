import type { Metadata } from "next";
import { LeadSignalMeters } from "@/components/lead-signal-meters";
import { HuntRulesPreview } from "@/components/hunt-rules-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Design system",
  robots: { index: false, follow: false },
};

/** Local component gallery — synthetic fixtures only; noindex. */
export default function DesignSystemPage() {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-10 px-4 py-10">
      <header>
        <p className="text-xs font-semibold tracking-[0.2em] text-[var(--accent)] uppercase">
          Internal
        </p>
        <h1
          className="mt-2 text-3xl text-[var(--text)]"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Design system
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-muted)]">
          Signal Desk workspace tokens and primitives. Prefer neutral surfaces, accessible accent,
          semantic status, and progressive disclosure. Examples use synthetic fixtures only.
        </p>
      </header>

      <section aria-labelledby="tokens-h">
        <h2 id="tokens-h" className="text-xl text-[var(--text)]">
          Color & status
        </h2>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["bg", "var(--bg)"],
            ["surface", "var(--surface)"],
            ["accent", "var(--accent)"],
            ["fit", "var(--fit)"],
            ["trust", "var(--trust)"],
            ["fresh", "var(--fresh)"],
            ["success", "var(--success)"],
            ["danger", "var(--danger)"],
          ].map(([name, css]) => (
            <div key={name} className="rounded-[var(--radius)] border border-[var(--border)] p-3">
              <div className="mb-2 h-10 rounded-md" style={{ background: css }} />
              <p className="text-xs text-[var(--text-muted)]">{name}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="controls-h">
        <h2 id="controls-h" className="text-xl text-[var(--text)]">
          Controls
        </h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button>Primary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="destructive">Destructive</Button>
          <Badge variant="accent">Accent</Badge>
          <Badge variant="success">Success</Badge>
          <Badge variant="danger">Danger</Badge>
        </div>
        <label className="sd-label mt-4 max-w-sm">
          <span>Sample input</span>
          <input className="sd-input" defaultValue="python, fastapi" aria-label="Sample keywords" />
        </label>
      </section>

      <section aria-labelledby="lead-h">
        <h2 id="lead-h" className="text-xl text-[var(--text)]">
          Lead signals
        </h2>
        <Card className="mt-4 p-5">
          <p className="text-sm font-medium text-[var(--text)]">Synthetic lead — React contract</p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Fit / trust / freshness stay separate — no single false-precision score.
          </p>
          <LeadSignalMeters className="mt-4" fit={0.82} trust={0.64} freshness={0.91} />
        </Card>
      </section>

      <section aria-labelledby="rules-h">
        <h2 id="rules-h" className="text-xl text-[var(--text)]">
          Hunt Rules preview
        </h2>
        <Card className="mt-4 p-5">
          <HuntRulesPreview
            prefs={{
              keywords: ["React", "TypeScript"],
              exclude_keywords: ["unpaid"],
              skills: ["React", "TypeScript"],
              min_budget: null,
              max_budget: null,
              min_hourly_rate: 75,
              sources: [],
              match_threshold: 0.35,
              notification_channels: ["email"],
              digest_mode: true,
              freelance_focus: true,
              digest_days: ["mon", "wed", "fri"],
              digest_time_local: "09:00",
              timezone: "UTC",
              notes: null,
            }}
          />
        </Card>
      </section>

      <section aria-labelledby="states-h">
        <h2 id="states-h" className="text-xl text-[var(--text)]">
          Empty & loading
        </h2>
        <div className="mt-4 space-y-4">
          <Skeleton className="h-16 w-full" />
          <EmptyState
            title="No matching leads"
            description="Widen skills, lower the rate floor, or refresh inventory. Demo fixtures stay local-only."
            actionHref="/preferences"
            actionLabel="Edit Hunt Rules"
          />
        </div>
      </section>
    </div>
  );
}
