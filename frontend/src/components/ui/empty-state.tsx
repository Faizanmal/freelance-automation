import Link from "next/link";
import { cn } from "@/lib/cn";

export function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
  secondaryHref,
  secondaryLabel,
  className,
  icon,
}: {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
  className?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-start rounded-[var(--radius)] border border-dashed border-[var(--border)] bg-[var(--bg-elevated)]/60 px-6 py-10",
        className,
      )}
    >
      {icon ? <div className="mb-4 text-[var(--accent)]">{icon}</div> : null}
      <h3
        className="text-xl text-[var(--text)]"
        style={{ fontFamily: "var(--font-display), Georgia, serif" }}
      >
        {title}
      </h3>
      <p className="mt-2 max-w-lg text-sm text-[var(--text-muted)]">{description}</p>
      {(actionHref && actionLabel) || (secondaryHref && secondaryLabel) ? (
        <div className="mt-5 flex flex-wrap gap-3">
          {actionHref && actionLabel ? (
            <Link
              href={actionHref}
              className="inline-flex h-10 items-center rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)]"
            >
              {actionLabel}
            </Link>
          ) : null}
          {secondaryHref && secondaryLabel ? (
            <Link
              href={secondaryHref}
              className="inline-flex h-10 items-center rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
            >
              {secondaryLabel}
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
