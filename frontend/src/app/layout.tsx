import type { Metadata } from "next";
import { Fraunces, Manrope } from "next/font/google";
import Link from "next/link";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { CookieConsent } from "@/components/cookie-consent";
import "./globals.css";const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const body = Manrope({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Signal Desk — Freelance Intelligence",
  description: "Live freelance and remote jobs matched to your preferences.",
  openGraph: {
    title: "Signal Desk — Freelance Intelligence",
    description: "Live freelance and remote jobs matched to your preferences.",
    url: "https://signaldesk.com",
    siteName: "Signal Desk",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Signal Desk — Freelance Intelligence",
    description: "Live freelance and remote jobs matched to your preferences.",
  },
};

const nav = [
  { href: "/", label: "Desk" },
  { href: "/pricing", label: "Pricing" },
  { href: "/jobs", label: "Jobs" },
  { href: "/findings", label: "Findings" },
  { href: "/matches", label: "Matches" },
  { href: "/sources", label: "Sources" },
  { href: "/preferences", label: "Prefs" },
  { href: "/notifications", label: "Alerts" },
  { href: "/auth", label: "Account" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full">
        <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem>
          <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16 pt-6 md:px-8">
            <header className="mb-10 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--mute)]/20 pb-5">
              <div>
                <p className="text-sm tracking-[0.28em] text-[var(--signal)] uppercase">Signal Desk</p>
                <p className="mt-1 text-sm text-[var(--mute)]">Freelance intelligence that actually pulls live jobs</p>
              </div>
              <div className="flex flex-col items-end gap-4">
                <div className="flex items-center gap-4">
                  <ThemeToggle />
                </div>
                <nav className="flex flex-wrap gap-2 text-sm justify-end">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-full border border-[var(--mute)]/30 px-3 py-1.5 text-[var(--fog)] transition hover:border-[var(--signal)]/50 hover:text-[var(--signal)]"
                >
                  {item.label}
                </Link>
              ))}
                </nav>
              </div>
            </header>
            <main className="flex-grow">
              {children}
            </main>
            <footer className="mt-16 border-t border-[var(--mute)]/20 pt-8 flex flex-wrap items-center justify-between gap-4 text-sm text-[var(--mute)]">
              <p>&copy; {new Date().getFullYear()} Signal Desk. All rights reserved.</p>
              <div className="flex gap-4">
                <Link href="/terms" className="hover:text-[var(--signal)]">Terms</Link>
                <Link href="/privacy" className="hover:text-[var(--signal)]">Privacy</Link>
                <a href="mailto:support@signaldesk.com" className="hover:text-[var(--signal)]">Support</a>
              </div>
            </footer>
          </div>
          <CookieConsent />
          {/* Web Analytics */}
          <script defer data-domain="signaldesk.com" src="https://plausible.io/js/script.js"></script>
        </ThemeProvider>
      </body>
    </html>
  );
}
