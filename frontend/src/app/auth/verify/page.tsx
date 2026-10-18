"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { resendVerification, verifyEmail } from "@/lib/api";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const missingToken = !token;

  useEffect(() => {
    if (!token) return;

    verifyEmail(token)
      .then(() => {
        setMessage("Email has been successfully verified! You can now log in.");
        setTimeout(() => router.push("/auth"), 3000);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to verify email");
      });
  }, [token, router]);

  const resend = async () => {
    try {
      setError(null);
      const res = await resendVerification(email);
      setMessage(res.detail || "If that email is unverified, a new link was sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resend failed");
    }
  };

  return (
    <div className="space-y-4">
      {missingToken ? (
        <div className="space-y-3">
          <p className="text-[var(--fog)]">
            Open the link from your verification email, or request a new one below. Hunts stay locked until
            your email is verified.
          </p>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Your account email"
            className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
          <button
            type="button"
            onClick={resend}
            disabled={!email}
            className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
          >
            Resend verification
          </button>
        </div>
      ) : null}
      {error && <p className="text-[var(--ember)]">{error}</p>}
      {message && <p className="text-[var(--signal)]">{message}</p>}
      {!missingToken && !error && !message && <p className="text-[var(--mute)]">Verifying your email...</p>}
      
      <div className="pt-4">
        <Link href="/auth" className="text-sm text-[var(--mute)] hover:text-[var(--signal)]">
          &larr; Back to sign in
        </Link>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6">
      <div>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Verify Email
        </h1>
      </div>

      <Suspense fallback={<p className="text-[var(--mute)]">Loading...</p>}>
        <VerifyEmailContent />
      </Suspense>
    </main>
  );
}
