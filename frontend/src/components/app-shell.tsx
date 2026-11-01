"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import {
  Bookmark,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  LayoutDashboard,
  Menu,
  Radar,
  Settings,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import {
  getAuthServerSnapshot,
  getAuthSnapshot,
  me,
  subscribeAuth,
  type User,
} from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";
import { AUTH_NAV, PUBLIC_NAV, isActivePath, type NavItem } from "@/components/nav-config";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

const COLLAPSE_KEY = "signaldesk_sidebar_collapsed";

function NavIcon({ name, className }: { name?: NavItem["icon"]; className?: string }) {
  const props = { className: cn("size-4 shrink-0", className) };
  switch (name) {
    case "desk":
      return <LayoutDashboard {...props} />;
    case "leads":
      return <Sparkles {...props} />;
    case "rules":
      return <Target {...props} />;
    case "saved":
      return <Bookmark {...props} />;
    case "billing":
    case "pricing":
      return <CreditCard {...props} />;
    case "account":
      return <Settings {...props} />;
    case "help":
      return <Radar {...props} />;
    default:
      return <LayoutDashboard {...props} />;
  }
}

function sectionLabel(section: NavItem["section"]) {
  if (section === "workspace") return "Workspace";
  if (section === "management") return "Management";
  if (section === "account") return "Account";
  return null;
}

