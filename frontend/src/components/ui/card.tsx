import * as React from "react";
import { cn } from "@/lib/cn";

export { cn } from "@/lib/cn";

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  interactive?: boolean;
};

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, interactive = false, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)]",
        interactive &&
          "transition-[border-color,transform] duration-150 hover:-translate-y-0.5 hover:border-[var(--border-strong)] motion-reduce:hover:translate-y-0",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export { Card };
