import type { MetadataRoute } from "next";

const siteUrl = process.env.NEXT_PUBLIC_APP_URL || "https://signaldesk.com";

/** Public routes only — never private desk data or empty thin auth states. */
export default function sitemap(): MetadataRoute.Sitemap {
  const paths = [
    "/",
    "/pricing",
    "/help",
    "/privacy",
    "/terms",
    "/status",
    "/freelance-jobs",
    "/auth",
  ];
  const now = new Date();
  return paths.map((path) => ({
    url: `${siteUrl.replace(/\/$/, "")}${path}`,
    lastModified: now,
    changeFrequency: path === "/" ? "daily" : "weekly",
    priority: path === "/" ? 1 : 0.6,
  }));
}
