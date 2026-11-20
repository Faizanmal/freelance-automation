import type { Preferences } from "@/lib/api";

/** Plain-language summary of Hunt Rules for desk / preferences. */
export function HuntRulesPreview({ prefs }: { prefs: Preferences | null }) {
  if (!prefs) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        No Hunt Rules yet. Add skills and a minimum rate to start ranking leads.
      </p>
    );
  }

  const skills = (prefs.skills?.length ? prefs.skills : prefs.keywords || []).slice(0, 8);
  const excludes = (prefs.exclude_keywords || []).slice(0, 5);
  const rate =
    typeof prefs.min_hourly_rate === "number"
      ? `≥ $${prefs.min_hourly_rate}/hr`
      : prefs.min_budget
        ? `budget from $${prefs.min_budget}`
        : "any rate";
  const focus = prefs.freelance_focus !== false ? "freelance / contract preferred" : "all engagement types";
  const digest = prefs.digest_mode
    ? `digest ${(prefs.digest_days || ["weekdays"]).join(", ")} at ${prefs.digest_time_local || "09:00"} (${prefs.timezone || "local"})`
    : "digest paused";

  return (
    <div className="space-y-2 text-sm text-[var(--text-secondary)]" aria-live="polite">
      <p>
        Looking for <strong className="text-[var(--text)]">{skills.join(", ") || "any skills"}</strong>
        {excludes.length ? (
          <>
            , excluding <strong className="text-[var(--text)]">{excludes.join(", ")}</strong>
          </>
        ) : null}
        .
      </p>
      <p>
        Pay filter: <strong className="text-[var(--text)]">{rate}</strong>. Focus:{" "}
        <strong className="text-[var(--text)]">{focus}</strong>.
      </p>
      <p>
        Alerts: <strong className="text-[var(--text)]">{digest}</strong>.
      </p>
    </div>
  );
}
