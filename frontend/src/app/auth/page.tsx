"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState, useTransition } from "react";
import { getToken, login, register, setToken, me, type User } from "@/lib/api";
import { AccountSettings } from "@/components/account-settings";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [info, setInfo] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [requireTotp, setRequireTotp] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [user, setUser] = useState<User | null>(null);
  const [loadingSession, setLoadingSession] = useState(() => Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;
    me()
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setLoadingSession(false));
  }, []);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        setInfo(null);
        if (mode === "register") {
          const created = await register(email, password, fullName || undefined);
          await login(email, password, requireTotp ? totpCode : undefined);
          const verifyFlag = created.auto_verified
            ? "auto"
            : created.verification_email_sent === false
              ? "smtp"
              : "needed";
          router.push(`/preferences?verify=${verifyFlag}`);
          return;
        }
        await login(email, password, requireTotp ? totpCode : undefined);
        router.push("/preferences");
      } catch (err) {
        if (err instanceof Error && err.message === "TOTP_REQUIRED") {
          setRequireTotp(true);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Auth failed");
          setToken(null);
        }
      }
    });
  };

  if (loadingSession) {
    return (
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6">
        <p className="text-[var(--text-muted)]">Loading...</p>
      </div>
    );
  }

  if (user) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6">
        <AccountSettings user={user} />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 py-8">
      <div>
        <h1
          className="text-4xl tracking-tight text-[var(--text)]"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          Set Hunt Rules, get ranked leads, and an email digest — then pitch on the original listing.
        </p>
      </div>

      <Card className="p-5">
        <form onSubmit={onSubmit} className="space-y-3">
          {mode === "register" ? (
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Full name"
              className="sd-input"
            />
          ) : null}
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email"
            className="sd-input"
          />
          <input
            type="password"
            required
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            disabled={requireTotp}
            className="sd-input disabled:opacity-50"
          />
          {requireTotp ? (
            <input
              type="text"
              required
              value={totpCode}
              onChange={(event) => setTotpCode(event.target.value)}
              placeholder="Authenticator code (6 digits)"
              className="sd-input"
            />
          ) : null}
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? "Working…" : mode === "login" ? "Sign in" : "Register"}
          </Button>
        </form>
      </Card>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {info ? <p className="text-sm text-[var(--accent)]">{info}</p> : null}

      {!requireTotp ? (
        <div className="flex flex-col items-start gap-4">
          <button
            type="button"
            className="text-sm text-[var(--accent)] hover:underline"
            onClick={() => setMode((current) => (current === "login" ? "register" : "login"))}
          >
            {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
          </button>

          {mode === "login" ? (
            <Link href="/auth/forgot-password" className="text-sm text-[var(--text-muted)] hover:text-[var(--accent)]">
              Forgot your password?
            </Link>
          ) : null}
        </div>
      ) : null}

      <Link href="/" className="text-sm text-[var(--text-muted)] hover:text-[var(--accent)]">
        Back to desk
      </Link>
    </div>
  );
}
