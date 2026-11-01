import * as React from "react";
import { cn } from "@/lib/cn";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "destructive" | "secondary";
  size?: "default" | "sm" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", type = "button", ...props }, ref) => {
    const variants = {
      default:
        "bg-[var(--accent)] text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)] shadow-[var(--shadow-sm)]",
      secondary:
        "bg-[var(--surface-hover)] text-[var(--text)] border border-[var(--border)] hover:border-[var(--border-strong)]",
      outline:
        "border border-[var(--border)] bg-transparent text-[var(--text)] hover:bg-[var(--surface-hover)] hover:border-[var(--border-strong)]",
      ghost: "bg-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]",
      destructive: "bg-[var(--danger-muted)] text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white",
    };

    const sizes = {
      default: "h-10 px-4 py-2 text-sm",
      sm: "h-8 px-3 text-xs",
      lg: "h-11 px-5 text-sm",
      icon: "h-9 w-9 p-0",
    };

    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-[var(--radius)] font-semibold transition-[color,background-color,border-color,transform,opacity] duration-150",
          "hover:scale-[1.01] active:scale-[0.98]",
          "motion-reduce:hover:scale-100 motion-reduce:active:scale-100",
          "disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button };
