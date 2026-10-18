"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function RedirectInner({ base }: { base: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const qs = searchParams.toString();
    router.replace(qs ? `${base}?${qs}` : base);
  }, [router, searchParams, base]);

  return (
    <main className="flex flex-1 flex-col justify-center">
      <p className="text-[var(--mute)]">Redirecting to Leads…</p>
    </main>
  );
}

export default function FindingsRedirectPage() {
  return (
    <Suspense fallback={<p className="text-[var(--mute)]">Redirecting…</p>}>
      <RedirectInner base="/leads" />
    </Suspense>
  );
}
