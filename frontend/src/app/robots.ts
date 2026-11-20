import type { MetadataRoute } from "next";

const siteUrl = process.env.NEXT_PUBLIC_APP_URL || "https://signaldesk.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/pricing", "/help", "/privacy", "/terms", "/status", "/freelance-jobs", "/auth"],
        disallow: [
          "/admin",
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
