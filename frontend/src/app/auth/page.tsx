"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState, useTransition } from "react";
import { login, register, setToken } from "@/lib/api";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        if (mode === "register") {
          await register(email, password, fullName || undefined);
        }
        await login(email, password);
        router.push("/preferences");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Auth failed");
        setToken(null);
      }
    });
  };

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6">
      <div>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-2 text-sm text-[var(--mute)]">Save preferences and get match alerts when scrapes land.</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-3">
        {mode === "register" ? (
          <input
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Full name"
            className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
        ) : null}
        <input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Email"
          className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
        />
        <input
          type="password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Password"
          className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
        />
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
        >
          {pending ? "Working…" : mode === "login" ? "Sign in" : "Register"}
        </button>
      </form>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}

      <button
        type="button"
        className="text-sm text-[var(--signal)]"
        onClick={() => setMode((current) => (current === "login" ? "register" : "login"))}
      >
        {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
      </button>

      <Link href="/" className="text-sm text-[var(--mute)]">
        Back to desk
      </Link>
    </main>
  );
}
