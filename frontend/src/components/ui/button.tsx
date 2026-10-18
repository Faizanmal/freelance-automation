import * as React from "react"
import { motion, HTMLMotionProps } from "framer-motion"
import { cn } from "./card" // Reusing cn utility

interface ButtonProps extends HTMLMotionProps<"button"> {
  variant?: "default" | "outline" | "ghost" | "destructive";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => {
    
    const variants = {
      default: "bg-[var(--signal)] text-[var(--ink)] shadow-[0_0_20px_rgba(198,242,92,0.3)] hover:shadow-[0_0_30px_rgba(198,242,92,0.5)]",
      outline: "border border-white/20 bg-transparent text-[var(--paper)] hover:border-[var(--signal)]/50 hover:bg-white/5",
      ghost: "bg-transparent text-[var(--mute)] hover:text-[var(--paper)] hover:bg-white/5",
      destructive: "bg-red-950 text-red-200 hover:bg-red-900",
    }

    return (
      <motion.button
        ref={ref}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={cn(
          "inline-flex items-center justify-center rounded-full px-5 py-2.5 font-semibold transition-all disabled:opacity-50 disabled:pointer-events-none",
          variants[variant],
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
