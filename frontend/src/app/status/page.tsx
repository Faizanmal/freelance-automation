"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { getApiBase } from "@/lib/api";

export default function StatusPage() {
  const [liveStatus, setLiveStatus] = useState<string>("Checking...");

  useEffect(() => {
    async function checkHealth() {
      const apiBase = getApiBase();
      if (!apiBase) {
        setLiveStatus("Not configured");
        return;
      }
      try {
        const liveRes = await fetch(`${apiBase}/health/live`);
        if (liveRes.ok) {
          setLiveStatus("Operational");
        } else {
          setLiveStatus("Degraded");
        }
      } catch {
        setLiveStatus("Down");
      }

    }
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    if (status === "Operational" || status === "ok") return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
    if (status === "Checking...") return "text-amber-400 bg-amber-400/10 border-amber-400/20";
    return "text-rose-400 bg-rose-400/10 border-rose-400/20";
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      className="flex flex-1 flex-col gap-8 max-w-3xl mx-auto w-full pt-12"
    >
      <section className="text-center mb-8">
        <motion.h1 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl font-medium" 
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          System Status
        </motion.h1>
        <p className="mt-4 text-[var(--fog)]">A basic live reachability check for the public API. It does not report dependency health or incident history.</p>
      </section>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-6 pb-6 border-b border-white/5">
          <div>
            <h2 className="text-xl font-semibold text-[var(--paper)]">Public API</h2>
            <p className="text-sm text-[var(--mute)]">Reachability only</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm border font-medium ${getStatusColor(liveStatus)}`}>
            {liveStatus}
          </span>
        </div>

      </Card>
      
      <p className="text-center text-sm text-[var(--mute)] mt-4">
        The check repeats every 30 seconds. This is not an uptime commitment.
      </p>
    </motion.div>
  );
}
