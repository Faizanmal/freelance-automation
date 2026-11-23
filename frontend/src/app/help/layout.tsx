import { publicPageMetadata } from "@/lib/public-metadata";

export const metadata = publicPageMetadata(
  "Help and how it works",
  "Learn how to set Hunt Rules, review freelance leads, and manage alerts in Signal Desk.",
  "/help",
);

export default function HelpLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
