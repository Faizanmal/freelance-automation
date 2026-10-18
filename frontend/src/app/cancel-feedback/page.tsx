"use client";

import { FormEvent, useState, useTransition } from "react";
import { submitCancellationFeedback } from "@/lib/api";

const REASONS = [
  { id: "too_expensive", label: "Too expensive" },
  { id: "missing_features", label: "Missing a feature I need" },
  { id: "not_enough_jobs", label: "Not enough relevant jobs" },
  { id: "switching", label: "Switching to something else" },
  { id: "other", label: "Something else" },
];

export default function CancelFeedbackPage() {
  const [reason, setReason] = useState(REASONS[0].id);
  const [details, setDetails] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      try {
        setError(null);
        const result = await submitCancellationFeedback({
          reason,
          details: details.trim() || undefined,
          email: email.trim() || undefined,
        });
        setMessage(result.detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not save feedback");
      }
    });
  };

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-6 pt-12">
      <div>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Exit survey
        </h1>
        <p className="mt-2 text-sm text-[var(--mute)]">
          If you canceled Pro, tell us what to fix. This is stored with the product, not sent to a third-party form.
        </p>
      </div>

      {message ? (
        <p className="text-sm text-[var(--signal)]">{message}</p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <fieldset className="space-y-2">
            <legend className="text-sm text-[var(--fog)] mb-2">Why did you cancel?</legend>
            {REASONS.map((option) => (
              <label key={option.id} className="flex items-center gap-3 text-sm text-[var(--paper)]">
                <input
                  type="radio"
                  name="reason"
                  value={option.id}
                  checked={reason === option.id}
                  onChange={() => setReason(option.id)}
                />
                {option.label}
              </label>
            ))}
          </fieldset>
          <textarea
            value={details}
            onChange={(event) => setDetails(event.target.value)}
            placeholder="What should we have done differently?"
            maxLength={2000}
            className="min-h-28 w-full rounded-2xl border border-white/15 bg-black/20 px-4 py-3 outline-none focus:border-[var(--signal)]/50"
          />
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email (optional)"
            className="w-full rounded-full border border-white/15 bg-black/20 px-4 py-2.5 outline-none focus:border-[var(--signal)]/50"
          />
          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
          >
            {pending ? "Saving..." : "Send feedback"}
          </button>
        </form>
      )}
      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
    </main>
  );
}
