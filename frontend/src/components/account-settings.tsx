"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  logout,
  request,
  updateProfile,
  exportMyData,
  type User,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function AccountSettings({ user }: { user: User }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [fullName, setFullName] = useState(user.full_name || "");
  const [currentName, setCurrentName] = useState(user.full_name || "");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleLogout = () => {
    startTransition(async () => {
      await logout();
      router.push("/");
    });
  };

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        setMessage(null);
        const updated = await updateProfile(fullName.trim());
        setCurrentName(updated.full_name || "");
        setMessage("Profile name updated.");
        setTimeout(() => setMessage(null), 3000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update profile");
      }
    });
  };

  const handleExport = () => {
    startTransition(async () => {
      try {
        setError(null);
        const data = await exportMyData();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `signal-desk-export-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        setMessage("Data export downloaded.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Export failed");
      }
    });
  };

  const handleDeleteAccount = () => {
    startTransition(async () => {
      try {
        setError(null);
        await request("/users/me", { method: "DELETE", auth: true });
        await logout();
        router.push("/");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete account");
      }
    });
  };

  const plan = (user.plan || "free").toLowerCase();
  const role = user.account_role || "freelancer";
  const visibility = user.profile_visibility || "private";

  return (
    <Card className="mt-2 p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            className="text-2xl text-[var(--text)]"
            style={{ fontFamily: "var(--font-display), Georgia, serif" }}
          >
            Account Settings
          </h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Profile, session, and account controls.
          </p>
        </div>
        <Badge variant={plan === "pro" ? "accent" : "muted"}>
          {plan === "pro" ? "Pro" : "Free"}
        </Badge>
      </div>

      {message ? (
        <p className="mb-4 rounded-md border border-[var(--accent)]/30 bg-[var(--accent-muted)] px-3 py-2 text-sm text-[var(--accent)]">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mb-4 text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}

      <div className="space-y-6">
        <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
          <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
            Personal information
          </h3>
          <p className="text-sm text-[var(--text-muted)]">
            Signed in as <strong className="text-[var(--text)]">{user.email}</strong>
            {currentName ? ` (${currentName})` : null}
          </p>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            Email verification:{" "}
            <span className={user.is_verified ? "text-[var(--success)]" : "text-[var(--warning)]"}>
              {user.is_verified ? "Verified" : "Not verified"}
            </span>
            {" · "}
            Role: <span className="text-[var(--text)]">{role}</span>
            {" · "}
            Visibility: <span className="text-[var(--text)]">{visibility}</span>
          </p>

          <form onSubmit={handleSaveProfile} className="mt-4 flex flex-wrap items-center gap-3">
            <div className="min-w-[200px] flex-1">
              <label htmlFor="account-fullname" className="sr-only">
                Full Name
              </label>
              <input
                id="account-fullname"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Full name"
                className="sd-input"
                maxLength={120}
              />
            </div>
            <Button type="submit" disabled={pending || fullName.trim() === currentName}>
              {pending ? "Saving…" : "Save name"}
            </Button>
          </form>

          <p className="mt-3 text-xs text-[var(--text-muted)]">
            Two-factor authentication and passwords are managed under Hunt Rules → Security. Privacy
            center:{" "}
            <Link href="/privacy/center" className="text-[var(--signal)] underline">
              export, consents, audit
            </Link>
            .
          </p>
        </div>

        <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
          <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
            Connected accounts
          </h3>
          <p className="mb-3 text-xs text-[var(--text-muted)]">
            OAuth links only after email ownership is verified. Unverified local accounts are not
            merged automatically.
          </p>
          <div className="space-y-2.5">
            <div className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm">
              <span className="font-medium text-[var(--text)]">Google</span>
              <Badge variant={user.google_id ? "accent" : "muted"}>
                {user.google_id ? "Connected" : "Not connected"}
              </Badge>
            </div>
            <div className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm">
              <span className="font-medium text-[var(--text)]">GitHub</span>
              <Badge variant={user.github_id ? "accent" : "muted"}>
                {user.github_id ? "Connected" : "Not connected"}
              </Badge>
            </div>
          </div>
        </div>

        <div className="border-t border-[var(--border)] pt-4">
          <Button onClick={handleExport} variant="outline" className="w-full sm:w-auto" disabled={pending}>
            {pending ? "Working…" : "Download my data"}
          </Button>
          <Button
            onClick={handleLogout}
            variant="outline"
            className="mt-3 w-full sm:ml-3 sm:mt-0 sm:w-auto"
            disabled={pending}
          >
            Sign out
          </Button>

          {user.is_superuser ? (
            <Button
              onClick={() => router.push("/admin")}
              className="mt-3 w-full sm:ml-3 sm:mt-0 sm:w-auto"
            >
              Admin Dashboard
            </Button>
          ) : null}
        </div>

        <div className="border-t border-[var(--danger)]/25 pt-6">
          <h3 className="mb-2 text-sm font-medium text-[var(--danger)]">Danger zone</h3>
          <p className="mb-4 text-sm text-[var(--text-muted)]">
            Permanently delete your account and associated desk data. Legal holds may delay purge of
            some operational logs.
          </p>

          {!confirmDelete ? (
            <Button onClick={() => setConfirmDelete(true)} variant="destructive">
              Delete Account
            </Button>
          ) : (
            <div className="flex flex-wrap items-center gap-3 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-muted)] p-4">
              <span className="text-sm text-[var(--danger)]">Are you absolutely sure?</span>
              <Button onClick={() => setConfirmDelete(false)} variant="outline" disabled={pending}>
                Cancel
              </Button>
              <Button onClick={handleDeleteAccount} variant="destructive" disabled={pending}>
                {pending ? "Deleting..." : "Yes, delete my account"}
              </Button>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
