"use client";

import { useState, useEffect } from "react";
import { Button } from "./ui/button";

export function CookieConsent() {
  const [showConsent, setShowConsent] = useState(false);

  useEffect(() => {
    // Check if user has already consented
    const hasConsented = localStorage.getItem("cookieConsent");
    if (!hasConsented) {
      setShowConsent(true);
    }
  }, []);

  const acceptCookies = () => {
    localStorage.setItem("cookieConsent", "true");
    setShowConsent(false);
  };

  if (!showConsent) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-[var(--background)] border-t border-[var(--mute)]/20 p-4 shadow-lg">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-sm text-[var(--fog)] text-center sm:text-left">
          We use cookies to improve your experience and analyze site traffic. By continuing to use our site, you agree to our <a href="/privacy" className="text-[var(--signal)] underline hover:no-underline">Privacy Policy</a> and <a href="/terms" className="text-[var(--signal)] underline hover:no-underline">Terms of Service</a>.
        </div>
        <div className="flex gap-4">
          <Button onClick={acceptCookies} className="whitespace-nowrap">
            Accept Cookies
          </Button>
        </div>
      </div>
    </div>
  );
}
