"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState, useTransition } from "react";
import { getGitHubAuthUrl, getGoogleAuthUrl, getToken, login, register, setToken, me, type User } from "@/lib/api";
import { AccountSettings } from "@/components/account-settings";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      />
    </svg>
  );
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
      />
    </svg>
  );
}

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
  const [googlePending, setGooglePending] = useState(false);
  const [githubPending, setGithubPending] = useState(false);
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

  const onGoogleSignIn = async () => {
    try {
      setGooglePending(true);
      setError(null);
      const redirectUri = `${window.location.origin}/auth/callback/google`;
      const res = await getGoogleAuthUrl(redirectUri);
      if (res?.url) {
        window.location.href = res.url;
      } else {
        throw new Error("Unable to obtain Google sign-in URL.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initiate Google sign-in");
      setGooglePending(false);
    }
  };

  const onGitHubSignIn = async () => {
    try {
      setGithubPending(true);
      setError(null);
      const redirectUri = `${window.location.origin}/auth/callback/github`;
      const res = await getGitHubAuthUrl(redirectUri);
      if (res?.url) {
        window.location.href = res.url;
      } else {
        throw new Error("Unable to obtain GitHub sign-in URL.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initiate GitHub sign-in");
      setGithubPending(false);
    }
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
        {!requireTotp ? (
          <>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              <button
                type="button"
                onClick={onGoogleSignIn}
                disabled={googlePending || githubPending || pending}
                className="flex items-center justify-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2.5 text-xs font-medium text-[var(--text)] transition hover:bg-[var(--surface-hover)] disabled:opacity-50 cursor-pointer"
              >
                <GoogleIcon className="h-4 w-4 shrink-0" />
                <span>{googlePending ? "Connecting…" : "Google"}</span>
              </button>
              <button
                type="button"
                onClick={onGitHubSignIn}
                disabled={googlePending || githubPending || pending}
                className="flex items-center justify-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2.5 text-xs font-medium text-[var(--text)] transition hover:bg-[var(--surface-hover)] disabled:opacity-50 cursor-pointer"
              >
                <GitHubIcon className="h-4 w-4 shrink-0" />
                <span>{githubPending ? "Connecting…" : "GitHub"}</span>
              </button>
            </div>

            <div className="relative my-4 flex items-center justify-center text-xs uppercase text-[var(--text-muted)]">
              <div className="w-full border-t border-[var(--border)]" />
              <span className="bg-[var(--surface-elevated)] px-2">or continue with email</span>
              <div className="w-full border-t border-[var(--border)]" />
            </div>
          </>
        ) : null}

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
