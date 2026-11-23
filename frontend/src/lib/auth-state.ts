import { useSyncExternalStore } from "react";
import { getToken } from "@/lib/api";

function subscribeToAuthChanges(onChange: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("signal-desk-token-change", onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener("signal-desk-token-change", onChange);
    window.removeEventListener("storage", onChange);
  };
}

function getAuthSnapshot() {
  return Boolean(getToken());
}

export function useIsAuthenticated() {
  return useSyncExternalStore(subscribeToAuthChanges, getAuthSnapshot, () => false);
}
