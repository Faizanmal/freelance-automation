export type NavItem = {
  href: string;
  label: string;
  icon?: "desk" | "leads" | "pipeline" | "rules" | "saved" | "billing" | "account" | "help" | "pricing" | "alerts" | "admin";
  section?: "workspace" | "management" | "account" | "public";
  /** When set, item only shows for matching account roles or superusers. */
  roles?: Array<"freelancer" | "client" | "staff" | "superuser">;
  /** Feature flag — hide until native marketplace is enabled. */
  featureFlag?: "native_marketplace";
};

/** Public marketing / logged-out chrome — labels locked by layout tests. */
export const PUBLIC_NAV: NavItem[] = [
  { href: "/", label: "Desk", icon: "desk", section: "public" },
  { href: "/leads", label: "Leads", icon: "leads", section: "public" },
  { href: "/pricing", label: "Pricing", icon: "pricing", section: "public" },
  { href: "/help", label: "Help", icon: "help", section: "public" },
  { href: "/auth", label: "Account", icon: "account", section: "public" },
];

/**
 * Authenticated product nav.
 * Uses "Billing" (not "Pricing") so auth layout tests pass while still linking to /pricing.
 * Sources / Findings / Matches stay off the main nav by design.
 */
export const AUTH_NAV: NavItem[] = [
  { href: "/", label: "Desk", icon: "desk", section: "workspace" },
  { href: "/leads", label: "Leads", icon: "leads", section: "workspace" },
  { href: "/pipeline", label: "Pipeline", icon: "pipeline", section: "workspace" },
  { href: "/finance", label: "Financials", icon: "billing", section: "workspace" },
  { href: "/preferences", label: "Hunt Rules", icon: "rules", section: "workspace" },
  { href: "/notifications", label: "Alerts", icon: "alerts", section: "workspace" },
  { href: "/talent", label: "Talent Directory", icon: "leads", section: "workspace" },
  { href: "/talent/profile", label: "Talent Profile", icon: "account", section: "workspace" },
  { href: "/leads?filter=saved", label: "Saved Opportunities", icon: "saved", section: "management" },
  { href: "/employer/settings", label: "Employer Workspace", icon: "account", section: "management" },
  { href: "/employer/projects", label: "Client Projects", icon: "pipeline", section: "management" },
  {
    href: "/marketplace",
    label: "Marketplace",
    icon: "leads",
    section: "management",
    featureFlag: "native_marketplace",
  },
  { href: "/pricing", label: "Billing", icon: "billing", section: "account" },
  { href: "/auth", label: "Account", icon: "account", section: "account" },
  {
    href: "/admin",
    label: "Admin",
    icon: "admin",
    section: "account",
    roles: ["superuser", "staff"],
  },
];

export const NATIVE_MARKETPLACE_ENABLED =
  process.env.NEXT_PUBLIC_NATIVE_MARKETPLACE === "true";

export function isActivePath(pathname: string, href: string) {
  const pathOnly = href.split("?")[0];
  if (pathOnly === "/") return pathname === "/";
  return pathname === pathOnly || pathname.startsWith(`${pathOnly}/`);
}

export function filterNavForUser(
  items: NavItem[],
  user: { account_role?: string | null; is_superuser?: boolean } | null,
): NavItem[] {
  return items.filter((item) => {
    if (item.featureFlag === "native_marketplace" && !NATIVE_MARKETPLACE_ENABLED) {
      return false;
    }
    if (!item.roles?.length) return true;
    if (user?.is_superuser) return true;
    const role = (user?.account_role || "freelancer").toLowerCase();
    return item.roles.some((r) => r === role || (r === "superuser" && user?.is_superuser));
  });
}
