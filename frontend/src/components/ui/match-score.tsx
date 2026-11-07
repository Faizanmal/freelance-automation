import { cn } from "@/lib/cn";

function fitLabel(scorePct: number) {
  if (scorePct >= 85) return "Excellent fit";
  if (scorePct >= 70) return "Strong fit";
  if (scorePct >= 55) return "Potential fit";
  return "Low fit";
}

function fitTone(scorePct: number) {
  if (scorePct >= 85) return "text-[var(--success)] border-[var(--success)]/25 bg-[var(--success-muted)]";
  if (scorePct >= 70) return "text-[var(--accent)] border-[var(--accent)]/25 bg-[var(--accent-muted)]";
  if (scorePct >= 55) return "text-[var(--warning)] border-[var(--warning)]/25 bg-[var(--warning-muted)]";
  return "text-[var(--text-muted)] border-[var(--border)] bg-[var(--surface-hover)]";
}

/** Score is 0–1 from the API; display as percentage. */
export function MatchScore({
  score,
  className,
  showLabel = true,
}: {
  score: number;
  className?: string;
  showLabel?: boolean;
}) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-md border px-2.5 py-1",
        fitTone(pct),
        className,
      )}
      title="Match score is an estimate based on your Hunt Rules — not a verified guarantee"
    >
      <span className="text-sm font-semibold tabular-nums">{pct}%</span>
      {showLabel ? <span className="text-[11px] font-medium tracking-wide uppercase">{fitLabel(pct)}</span> : null}
    </div>
  );
}

export function MatchScoreBar({ score, className }: { score: number; className?: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  return (
    <div className={cn("w-full", className)}>
      <div className="mb-1 flex items-center justify-between text-xs text-[var(--text-muted)]">
        <span>Match estimate</span>
        <span className="tabular-nums text-[var(--text-secondary)]">{pct}% · {fitLabel(pct)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
