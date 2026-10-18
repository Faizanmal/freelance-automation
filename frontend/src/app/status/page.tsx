"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { getApiBase } from "@/lib/api";

type ReadyStatus = {
  status?: string;
  checks?: {
    database?: string;
    redis?: string;
  };
};

export default function StatusPage() {
  const [liveStatus, setLiveStatus] = useState<string>("Checking...");
  const [readyStatus, setReadyStatus] = useState<ReadyStatus | null>(null);

  useEffect(() => {
    async function checkHealth() {
      try {
        const liveRes = await fetch(`${getApiBase()}/health/live`);
        if (liveRes.ok) {
          setLiveStatus("Operational");
        } else {
          setLiveStatus("Degraded");
        }
      } catch {
        setLiveStatus("Down");
      }

      try {
        const readyRes = await fetch(`${getApiBase()}/health/ready`);
        if (readyRes.ok) {
          const data = await readyRes.json();
          setReadyStatus(data);
        }
      } catch {
        setReadyStatus(null);
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
    <motion.main 
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
        <p className="mt-4 text-[var(--fog)]">Real-time status of the Signal Desk API, databases, and scrapers.</p>
      </section>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-6 pb-6 border-b border-white/5">
          <div>
            <h2 className="text-xl font-semibold text-[var(--paper)]">API endpoints</h2>
            <p className="text-sm text-[var(--mute)]">Core routing and job matching API</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm border font-medium ${getStatusColor(liveStatus)}`}>
            {liveStatus}
          </span>
        </div>

        <div className="flex items-center justify-between mb-6 pb-6 border-b border-white/5">
          <div>
            <h2 className="text-xl font-semibold text-[var(--paper)]">Database cluster</h2>
            <p className="text-sm text-[var(--mute)]">Main PostgreSQL database</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm border font-medium ${getStatusColor(readyStatus?.checks?.database || "Checking...")}`}>
            {readyStatus?.checks?.database === "ok" ? "Operational" : readyStatus ? "Degraded" : "Checking..."}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-[var(--paper)]">Background workers</h2>
            <p className="text-sm text-[var(--mute)]">Redis scraping & alert queues</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm border font-medium ${getStatusColor(readyStatus?.checks?.redis || "Checking...")}`}>
            {readyStatus?.checks?.redis === "ok" ? "Operational" : readyStatus ? "Degraded" : "Checking..."}
          </span>
        </div>
      </Card>
      
      <p className="text-center text-sm text-[var(--mute)] mt-4">
        Checks are automatically performed every 30 seconds.
      </p>
    </motion.main>
  );
}
