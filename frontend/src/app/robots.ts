import type { MetadataRoute } from "next";
import { getSiteUrl, shouldIndexSite } from "@/lib/site-url";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl();
  if (!shouldIndexSite()) {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/pricing", "/help", "/privacy", "/terms", "/freelance-jobs"],
        disallow: [
          "/admin",
          "/pipeline",
          "/finance",
          "/jobs",
          "/projects",
          "/employer",
          "/talent",
          "/ops",
          "/waitlist",
          "/health",
          "/status",
          "/cancel-feedback",
          "/roadmap",
          "/preferences",
          "/notifications",
          "/privacy/center",
          "/leads",
          "/findings",
          "/matches",
          "/sources",
          "/design-system",
          "/api/",
        ],
      },
    ],
    sitemap: `${siteUrl.replace(/\/$/, "")}/sitemap.xml`,
  };
}
