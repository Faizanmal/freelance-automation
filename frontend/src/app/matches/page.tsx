"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function RedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const qs = searchParams.toString();
    router.replace(qs ? `/leads?${qs}` : "/leads");
  }, [router, searchParams]);

  return (
    <main className="flex flex-1 flex-col justify-center">
      <p className="text-[var(--mute)]">Redirecting to Leads…</p>
    </main>
  );
}

export default function MatchesRedirectPage() {
  return (
    <Suspense fallback={<p className="text-[var(--mute)]">Redirecting…</p>}>
      <RedirectInner />
    </Suspense>
  );
}
