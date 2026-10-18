"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import {
  getAuthServerSnapshot,
  getAuthSnapshot,
  subscribeAuth,
} from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";

type NavItem = { href: string; label: string };

const PUBLIC_NAV: NavItem[] = [
  { href: "/", label: "Desk" },
  { href: "/pricing", label: "Pricing" },
  { href: "/leads", label: "Leads" },
  { href: "/auth", label: "Account" },
];

const AUTH_NAV: NavItem[] = [
  { href: "/", label: "Desk" },
  { href: "/leads", label: "Leads" },
  { href: "/preferences", label: "Hunt Rules" },
  { href: "/auth", label: "Account" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader() {
  const pathname = usePathname() || "/";
  // Defer auth-dependent chrome until after hydrate so localStorage tokens
  // do not mismatch the server snapshot (always unauthenticated on SSR).
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const authedRaw = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthServerSnapshot);
  const authed = mounted && authedRaw;
  // Track which path the menu was opened on so navigation closes it without an effect.
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const menuOpen = menuPath === pathname;

  const nav = authed ? AUTH_NAV : PUBLIC_NAV;

  const linkClass = (href: string) => {
    const active = isActive(pathname, href);
    return [
      "rounded-full px-3 py-1.5 text-sm transition",
      active
        ? "border border-[var(--signal)]/60 text-[var(--signal)] bg-[var(--signal)]/10"
        : "border border-[var(--mute)]/30 text-[var(--fog)] hover:border-[var(--signal)]/50 hover:text-[var(--signal)]",
    ].join(" ");
  };

  return (
    <header className="mb-10 border-b border-[var(--mute)]/20 pb-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/" className="text-sm tracking-[0.28em] text-[var(--signal)] uppercase">
            Signal Desk
          </Link>
          <p className="mt-1 text-sm text-[var(--mute)]">
            {authed
              ? "Your desk — hunt public work, rank fit, open the original"
              : "Find freelance fit outside marketplace bid wars"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-full border border-[var(--mute)]/30 px-3 py-1.5 text-sm text-[var(--fog)] md:hidden"
            aria-expanded={menuOpen}
            aria-controls="site-primary-nav"
            onClick={() => setMenuPath(menuOpen ? null : pathname)}
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
          <nav className="hidden flex-wrap justify-end gap-2 md:flex" aria-label="Primary">
            {nav.map((item) => (
              <Link key={item.href} href={item.href} className={linkClass(item.href)}>
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
      {menuOpen ? (
        <nav
          id="site-primary-nav"
          className="mt-4 flex flex-col gap-2 md:hidden"
          aria-label="Primary"
        >
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={linkClass(item.href)}
              onClick={() => setMenuPath(null)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      ) : null}
    </header>
  );
}
