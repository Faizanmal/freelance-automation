import { cn } from "@/lib/cn";

type BadgeVariant = "default" | "accent" | "success" | "warning" | "danger" | "muted" | "outline";

export function Badge({
  children,
  className,
  variant = "default",
  ...props
}: {
  children: React.ReactNode;
  className?: string;
  variant?: BadgeVariant;
} & React.HTMLAttributes<HTMLSpanElement>) {
  const variants: Record<BadgeVariant, string> = {
    default: "bg-[var(--surface-hover)] text-[var(--text-secondary)] border-[var(--border)]",
    accent: "bg-[var(--accent-muted)] text-[var(--accent)] border-transparent",
    success: "bg-[var(--success-muted)] text-[var(--success)] border-transparent",
    warning: "bg-[var(--warning-muted)] text-[var(--warning)] border-transparent",
    danger: "bg-[var(--danger-muted)] text-[var(--danger)] border-transparent",
    muted: "bg-transparent text-[var(--text-muted)] border-[var(--border)]",
    outline: "bg-transparent text-[var(--text-secondary)] border-[var(--border)]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase",
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
