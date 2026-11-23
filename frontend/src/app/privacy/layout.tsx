import { publicPageMetadata } from "@/lib/public-metadata";

export const metadata = publicPageMetadata(
  "Privacy policy",
  "How Signal Desk handles account information, source data, analytics consent, and deletion requests.",
  "/privacy",
);

export default function PrivacyLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
