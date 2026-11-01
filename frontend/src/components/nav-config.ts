export type NavItem = {
  href: string;
  label: string;
  icon?: "desk" | "leads" | "rules" | "saved" | "billing" | "account" | "help" | "pricing";
  section?: "workspace" | "management" | "account" | "public";
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
  { href: "/preferences", label: "Hunt Rules", icon: "rules", section: "workspace" },
  { href: "/leads?filter=saved", label: "Saved Opportunities", icon: "saved", section: "management" },
  { href: "/pricing", label: "Billing", icon: "billing", section: "account" },
  { href: "/auth", label: "Account", icon: "account", section: "account" },
];

export function isActivePath(pathname: string, href: string) {
  const pathOnly = href.split("?")[0];
  if (pathOnly === "/") return pathname === "/";
  return pathname === pathOnly || pathname.startsWith(`${pathOnly}/`);
}
