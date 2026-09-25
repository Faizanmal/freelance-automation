"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  const mounted = React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  if (!mounted) {
    return (
      <button className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--mute)]/30 text-[var(--fog)] opacity-50">
        <span className="sr-only">Toggle theme</span>
      </button>
    );
  }

  const isLight = resolvedTheme === "light";

  return (
    <button
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--mute)]/30 p-2 text-[var(--fog)] transition hover:border-[var(--signal)]/50 hover:text-[var(--signal)]"
      aria-label="Toggle theme"
    >
      {isLight ? (
        <Moon className="h-4 w-4" />
      ) : (
        <Sun className="h-4 w-4" />
      )}
    </button>
  );
}
