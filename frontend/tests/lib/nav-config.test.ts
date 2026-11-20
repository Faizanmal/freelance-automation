import { describe, expect, it } from "vitest";
import { AUTH_NAV, filterNavForUser } from "@/components/nav-config";

describe("filterNavForUser", () => {
  it("hides marketplace unless feature flag is on", () => {
    const items = filterNavForUser(AUTH_NAV, { account_role: "freelancer" });
    expect(items.some((i) => i.href === "/marketplace")).toBe(false);
  });

  it("shows admin for superuser", () => {
    const items = filterNavForUser(AUTH_NAV, {
      account_role: "freelancer",
      is_superuser: true,
    });
    expect(items.some((i) => i.href === "/admin")).toBe(true);
  });

  it("hides admin for regular freelancer", () => {
    const items = filterNavForUser(AUTH_NAV, { account_role: "freelancer" });
    expect(items.some((i) => i.href === "/admin")).toBe(false);
  });
});
