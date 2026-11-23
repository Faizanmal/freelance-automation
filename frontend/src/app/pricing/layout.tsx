import { publicPageMetadata } from "@/lib/public-metadata";

export const metadata = publicPageMetadata(
  "Pricing",
  "Compare Signal Desk plans, current limits, and available checkout options.",
  "/pricing",
);

export default function PricingLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
