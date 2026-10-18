"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRouter } from "next/navigation";

export function OnboardingWizard() {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState(0);
  const router = useRouter();

  useEffect(() => {
    const hasSeenOnboarding = localStorage.getItem("signaldesk_onboarded");
    if (!hasSeenOnboarding) {
      const timer = setTimeout(() => setIsOpen(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const completeOnboarding = () => {
    localStorage.setItem("signaldesk_onboarded", "true");
    setIsOpen(false);
  };

  const steps = [
    {
      title: "Set Hunt Rules",
      content:
        "Tell Signal Desk what to hunt — skills, budget, location, and freelance focus. Rules drive matching and your digest.",
      action: "Open Hunt Rules",
      onClick: () => {
        router.push("/preferences?tab=matching");
        setStep(1);
      },
    },
    {
      title: "Open your leads",
      content:
        "Leads ranks public freelance and contract fits with why/risks. Open the original listing to pitch.",
      action: "Open Leads",
      onClick: () => {
        router.push("/leads");
        setStep(2);
      },
    },
    {
      title: "Pitch on the source",
      content:
        "Use Open original for every lead. Signal Desk finds and ranks — it never invents jobs or auto-applies.",
      action: "Finish setup",
      onClick: completeOnboarding,
    },
  ];

  if (!isOpen) return null;

  const current = steps[step];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="w-full max-w-lg"
        >
          <Card className="relative border-white/20 bg-black/90 p-8 shadow-2xl">
            <button
              type="button"
              onClick={completeOnboarding}
              className="absolute top-4 right-4 text-white/50 hover:text-white"
              aria-label="Dismiss onboarding"
            >
              ×
            </button>
            <div className="mb-8">
              <div className="mb-6 flex gap-2">
                {steps.map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-[var(--signal)]" : "bg-white/10"}`}
                  />
                ))}
              </div>
              <h2 className="mb-3 text-2xl font-semibold text-[var(--paper)]">{current.title}</h2>
              <p className="text-lg leading-relaxed text-[var(--fog)]">{current.content}</p>
            </div>
            <div className="mt-8 flex justify-end gap-3 border-t border-white/10 pt-6">
              {step > 0 ? (
                <Button variant="outline" onClick={() => setStep(step - 1)}>
                  Back
                </Button>
              ) : null}
              <Button
                onClick={current.onClick}
                className="bg-[var(--signal)] font-medium text-[var(--ink)] hover:bg-[var(--signal)]/90"
              >
                {current.action}
              </Button>
            </div>
          </Card>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
