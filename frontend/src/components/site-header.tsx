"use client";

import { PUBLIC_NAV } from "@/components/nav-config";
import { SiteHeaderInner } from "@/components/app-shell";

/** Logged-out marketing header (layout tests and legacy imports). */
export function SiteHeader() {
  return <SiteHeaderInner nav={PUBLIC_NAV} />;
}
