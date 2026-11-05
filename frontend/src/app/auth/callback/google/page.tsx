"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState, useTransition } from "react";
import { loginWithGoogle } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

function GoogleCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const oauthError = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");

  const initialError = oauthError
    ? errorDescription || `Google sign-in was cancelled or failed (${oauthError}).`
    : !code
    ? "Missing authorization code from Google."
    : null;

  const [error, setError] = useState<string | null>(initialError);
  const [requireTotp, setRequireTotp] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!code || oauthError) {
      return;
    }

    let isCancelled = false;

    startTransition(async () => {
      try {
        const redirectUri = `${window.location.origin}/auth/callback/google`;
        await loginWithGoogle({
          code,
          state: state || undefined,
          redirect_uri: redirectUri,
        });
        if (!isCancelled) {
          router.push("/preferences");
        }
      } catch (err) {
        if (isCancelled) return;
        if (err instanceof Error && err.message === "TOTP_REQUIRED") {
          setRequireTotp(true);
        } else {
          setError(err instanceof Error ? err.message : "Google sign-in failed.");
        }
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [code, state, oauthError, router]);

  const onTotpSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!code) return;
    startTransition(async () => {
      try {
        setError(null);
        const redirectUri = `${window.location.origin}/auth/callback/google`;
        await loginWithGoogle({
          code,
          state: state || undefined,
          redirect_uri: redirectUri,
          totp_code: totpCode,
        });
        router.push("/preferences");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Two-factor authentication failed.");
      }
    });
  };

  if (requireTotp) {
    return (
      <Card className="p-6">
        <h2 className="text-xl font-medium text-[var(--text)]">Two-Factor Authentication</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Your account is protected with 2FA. Enter the 6-digit code from your authenticator app to finish signing in.
        </p>
        <form onSubmit={onTotpSubmit} className="mt-4 space-y-4">
          <input
            type="text"
            required
            autoFocus
            maxLength={6}
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value.trim())}
            placeholder="000000"
            className="sd-input text-center text-lg tracking-widest"
          />
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          <Button type="submit" disabled={pending || totpCode.length < 6} className="w-full">
            {pending ? "Verifying…" : "Confirm Code"}
          </Button>
        </form>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 text-center">
        <h2 className="text-lg font-medium text-[var(--danger)]">Sign-in Failed</h2>
        <p className="mt-2 text-sm text-[var(--text-muted)]">{error}</p>
        <div className="mt-5">
          <Link href="/auth">
            <Button variant="outline">Return to Sign In</Button>
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-8 text-center">
      <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
      <h2 className="text-lg font-medium text-[var(--text)]">Signing in with Google</h2>
      <p className="mt-1 text-sm text-[var(--text-muted)]">Completing secure authentication, please wait…</p>
    </Card>
  );
}

export default function GoogleCallbackPage() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 py-12">
      <Suspense
        fallback={
          <Card className="p-8 text-center">
            <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
            <p className="text-sm text-[var(--text-muted)]">Loading…</p>
          </Card>
        }
      >
        <GoogleCallbackContent />
      </Suspense>
    </div>
  );
}

