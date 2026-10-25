import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import { ThemeProvider } from "@/components/theme-provider";
import { CookieConsent, Analytics, ClientErrorReporter } from "@/components/cookie-consent";
import { OnboardingWizard } from "@/components/onboarding-wizard";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

// Self-hosted: next/font/google intermittently fails CI when Google returns
// extensionless /l/font?kit=… URLs (vercel/next.js#99114).
const display = localFont({
  src: "./fonts/Fraunces-latin.woff2",
  variable: "--font-display",
  weight: "500 700",
  display: "swap",
});

const body = localFont({
  src: "./fonts/Manrope-latin.woff2",
  variable: "--font-body",
  weight: "400 700",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Signal Desk — Freelance Intelligence",
  description:
    "Set Hunt Rules. We find public freelance and contract posts outside marketplaces — ranked leads and a short digest.",
  openGraph: {
    title: "Signal Desk — Freelance Intelligence",
    description:
      "Set Hunt Rules. We find public freelance and contract posts outside marketplaces — ranked leads and a short digest.",
    url: "https://signaldesk.com",
    siteName: "Signal Desk",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Signal Desk — Freelance Intelligence",
    description:
      "Set Hunt Rules. We find public freelance and contract posts outside marketplaces — ranked leads and a short digest.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full">
        <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem>
          <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16 pt-6 md:px-8">
            <SiteHeader />
            <main className="flex-grow">{children}</main>
            <footer className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-[var(--mute)]/20 pt-8 text-sm text-[var(--mute)]">
              <p>&copy; 2026 Signal Desk. All rights reserved.</p>
              <div className="flex flex-wrap gap-4">
                <Link href="/jobs" className="hover:text-[var(--signal)]">
                  Jobs
                </Link>
                <Link href="/notifications" className="hover:text-[var(--signal)]">
                  Alerts
                </Link>
                <Link href="/roadmap" className="hover:text-[var(--signal)]">
                  Roadmap
                </Link>
                <Link href="/help" className="hover:text-[var(--signal)]">
                  Help
                </Link>
                <Link href="/terms" className="hover:text-[var(--signal)]">
                  Terms
                </Link>
                <Link href="/privacy" className="hover:text-[var(--signal)]">
                  Privacy
                </Link>
                <a href="mailto:support@signaldesk.com" className="hover:text-[var(--signal)]">
                  Support
                </a>
              </div>
            </footer>
          </div>
          <CookieConsent />
          <Analytics />
          <ClientErrorReporter />
          <OnboardingWizard />
        </ThemeProvider>
      </body>
    </html>
  );
}
