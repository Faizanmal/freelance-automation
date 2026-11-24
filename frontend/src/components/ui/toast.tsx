"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

type ToastTone = "default" | "success" | "error";

export type ToastChip = {
  id: string;
  label: string;
  onSelect: () => void;
};

type ToastItem = {
  id: string;
  message: string;
  tone: ToastTone;
  actionLabel?: string;
  onAction?: () => void;
  chips?: ToastChip[];
  chipsLabel?: string;
};

type ToastOptions = {
  tone?: ToastTone;
  actionLabel?: string;
  onAction?: () => void;
  durationMs?: number;
  chips?: ToastChip[];
  chipsLabel?: string;
};

type ToastContextValue = {
  toast: (message: string, options?: ToastTone | ToastOptions) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, options?: ToastTone | ToastOptions) => {
      const opts: ToastOptions =
        typeof options === "string" || options === undefined
          ? { tone: options || "default" }
          : options;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setItems((current) => [
        ...current.slice(-3),
        {
          id,
          message,
          tone: opts.tone || "default",
          actionLabel: opts.actionLabel,
          onAction: opts.onAction,
          chips: opts.chips,
          chipsLabel: opts.chipsLabel,
        },
      ]);
      const holdMs = opts.chips?.length
        ? Math.max(opts.durationMs ?? 8000, 10000)
        : opts.durationMs ?? (opts.onAction ? 6000 : 3200);
      window.setTimeout(() => dismiss(id), holdMs);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-[80] flex w-full max-w-sm flex-col gap-2">
        <AnimatePresence>
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8 }}
              className={cn(
                "pointer-events-auto flex flex-col gap-2 rounded-[var(--radius)] border px-4 py-3 shadow-[var(--shadow-md)]",
                item.tone === "success" &&
                  "border-[var(--success)]/30 bg-[var(--surface)] text-[var(--success)]",
                item.tone === "error" &&
                  "border-[var(--danger)]/30 bg-[var(--surface)] text-[var(--danger)]",
                item.tone === "default" &&
                  "border-[var(--border)] bg-[var(--surface)] text-[var(--text)]",
              )}
              role="status"
            >
              <div className="flex items-start gap-3">
                <p className="flex-1 text-sm text-[var(--text)]">{item.message}</p>
                {item.actionLabel && item.onAction ? (
                  <button
                    type="button"
                    data-testid="toast-undo"
                    className="shrink-0 rounded-md border border-[var(--accent)]/40 bg-[var(--accent-muted)] px-2.5 py-1 text-sm font-semibold text-[var(--accent)] hover:border-[var(--accent)]"
                    onClick={() => {
                      item.onAction?.();
                      dismiss(item.id);
                    }}
                  >
                    {item.actionLabel}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="rounded p-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
                  onClick={() => dismiss(item.id)}
                  aria-label="Dismiss"
                >
                  <X className="size-4" />
                </button>
              </div>
              {item.chips && item.chips.length > 0 ? (
                <div className="border-t border-[var(--border)] pt-2">
                  <p className="mb-1.5 text-[11px] font-semibold tracking-wide text-[var(--text-secondary)] uppercase">
                    {item.chipsLabel || "Why?"}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {item.chips.map((chip) => (
                      <button
                        key={chip.id}
                        type="button"
                        data-testid={`toast-chip-${chip.id}`}
                        className="rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-2.5 py-1 text-xs font-semibold text-[var(--text)] hover:border-[var(--accent)] hover:bg-[var(--accent-muted)] hover:text-[var(--accent)]"
                        onClick={() => {
                          chip.onSelect();
                          dismiss(item.id);
                        }}
                      >
                        {chip.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      toast: (message: string) => {
        if (typeof window !== "undefined") {
          console.info(message);
        }
      },
    };
  }
  return ctx;
}
