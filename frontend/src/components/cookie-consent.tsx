"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Button } from "./ui/button";
import { getApiBase } from "@/lib/api";

const CONSENT_KEY = "cookieConsent";
const CONSENT_EVENT = "cookie-consent";

function readConsent(): "accepted" | "rejected" | null {
  const value = localStorage.getItem(CONSENT_KEY);
  if (value === "accepted" || value === "true") return "accepted";
  if (value === "rejected") return "rejected";
  return null;
}

function subscribeToConsent(onChange: () => void) {
  window.addEventListener(CONSENT_EVENT, onChange);
  return () => window.removeEventListener(CONSENT_EVENT, onChange);
}

export function CookieConsent() {
  // Server snapshot must match the client's first paint (no localStorage yet → null).
  // Returning "accepted" on the server hid the banner in HTML while the client showed it.
  const consent = useSyncExternalStore(subscribeToConsent, readConsent, () => null);

  const choose = (value: "accepted" | "rejected") => {
    localStorage.setItem(CONSENT_KEY, value);
    window.dispatchEvent(new Event(CONSENT_EVENT));
  };

  if (consent !== null) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-[var(--background)] border-t border-[var(--mute)]/20 p-4 shadow-lg">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-sm text-[var(--fog)] text-center sm:text-left">
          We use optional analytics cookies to understand site traffic. Job alerts and sign-in work either way. See our{" "}
          <a href="/privacy" className="text-[var(--signal)] underline hover:no-underline">Privacy Policy</a> and{" "}
          <a href="/terms" className="text-[var(--signal)] underline hover:no-underline">Terms of Service</a>.
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => choose("rejected")} className="whitespace-nowrap">
            Reject
          </Button>
          <Button onClick={() => choose("accepted")} className="whitespace-nowrap">
            Accept
          </Button>
        </div>
      </div>
    </div>
  );
}

export function Analytics() {
  const consent = useSyncExternalStore(subscribeToConsent, readConsent, () => null);
  const allowed = consent === "accepted";

  useEffect(() => {
    if (!allowed) return;
    if (document.getElementById("plausible-script")) return;
    const script = document.createElement("script");
    script.id = "plausible-script";
    script.defer = true;
    script.dataset.domain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN || "signaldesk.com";
    script.src = "https://plausible.io/js/script.js";
    document.body.appendChild(script);
  }, [allowed]);

  return null;
}

export function ClientErrorReporter() {
  useEffect(() => {
    const send = (message: string, stack?: string) => {
      const body = JSON.stringify({
        message: message.slice(0, 500),
        stack: stack ? stack.slice(0, 4000) : undefined,
        path: window.location.pathname,
      });
      fetch(`${getApiBase()}/telemetry/client-error`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => undefined);
    };

    const onError = (event: ErrorEvent) => {
      send(event.message || "Frontend error", event.error instanceof Error ? event.error.stack : undefined);
    };
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const message = reason instanceof Error ? reason.message : String(reason);
      const stack = reason instanceof Error ? reason.stack : undefined;
      send(message || "Unhandled rejection", stack);
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return null;
}
