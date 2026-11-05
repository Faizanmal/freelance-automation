import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-6 py-20 text-center">
      <span className="text-xs font-semibold tracking-widest text-[var(--accent)] uppercase">
        404 — Page Not Found
      </span>
      <h1
        className="text-4xl tracking-tight text-[var(--text)] md:text-5xl"
        style={{ fontFamily: "var(--font-display), Georgia, serif" }}
      >
        Signal lost
      </h1>
      <p className="max-w-md text-sm text-[var(--text-secondary)]">
        The page or lead you are looking for has been moved, expired, or doesn’t exist. Head back to the desk or browse recent leads.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
        <Link href="/">
          <Button variant="default">Back to Desk</Button>
        </Link>
        <Link href="/leads">
          <Button variant="outline">Browse Leads</Button>
        </Link>
      </div>
    </div>
  );
}

