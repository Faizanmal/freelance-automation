"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";

export default function SessionExpiredPage() {
  return (
    <div className="mx-auto flex min-h-[70vh] w-full max-w-lg flex-col justify-center px-4 py-12">
      <Card className="p-8" role="alert">
        <h1
          className="text-2xl text-[var(--text)]"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Session expired
        </h1>
        <p className="mt-3 text-sm text-[var(--text-muted)]">
          Your signed-in session ended or could not be refreshed. Sign in again to continue
          hunting leads. Unsaved Hunt Rules changes may need to be re-entered.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/auth"
            className="inline-flex h-10 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-foreground)]"
          >
            Sign in
          </Link>
          <Link
            href="/"
            className="inline-flex h-10 items-center justify-center rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm font-semibold text-[var(--text)]"
          >
            Back to desk
          </Link>
        </div>
      </Card>
    </div>
  );
}
