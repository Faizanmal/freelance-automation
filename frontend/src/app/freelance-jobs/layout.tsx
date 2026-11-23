import { publicPageMetadata } from "@/lib/public-metadata";

export const metadata = publicPageMetadata(
  "Freelance and contract opportunities",
  "Browse public freelance and contract opportunities with source links and clear listing details.",
  "/freelance-jobs",
);

export default function FreelanceJobsLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
