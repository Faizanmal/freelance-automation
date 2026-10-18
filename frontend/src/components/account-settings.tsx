"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { setToken, request, type User } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function AccountSettings({ user }: { user: User }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleLogout = () => {
    setToken(null);
    router.push("/");
  };

  const handleDeleteAccount = () => {
    startTransition(async () => {
      try {
        setError(null);
        await request("/users/me", { method: "DELETE", auth: true });
        setToken(null);
        router.push("/");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete account");
      }
    });
  };

  return (
    <Card className="p-8 mt-8">
      <h2 className="text-2xl mb-6" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
        Account Settings
      </h2>
      
      <div className="space-y-6">
        <div>
          <h3 className="text-sm font-medium text-[var(--fog)] mb-1">Profile details</h3>
          <p className="text-sm text-[var(--mute)]">
            Signed in as <strong className="text-[var(--paper)]">{user.email}</strong> 
            {user.full_name && ` (${user.full_name})`}
          </p>
        </div>

        <div className="pt-4 border-t border-white/10">
          <Button onClick={handleLogout} variant="outline" className="w-full sm:w-auto">
            Sign out
          </Button>
          
          {user.is_superuser && (
            <Button onClick={() => router.push("/admin")} className="w-full sm:w-auto ml-0 sm:ml-3 mt-3 sm:mt-0 bg-[var(--signal)] text-[var(--ink)]">
              Admin Dashboard
            </Button>
          )}
        </div>

        <div className="pt-8 border-t border-red-900/30">
          <h3 className="text-sm font-medium text-[var(--ember)] mb-2">Danger Zone</h3>
          <p className="text-sm text-[var(--mute)] mb-4">
            Permanently delete your account and all associated data. This action cannot be undone.
          </p>
          
          {!confirmDelete ? (
            <Button 
              onClick={() => setConfirmDelete(true)} 
              variant="destructive"
              className="bg-red-950 text-red-200 hover:bg-red-900"
            >
              Delete Account
            </Button>
          ) : (
            <div className="flex items-center gap-3 bg-red-950/40 p-4 rounded-xl border border-red-900/50">
              <span className="text-sm text-red-200">Are you absolutely sure?</span>
              <Button onClick={() => setConfirmDelete(false)} variant="outline" disabled={pending}>
                Cancel
              </Button>
              <Button onClick={handleDeleteAccount} variant="destructive" disabled={pending}>
                {pending ? "Deleting..." : "Yes, delete my account"}
              </Button>
            </div>
          )}
          {error && <p className="text-sm text-[var(--ember)] mt-2">{error}</p>}
        </div>
      </div>
    </Card>
  );
}
