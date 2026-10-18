"use client";

import Link from "next/link";
import { FormEvent, useState, useTransition } from "react";
import { forgotPassword } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        setMessage(null);
        const res = await forgotPassword(email);
        setMessage(res.detail || "If that email is registered, we have sent a reset link.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to request password reset");
      }
    });
  };

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6">
      <div>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Reset Password
        </h1>
        <p className="mt-2 text-sm text-[var(--mute)]">Enter your email and we&apos;ll send you a link to reset your password.</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-3">
        <input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Email"
          className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
        />
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
        >
          {pending ? "Sending..." : "Send Reset Link"}
        </button>
      </form>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
      {message ? <p className="text-sm text-[var(--signal)]">{message}</p> : null}

      <Link href="/auth" className="text-sm text-[var(--mute)] hover:text-[var(--signal)]">
        &larr; Back to sign in
      </Link>
    </main>
  );
}
