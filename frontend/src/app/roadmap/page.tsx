"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { listRoadmap, voteRoadmap, type RoadmapItem } from "@/lib/api";

const VOTER_KEY = "signaldesk_voter";

function voterId() {
  const existing = localStorage.getItem(VOTER_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(VOTER_KEY, created);
  return created;
}

export default function RoadmapPage() {
  const [items, setItems] = useState<RoadmapItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  useEffect(() => {
    const id = voterId();
    listRoadmap(id)
      .then(setItems)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load the roadmap"));
  }, []);

  const vote = (key: string) => {
    setPendingKey(key);
    voteRoadmap(key, voterId())
      .then((updated) => {
        setItems((current) => current.map((item) => (item.key === updated.key ? updated : item)));
        setError(null);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not save your vote"))
      .finally(() => setPendingKey(null));
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "Completed": return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
      case "In Progress": return "text-amber-400 bg-amber-400/10 border-amber-400/20";
      case "Planned": return "text-blue-400 bg-blue-400/10 border-blue-400/20";
      default: return "text-[var(--mute)] bg-white/5 border-white/10";
    }
  };

  return (
    <motion.main
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-8 max-w-4xl mx-auto w-full pt-12"
    >
      <section className="text-center mb-8">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl font-medium"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Public Roadmap
        </motion.h1>
        <p className="mt-4 text-[var(--fog)] text-lg">
          Vote once per browser. Counts are stored on the server.
        </p>
      </section>

      <div className="flex justify-end mb-4">
        <Button onClick={() => window.location.href = "mailto:feedback@signaldesk.com?subject=Feature Request"}>
          Submit an Idea
        </Button>
      </div>

      {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}

      <div className="grid gap-4">
        {items.map((item, i) => (
          <motion.div
            key={item.key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <Card className="flex flex-col md:flex-row gap-6 p-6 items-start md:items-center justify-between border-white/10 hover:border-white/20 transition">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-xl font-semibold text-[var(--paper)]">{item.title}</h3>
                  <span className={`px-2 py-0.5 text-xs rounded-full border ${getStatusColor(item.status)}`}>
                    {item.status}
                  </span>
                </div>
                <p className="text-[var(--fog)] text-sm">{item.description}</p>
              </div>
              <Button
                variant={item.voted ? "default" : "outline"}
                disabled={item.voted || pendingKey === item.key}
                onClick={() => vote(item.key)}
                className="mt-4 md:mt-0 min-w-[88px] flex-col gap-0 py-3"
              >
                <span className="text-lg leading-none">↑</span>
                <span className="text-sm">{item.votes}</span>
              </Button>
            </Card>
          </motion.div>
        ))}
      </div>
    </motion.main>
  );
}
