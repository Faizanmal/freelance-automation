import { publicPageMetadata } from "@/lib/public-metadata";

export const metadata = publicPageMetadata(
  "Terms of service",
  "Service scope, account responsibilities, subscriptions, and usage terms for Signal Desk.",
  "/terms",
);

export default function TermsLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
