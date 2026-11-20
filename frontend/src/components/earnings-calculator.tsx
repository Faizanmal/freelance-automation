"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";

/**
 * Lightweight planning aid — not tax advice. Shows how many leads need to convert
 * at a given rate; never invents revenue.
 */
export function EarningsCalculator() {
  const [hourly, setHourly] = useState(85);
  const [hoursPerWeek, setHoursPerWeek] = useState(20);
  const [winRate, setWinRate] = useState(8);

  const weekly = useMemo(() => hourly * hoursPerWeek, [hourly, hoursPerWeek]);
  const monthly = useMemo(() => weekly * 4.33, [weekly]);
  const leadsNeeded = useMemo(() => {
    if (winRate <= 0) return null;
    return Math.ceil(100 / winRate);
  }, [winRate]);

  return (
    <Card className="p-5">
      <h2
        className="text-lg text-[var(--text)]"
        style={{ fontFamily: "var(--font-display), Georgia, serif" }}
      >
        Capacity sketch
      </h2>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        Rough planning only — not earnings promises or tax advice. Platform fees are separate from
        what you negotiate on the original listing.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="sd-label">
          <span>Target rate ($/hr)</span>
          <input
            className="sd-input"
            type="number"
            min={1}
            value={hourly}
            onChange={(e) => setHourly(Number(e.target.value) || 0)}
          />
        </label>
        <label className="sd-label">
          <span>Hours / week</span>
          <input
            className="sd-input"
            type="number"
            min={1}
            value={hoursPerWeek}
            onChange={(e) => setHoursPerWeek(Number(e.target.value) || 0)}
          />
        </label>
        <label className="sd-label">
          <span>Win rate (%)</span>
          <input
            className="sd-input"
            type="number"
            min={1}
            max={100}
            value={winRate}
            onChange={(e) => setWinRate(Number(e.target.value) || 0)}
          />
        </label>
      </div>
      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-[var(--text-muted)]">Weekly capacity</dt>
          <dd className="text-lg font-semibold text-[var(--text)]">${Math.round(weekly).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-[var(--text-muted)]">~Monthly</dt>
          <dd className="text-lg font-semibold text-[var(--text)]">${Math.round(monthly).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-[var(--text-muted)]">Leads per win (est.)</dt>
          <dd className="text-lg font-semibold text-[var(--text)]">
            {leadsNeeded == null ? "—" : `~${leadsNeeded}`}
          </dd>
        </div>
      </dl>
    </Card>
  );
}
