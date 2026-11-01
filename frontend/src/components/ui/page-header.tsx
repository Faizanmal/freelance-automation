import { cn } from "@/lib/cn";

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="min-w-0 max-w-2xl">
        {eyebrow ? (
          <p className="mb-1 text-xs font-semibold tracking-[0.2em] text-[var(--accent)] uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1
          className="text-3xl tracking-tight text-[var(--text)] md:text-4xl"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          {title}
        </h1>
        {description ? <p className="mt-2 text-[var(--text-secondary)]">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
