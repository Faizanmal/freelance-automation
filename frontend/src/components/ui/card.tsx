import * as React from "react"
import { motion, HTMLMotionProps } from "framer-motion"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const Card = React.forwardRef<HTMLDivElement, HTMLMotionProps<"div">>(
  ({ className, ...props }, ref) => (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={cn(
        "rounded-2xl border border-white/10 bg-black/40 backdrop-blur-xl",
        "shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-colors hover:border-white/20",
        className
      )}
      {...props}
    />
  )
)
Card.displayName = "Card"

export { Card }
