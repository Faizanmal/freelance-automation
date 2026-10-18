"use client";

import { useState, useTransition } from "react";
import { setup2fa, enable2fa, disable2fa, type User } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { QRCodeSVG } from "qrcode.react";

export function SecuritySettings({ user, onUpdate }: { user: User; onUpdate: () => void }) {
  const [setupData, setSetupData] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const handleSetup = () => {
    startTransition(async () => {
      try {
        setError(null);
        const data = await setup2fa();
        setSetupData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to initiate 2FA setup");
      }
    });
  };

  const handleEnable = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        await enable2fa(code);
        setMessage("2FA successfully enabled!");
        setSetupData(null);
        setCode("");
        onUpdate();
        setTimeout(() => setMessage(null), 3000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Invalid code");
      }
    });
  };

  const handleDisable = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        await disable2fa(code);
        setMessage("2FA successfully disabled");
        setCode("");
        onUpdate();
        setTimeout(() => setMessage(null), 3000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Invalid code");
      }
    });
  };

  return (
    <Card className="p-8">
      <h2 className="text-2xl mb-6" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
        Security
      </h2>
      <div className="space-y-4">
        <h3 className="text-lg font-medium text-[var(--fog)]">Two-Factor Authentication (2FA)</h3>
        
        {user.is_totp_enabled ? (
          <div>
            <p className="text-sm text-[var(--mute)] mb-4">
              2FA is currently <strong className="text-[var(--signal)]">enabled</strong> on your account.
            </p>
            <form onSubmit={handleDisable} className="flex flex-col gap-3 max-w-sm">
              <input
                type="text"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Authenticator code (to disable)"
                className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 outline-none transition focus:border-[var(--ember)]/50 focus:bg-black/60 shadow-inner"
              />
              <Button type="submit" variant="destructive" disabled={pending}>
                {pending ? "Disabling..." : "Disable 2FA"}
              </Button>
            </form>
          </div>
        ) : (
          <div>
            <p className="text-sm text-[var(--mute)] mb-4">
              Protect your account with an authenticator app (like Authy or Google Authenticator).
            </p>
            {!setupData ? (
              <Button onClick={handleSetup} disabled={pending}>
                {pending ? "Loading..." : "Set up 2FA"}
              </Button>
            ) : (
              <div className="bg-black/20 p-6 rounded-xl border border-white/5 space-y-6">
                <div>
                  <p className="text-sm text-[var(--fog)] mb-4">1. Scan this QR code with your authenticator app:</p>
                  <div className="bg-white p-4 inline-block rounded-xl">
                    <QRCodeSVG value={setupData.provisioning_uri} size={160} />
                  </div>
                </div>
                
                <form onSubmit={handleEnable} className="flex flex-col gap-3 max-w-sm">
                  <p className="text-sm text-[var(--fog)]">2. Enter the 6-digit code to confirm:</p>
                  <input
                    type="text"
                    required
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="123456"
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 outline-none transition focus:border-[var(--signal)]/50 focus:bg-black/60 shadow-inner"
                  />
                  <Button type="submit" disabled={pending}>
                    {pending ? "Verifying..." : "Verify & Enable"}
                  </Button>
                </form>
              </div>
            )}
          </div>
        )}
        
        {error && <p className="text-sm text-[var(--ember)] mt-2">{error}</p>}
        {message && <p className="text-sm text-[var(--signal)] mt-2">{message}</p>}
      </div>
    </Card>
  );
}
