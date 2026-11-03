"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { usePathname, useRouter } from "next/navigation";
import {
  getToken,
  getPreferences,
  updatePreferences,
  subscribeAuth,
  type Preferences,
} from "@/lib/api";
import { Check, Sparkles, Clock, DollarSign, Plus, ArrowRight } from "lucide-react";

const SUGGESTED_SKILLS = [
  "React",
  "Next.js",
  "TypeScript",
  "Python",
  "FastAPI",
  "Node.js",
  "AI / LLM",
  "DevOps",
  "Mobile",
  "UI/UX Design",
  "PostgreSQL",
  "Go",
];

const SUGGESTED_RATES = [
  { label: "Any rate", value: null },
  { label: "$50/hr+", value: 50 },
  { label: "$75/hr+", value: 75 },
  { label: "$100/hr+", value: 100 },
  { label: "$150/hr+", value: 150 },
];

export function OnboardingWizard() {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [hasToken, setHasToken] = useState(false);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([
    "React",
    "TypeScript",
    "Python",
  ]);
  const [customSkill, setCustomSkill] = useState("");
  const [minRate, setMinRate] = useState<number | null>(75);
  const [freelanceFocus, setFreelanceFocus] = useState(true);
  const [digestTime, setDigestTime] = useState("09:00");
  const [saving, setSaving] = useState(false);
  const [timezone, setTimezone] = useState("UTC");

  const router = useRouter();
  const pathname = usePathname();
  const onAuthPage = Boolean(pathname?.startsWith("/auth"));

  useEffect(() => {
    setHasToken(Boolean(getToken()));
    try {
      setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
    } catch {
      setTimezone("UTC");
    }
    return subscribeAuth(() => setHasToken(Boolean(getToken())));
  }, []);

  useEffect(() => {
    if (onAuthPage || !hasToken) return;
    const hasSeenOnboarding = localStorage.getItem("signaldesk_onboarded");
    if (hasSeenOnboarding) return;

    // Load any existing preferences to prefill
    getPreferences()
      .then((existing) => {
        if (existing?.keywords?.length) {
          setSelectedSkills(existing.keywords);
        }
        if (typeof existing?.min_hourly_rate === "number") {
          setMinRate(existing.min_hourly_rate);
        }
      })
      .catch(() => {})
      .finally(() => {
        const timer = setTimeout(() => setIsOpen(true), 1200);
        return () => clearTimeout(timer);
      });
  }, [pathname, onAuthPage, hasToken]);

  const dismissOnboarding = () => {
    localStorage.setItem("signaldesk_onboarded", "true");
    setIsOpen(false);
  };

  const toggleSkill = (skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  const handleAddCustomSkill = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const clean = customSkill.trim();
    if (clean && !selectedSkills.includes(clean)) {
      setSelectedSkills((prev) => [...prev, clean]);
      setCustomSkill("");
    }
  };

  const handleSaveAndFinish = async () => {
    setSaving(true);
    try {
      const payload: Preferences = {
        keywords: selectedSkills.length ? selectedSkills : ["freelance", "contract"],
        exclude_keywords: ["unpaid", "equity-only", "internship"],
        skills: selectedSkills,
        min_budget: minRate ? minRate * 20 : null,
        max_budget: null,
        min_hourly_rate: minRate,
        sources: [
          "serpapi_freelance",
          "serpapi_jobs",
          "serpapi_companies",
          "hn_hiring",
          "remoteok",
          "himalayas",
        ],
        freelance_focus: freelanceFocus,
        digest_mode: true,
        digest_time_local: digestTime,
        digest_days: ["mon", "tue", "wed", "thu", "fri"],
        timezone: timezone,
      };

      await updatePreferences(payload);
      localStorage.setItem("signaldesk_onboarded", "true");
      setIsOpen(false);
      router.push("/leads");
    } catch {
      // If saving fails, fallback to standard dismiss
      dismissOnboarding();
      router.push("/leads");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || onAuthPage || !hasToken) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          className="w-full max-w-xl"
        >
          <Card className="relative border-white/15 bg-[var(--surface)] p-6 md:p-8 shadow-2xl">
            <button
              type="button"
              onClick={dismissOnboarding}
              className="absolute top-4 right-4 text-white/50 hover:text-white text-lg"
              aria-label="Dismiss setup"
            >
              ×
            </button>

            {/* Step Indicators */}
            <div className="mb-6 flex gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className={`h-1.5 flex-1 rounded-full transition-colors ${
                    i <= step ? "bg-[var(--accent)]" : "bg-white/10"
                  }`}
                />
              ))}
            </div>

            {/* Step 0: Skills Selection */}
            {step === 0 && (
              <motion.div
                key="step-0"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="space-y-5"
              >
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">
                    <Sparkles className="size-3.5" />
                    <span>Step 1 of 3</span>
                  </div>
                  <h2 className="mt-1 text-2xl font-semibold text-[var(--paper)]">
                    What are your core skills?
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Select your focus areas. We rank public client opportunities matching these rules.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  {SUGGESTED_SKILLS.map((skill) => {
                    const active = selectedSkills.includes(skill);
                    return (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => toggleSkill(skill)}
                        className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                          active
                            ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                            : "border border-white/10 bg-white/5 text-[var(--text-secondary)] hover:bg-white/10"
                        }`}
                      >
                        {active ? <Check className="size-3" /> : null}
                        {skill}
                      </button>
                    );
                  })}
                </div>

                <form onSubmit={handleAddCustomSkill} className="flex gap-2 pt-2">
                  <input
                    value={customSkill}
                    onChange={(e) => setCustomSkill(e.target.value)}
                    placeholder="Add custom skill (e.g. Docker, GraphQL, Figma)…"
                    className="sd-input flex-1 text-xs"
                  />
                  <Button
                    type="submit"
                    variant="outline"
                    size="sm"
                    disabled={!customSkill.trim()}
                  >
                    <Plus className="size-3.5" />
                    Add
                  </Button>
                </form>

                <div className="mt-8 flex justify-end gap-3 border-t border-white/10 pt-4">
                  <Button
                    onClick={() => setStep(1)}
                    disabled={selectedSkills.length === 0}
                    className="gap-2"
                  >
                    <span>Next: Target Rates</span>
                    <ArrowRight className="size-4" />
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 1: Rates & Contract Focus */}
            {step === 1 && (
              <motion.div
                key="step-1"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="space-y-5"
              >
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">
                    <DollarSign className="size-3.5" />
                    <span>Step 2 of 3</span>
                  </div>
                  <h2 className="mt-1 text-2xl font-semibold text-[var(--paper)]">
                    Target rate & contract preference
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Filter out low-budget gigs and prioritize high-paying direct client work.
                  </p>
                </div>

                <div className="space-y-2 pt-2">
                  <span className="text-xs font-medium text-[var(--text-muted)]">
                    Minimum Hourly Rate
                  </span>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                    {SUGGESTED_RATES.map((rate) => {
                      const active = minRate === rate.value;
                      return (
                        <button
                          key={rate.label}
                          type="button"
                          onClick={() => setMinRate(rate.value)}
                          className={`rounded-lg border p-2 text-center text-xs font-medium transition-colors ${
                            active
                              ? "border-[var(--accent)] bg-[var(--accent-muted)] text-[var(--accent)]"
                              : "border-white/10 bg-white/5 text-[var(--text-secondary)] hover:bg-white/10"
                          }`}
                        >
                          {rate.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="rounded-lg border border-white/10 bg-white/5 p-4 pt-3">
                  <label className="flex cursor-pointer items-start gap-3">
                    <input
                      type="checkbox"
                      checked={freelanceFocus}
                      onChange={(e) => setFreelanceFocus(e.target.checked)}
                      className="mt-1 size-4 rounded accent-[var(--accent)]"
                    />
                    <div>
                      <p className="text-sm font-medium text-[var(--text)]">
                        Freelance & Contract Focus (Recommended)
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--text-muted)] leading-relaxed">
                        Downranks full-time salaried W-2 roles with benefits packages. Boosts hourly, contract, retainer, and project-based opportunities.
                      </p>
                    </div>
                  </label>
                </div>

                <div className="mt-8 flex justify-between gap-3 border-t border-white/10 pt-4">
                  <Button variant="outline" onClick={() => setStep(0)}>
                    Back
                  </Button>
                  <Button onClick={() => setStep(2)} className="gap-2">
                    <span>Next: Digest Schedule</span>
                    <ArrowRight className="size-4" />
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 2: Show Clock / Digest Schedule */}
            {step === 2 && (
              <motion.div
                key="step-2"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="space-y-5"
              >
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--accent)]">
                    <Clock className="size-3.5" />
                    <span>Step 3 of 3</span>
                  </div>
                  <h2 className="mt-1 text-2xl font-semibold text-[var(--paper)]">
                    Your daily digest schedule
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    We hunt continuously. When would you like your curated opportunity digest?
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3 pt-2">
                  {[
                    { label: "Morning", time: "09:00", desc: "9:00 AM" },
                    { label: "Midday", time: "13:00", desc: "1:00 PM" },
                    { label: "Evening", time: "18:00", desc: "6:00 PM" },
                  ].map((slot) => {
                    const active = digestTime === slot.time;
                    return (
                      <button
                        key={slot.time}
                        type="button"
                        onClick={() => setDigestTime(slot.time)}
                        className={`rounded-lg border p-3 text-left transition-colors ${
                          active
                            ? "border-[var(--accent)] bg-[var(--accent-muted)] text-[var(--accent)]"
                            : "border-white/10 bg-white/5 text-[var(--text-secondary)] hover:bg-white/10"
                        }`}
                      >
                        <p className="text-xs font-semibold uppercase">{slot.label}</p>
                        <p className="mt-1 text-lg font-bold text-[var(--text)]">{slot.desc}</p>
                      </button>
                    );
                  })}
                </div>

                <div className="text-xs text-[var(--text-muted)]">
                  Timezone detected: <span className="text-[var(--text)] font-medium">{timezone}</span> (Delivery on weekdays).
                </div>

                <div className="mt-8 flex justify-between gap-3 border-t border-white/10 pt-4">
                  <Button variant="outline" onClick={() => setStep(1)} disabled={saving}>
                    Back
                  </Button>
                  <Button
                    onClick={handleSaveAndFinish}
                    disabled={saving}
                    className="bg-[var(--accent)] font-semibold text-[var(--accent-foreground)]"
                  >
                    {saving ? "Saving Hunt Rules…" : "Save & View My Leads ➔"}
                  </Button>
                </div>
              </motion.div>
            )}
          </Card>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
