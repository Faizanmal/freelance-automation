import { cn } from "@/lib/cn";

type Props = {
  fit: number;
  trust: number;
  freshness: number;
  compact?: boolean;
  className?: string;
};

function clamp01(n: number) {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

function Meter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "fit" | "trust" | "fresh";
}) {
  const pct = Math.round(clamp01(value) * 100);
  return (
    <div className="min-w-0 flex-1">
      <div className="mb-1 flex items-center justify-between gap-2 text-[10px] font-semibold tracking-wide uppercase">
        <span className="text-[var(--text-muted)]">{label}</span>
        <span className="tabular-nums text-[var(--text-secondary)]" aria-hidden>
          {pct}%
        </span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-[var(--border)]"
        role="meter"
        aria-label={`${label} ${pct} percent`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-300 motion-reduce:transition-none",
            tone === "fit" && "bg-[var(--fit)]",
            tone === "trust" && "bg-[var(--trust)]",
            tone === "fresh" && "bg-[var(--fresh)]",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Separates fit vs trust vs freshness — avoids a single false-precision score.
 * Values are 0–1; labels stay plain language.
 */
export function LeadSignalMeters({ fit, trust, freshness, compact, className }: Props) {
  return (
    <div
      className={cn(
        "grid gap-3",
        compact ? "grid-cols-3" : "grid-cols-1 sm:grid-cols-3",
        className,
      )}
    >
      <Meter label="Fit" value={fit} tone="fit" />
      <Meter label="Trust" value={trust} tone="trust" />
      <Meter label="Fresh" value={freshness} tone="fresh" />
    </div>
  );
}
