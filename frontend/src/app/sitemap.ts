import type { MetadataRoute } from "next";
import { getSiteUrl, shouldIndexSite } from "@/lib/site-url";

/** Public routes only — never private desk data or empty thin auth states. */
export default function sitemap(): MetadataRoute.Sitemap {
  if (!shouldIndexSite()) return [];
  const siteUrl = getSiteUrl();
  const paths = [
    "/",
    "/pricing",
    "/help",
    "/privacy",
    "/terms",
    "/freelance-jobs",
  ];
  return paths.map((path) => ({
    url: `${siteUrl.replace(/\/$/, "")}${path}`,
    changeFrequency: path === "/" ? "daily" : "weekly",
    priority: path === "/" ? 1 : 0.6,
  }));
}
