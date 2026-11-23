import type { NextConfig } from "next";

const apiOrigin = process.env.NEXT_PUBLIC_API_URL
  ? new URL(process.env.NEXT_PUBLIC_API_URL).origin
  : null;
const connectSources = [
  "'self'",
  apiOrigin,
  "https://plausible.io",
  ...(process.env.NODE_ENV === "development"
    ? ["http://127.0.0.1:8000", "http://localhost:8000"]
    : []),
].filter((source): source is string => Boolean(source));

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Next 16.3 + Vercel adapter skips next-server.js.nft.json; standalone still
  // reads it → ENOENT. Keep standalone for Docker; omit on Vercel (VERCEL=1).
  // https://github.com/vercel/next.js/issues/96646
  output: process.env.VERCEL ? undefined : "standalone",
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 31536000,
  },
  async redirects() {
    return [
      { source: "/findings", destination: "/leads", permanent: true },
      { source: "/matches", destination: "/leads", permanent: true },
      { source: "/matches/:path*", destination: "/leads", permanent: true },
    ];
  },
  async headers() {
    const security = [
      { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      {
        key: "Content-Security-Policy",
        value: [
          "default-src 'self'",
          `script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""} https://plausible.io`,
          "style-src 'self' 'unsafe-inline'",
          "img-src 'self' data: blob: https:",
          "font-src 'self' data:",
          `connect-src ${connectSources.join(" ")}`,
          "frame-ancestors 'none'",
          "base-uri 'self'",
          "form-action 'self'",
        ].join("; "),
      },
    ];
    return [
      {
        source: "/:path*",
        headers: security,
      },
      ...[
        "/admin/:path*", "/auth/:path*", "/privacy/center/:path*", "/preferences/:path*",
        "/pipeline/:path*", "/leads/:path*", "/jobs/:path*", "/notifications/:path*",
        "/sources/:path*", "/finance/:path*", "/ops/:path*", "/employer/:path*",
        "/talent/:path*", "/projects/:path*", "/waitlist/:path*", "/design-system/:path*",
        "/health/:path*", "/status/:path*", "/cancel-feedback/:path*", "/roadmap/:path*",
      ].map((source) => ({
        source,
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" }],
      })),
      {
        source: "/_next/image(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        source: "/_next/static/(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
