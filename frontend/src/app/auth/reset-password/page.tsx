"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState, useTransition, Suspense } from "react";
import { resetPassword } from "@/lib/api";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  if (!token) {
    return (
      <div className="space-y-4">
        <p className="text-[var(--ember)]">Missing or invalid reset token.</p>
        <Link href="/auth/forgot-password" className="text-sm text-[var(--signal)] hover:underline">
          Request a new link
        </Link>
      </div>
    );
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        await resetPassword(token, password);
        setMessage("Password has been successfully reset! You can now sign in.");
        setTimeout(() => router.push("/auth"), 3000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to reset password");
      }
    });
  };

  return (
    <>
      <form onSubmit={onSubmit} className="space-y-3">
        <input
          type="password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="New Password"
          className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
        />
        <button
          type="submit"
          disabled={pending || !!message}
          className="w-full rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
        >
          {pending ? "Resetting..." : "Save New Password"}
        </button>
      </form>
      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {message ? <p className="text-sm text-[var(--signal)]">{message}</p> : null}
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6">
      <div>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Set New Password
        </h1>
        <p className="mt-2 text-sm text-[var(--mute)]">Choose a strong, new password for your account.</p>
      </div>

      <Suspense fallback={<p className="text-[var(--mute)]">Loading...</p>}>
        <ResetPasswordForm />
      </Suspense>

      <Link href="/auth" className="text-sm text-[var(--mute)] hover:text-[var(--signal)]">
        &larr; Back to sign in
      </Link>
    </main>
  );
}
