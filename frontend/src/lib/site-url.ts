/** Resolve canonical origin from the deployment, never a guessed brand domain. */
export function getSiteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_APP_URL?.trim().replace(/\/+$/, "");
  if (configured) return configured;
  if (process.env.VERCEL_ENV === "production" && process.env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
  }
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://localhost:3000";
}

export function shouldIndexSite(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_APP_URL?.trim()) && process.env.VERCEL_ENV === "production";
}
