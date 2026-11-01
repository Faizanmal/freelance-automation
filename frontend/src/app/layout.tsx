import type { Metadata } from "next";
import localFont from "next/font/local";
import { ThemeProvider } from "@/components/theme-provider";
import { CookieConsent, Analytics, ClientErrorReporter } from "@/components/cookie-consent";
import { OnboardingWizard } from "@/components/onboarding-wizard";
import { AppShell } from "@/components/app-shell";
import { ToastProvider } from "@/components/ui/toast";
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
          <ToastProvider>
            <AppShell>
              <main className="flex flex-1 flex-col">{children}</main>
            </AppShell>
            <CookieConsent />
            <Analytics />
            <ClientErrorReporter />
            <OnboardingWizard />
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