function MarketingHeader({ nav }: { nav: NavItem[] }) {
  const pathname = usePathname() || "/";
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const menuOpen = menuPath === pathname;

  const linkClass = (href: string) => {
    const active = isActivePath(pathname, href);
    return cn(
      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
      active
        ? "bg-[var(--accent-muted)] text-[var(--accent)]"
        : "text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]",
    );
  };

  return (
    <header className="mb-8 border-b border-[var(--border)] pb-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/" className="text-sm font-semibold tracking-[0.22em] text-[var(--accent)] uppercase">
            Signal Desk
          </Link>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Find freelance fit outside marketplace bid wars
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] md:hidden"
            aria-expanded={menuOpen}
            aria-controls="site-primary-nav"
            onClick={() => setMenuPath(menuOpen ? null : pathname)}
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
          <nav className="hidden flex-wrap justify-end gap-1 md:flex" aria-label="Primary">
            {nav.map((item) => (
              <Link key={item.href} href={item.href} className={linkClass(item.href)}>
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
      {menuOpen ? (
        <nav id="site-primary-nav" className="mt-4 flex flex-col gap-1 md:hidden" aria-label="Primary">
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

function SiteFooter({ authed }: { authed: boolean }) {
  return (
    <footer className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-[var(--border)] pt-6 text-sm text-[var(--text-muted)]">
      <p>&copy; 2026 Signal Desk. All rights reserved.</p>
      <div className="flex flex-wrap gap-4">
        <Link href="/" className="hover:text-[var(--accent)]">
          Desk
        </Link>
        <Link href="/leads" className="hover:text-[var(--accent)]">
          Leads
        </Link>
        <Link href="/preferences" className="hover:text-[var(--accent)]">
          Hunt Rules
        </Link>
        {authed ? (
          <Link href="/pricing" className="hover:text-[var(--accent)]">
            Billing
          </Link>
        ) : (
          <Link href="/pricing" className="hover:text-[var(--accent)]">
            Pricing
          </Link>
        )}
        <Link href="/help" className="hover:text-[var(--accent)]">
          Help
        </Link>
        <Link href="/terms" className="hover:text-[var(--accent)]">
          Terms
        </Link>
        <Link href="/privacy" className="hover:text-[var(--accent)]">
          Privacy
        </Link>
        <a href="mailto:support@signaldesk.com" className="hover:text-[var(--accent)]">
          Support
        </a>
      </div>
    </footer>
  );
}

function SidebarNav({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname() || "/";
  const sections: Array<NavItem["section"]> = ["workspace", "management", "account"];

  return (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Primary">
      {sections.map((section) => {
        const items = AUTH_NAV.filter((item) => item.section === section);
        const label = sectionLabel(section);
        return (
          <div key={section}>
            {label && !collapsed ? (
              <p className="mb-2 px-2 text-[10px] font-semibold tracking-[0.18em] text-[var(--text-muted)] uppercase">
                {label}
              </p>
            ) : null}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = isActivePath(pathname, item.href);
                return (
                  <li key={`${item.href}-${item.label}`}>
                    <Link
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      onClick={onNavigate}
                      className={cn(
                        "group flex items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                          : "text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]",
                        collapsed && "justify-center px-0",
                      )}
                    >
                      <NavIcon name={item.icon} />
                      {!collapsed ? <span className="truncate">{item.label}</span> : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function UserChip({ user, collapsed }: { user: User | null; collapsed: boolean }) {
  const initial = (user?.full_name || user?.email || "?").slice(0, 1).toUpperCase();
  const plan = (user?.plan || "free").toLowerCase();
  const isPro = plan === "pro";

  return (
    <Link
      href="/auth"
      className={cn(
        "mx-3 mb-3 flex items-center gap-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] p-2.5 transition-colors hover:border-[var(--border-strong)]",
        collapsed && "justify-center px-2",
      )}
      title={collapsed ? user?.email || "Account" : undefined}
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--accent-muted)] text-sm font-semibold text-[var(--accent)]">
        {initial}
      </span>
      {!collapsed ? (
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-[var(--text)]">
            {user?.full_name || user?.email || "Account"}
          </span>
          <span className="mt-0.5 flex items-center gap-1.5">
            <Badge variant={isPro ? "accent" : "muted"}>{isPro ? "Pro" : "Free"}</Badge>
          </span>
        </span>
      ) : null}
    </Link>
  );
}

function ProductShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    me()
      .then((current) => {
        if (!cancelled) setUser(current);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  };

  const pageTitle =
    AUTH_NAV.find((item) => isActivePath(pathname, item.href))?.label ||
    (pathname.startsWith("/help") ? "Help" : "Signal Desk");

  return (
    <div className="flex min-h-screen w-full">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] transition-[width] duration-200 md:flex",
          collapsed ? "w-[var(--sidebar-collapsed)]" : "w-[var(--sidebar-width)]",
        )}
      >
        <div
          className={cn(
            "flex h-[var(--header-height)] items-center border-b border-[var(--border)] px-3",
            collapsed ? "justify-center" : "justify-between gap-2",
          )}
        >
          {!collapsed ? (
            <Link href="/" className="truncate text-sm font-semibold tracking-[0.18em] text-[var(--accent)] uppercase">
              Signal Desk
            </Link>
          ) : (
            <Link href="/" aria-label="Signal Desk" className="text-[var(--accent)]">
              <Radar className="size-5" />
            </Link>
          )}
          <button
            type="button"
            onClick={toggleCollapsed}
            className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
          </button>
        </div>
        <SidebarNav collapsed={collapsed} />
        <UserChip user={user} collapsed={collapsed} />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-[min(18rem,88vw)] flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-md)]">
            <div className="flex h-[var(--header-height)] items-center justify-between border-b border-[var(--border)] px-4">
              <Link href="/" className="text-sm font-semibold tracking-[0.18em] text-[var(--accent)] uppercase">
                Signal Desk
              </Link>
              <button
                type="button"
                className="rounded-md p-1.5 text-[var(--text-muted)]"
                onClick={() => setMobileOpen(false)}
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
            <SidebarNav collapsed={false} onNavigate={() => setMobileOpen(false)} />
            <UserChip user={user} collapsed={false} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-[var(--header-height)] items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--bg)]/90 px-4 backdrop-blur-md md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-md border border-[var(--border)] p-2 text-[var(--text-secondary)] md:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="size-4" />
            </button>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[var(--text)]">{pageTitle}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/auth"
              className="hidden rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] sm:inline-flex"
            >
              Account
            </Link>
          </div>
        </header>
        <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 md:px-6 md:py-8">
          <div className="flex-1">{children}</div>
          <SiteFooter authed />
        </div>
      </div>
    </div>
  );
}

/**
 * Auth-aware application chrome.
 * Logged out: marketing header + centered column.
 * Logged in: collapsible sidebar product shell.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const authedRaw = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthServerSnapshot);
  const authed = mounted && authedRaw;

  if (authed) {
    return <ProductShell>{children}</ProductShell>;
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16 pt-6 md:px-8">
      <MarketingHeader nav={PUBLIC_NAV} />
      <div className="flex-1">{children}</div>
      <SiteFooter authed={false} />
    </div>
  );
}

/** Kept for tests and any direct imports — thin re-export of marketing chrome when logged out. */
export { MarketingHeader as SiteHeaderInner };
