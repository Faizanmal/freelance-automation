"use client";

import { useEffect, useState, useTransition } from "react";
import { getNotificationHistory, sendNotification } from "@/lib/api";

const channelOptions = ["telegram", "whatsapp", "discord", "email", "slack"] as const;
const priorityOptions = ["low", "normal", "high", "urgent"] as const;

type DeliveryRow = {
  channel?: string;
  delivered?: boolean;
  error?: string | null;
};

type HistoryItem = {
  id?: number | string;
  title?: string;
  status?: string;
  deliveries?: DeliveryRow[];
};

function statusLabel(status: string | undefined) {
  if (status === "partial") return "Partial (some channels failed)";
  if (status === "failed") return "Failed";
  if (status === "delivered") return "Delivered";
  return status || "unknown";
}

export default function NotificationsPage() {
  const [title, setTitle] = useState("New high-priority job match");
  const [body, setBody] = useState("A new job matches your profile and is ready for review.");
  const [channels, setChannels] = useState<string[]>(["email", "slack"]);
  const [priority, setPriority] = useState<string>("high");
  const [digest, setDigest] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const data = await getNotificationHistory();
        setHistory(data.items as HistoryItem[]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Sign in to view alerts");
        setHistory([]);
      }
    });
  }, []);

  const toggleChannel = (channel: string) => {
    setChannels((current) =>
      current.includes(channel) ? current.filter((item) => item !== channel) : [...current, channel],
    );
  };

  const send = () => {
    startTransition(async () => {
      try {
        setError(null);
        const response = await sendNotification({
          title,
          body,
          channels,
          priority,
          digest,
        });
        setResult(response);
        if (response.status === "failed" || response.status === "partial") {
          const rows = Array.isArray(response.results) ? (response.results as DeliveryRow[]) : [];
          const failed = rows.filter((row) => !row.delivered);
          if (failed.length) {
            setError(
              failed
                .map((row) => `${row.channel}: ${row.error || "delivery failed"}`)
                .join(" · "),
            );
          }
        }
        const data = await getNotificationHistory();
        setHistory(data.items as HistoryItem[]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Send failed");
        setResult(null);
      }
    });
  };

  return (
    <main className="flex flex-1 flex-col gap-8">
      <section>
        <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Alerts
        </h1>
        <p className="mt-2 max-w-2xl text-[var(--fog)]">
          Compose multi-channel alerts. Unconfigured providers return provider_not_configured per channel —
          history shows partial vs failed clearly.
        </p>
      </section>

      <section className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="w-full rounded-2xl border border-white/15 bg-black/20 px-4 py-3 outline-none focus:border-[var(--signal)]/50"
            placeholder="Notification title"
          />
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            className="min-h-28 w-full rounded-2xl border border-white/15 bg-black/20 px-4 py-3 outline-none focus:border-[var(--signal)]/50"
            placeholder="Notification body"
          />
          <div className="flex flex-wrap gap-2">
            {channelOptions.map((channel) => (
              <button
                key={channel}
                type="button"
                onClick={() => toggleChannel(channel)}
                className={`rounded-full px-4 py-2 text-sm ${channels.includes(channel) ? "bg-[var(--signal)] text-[var(--ink)]" : "border border-white/15 text-[var(--fog)]"}`}
              >
                {channel}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-[var(--mute)]">Priority</label>
            <select
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
              className="rounded-full border border-white/15 bg-black/20 px-3 py-2"
            >
              {priorityOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-[var(--mute)]">
              <input type="checkbox" checked={digest} onChange={() => setDigest((value) => !value)} />
              Digest mode
            </label>
          </div>
          <button
            type="button"
            onClick={send}
            disabled={pending || channels.length === 0}
            className="rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)] disabled:opacity-60"
          >
            {pending ? "Sending…" : "Send now"}
          </button>
          {error ? <p className="text-sm text-[var(--ember)]">{error}</p> : null}
        </div>

        <div className="space-y-6 border-t border-white/10 pt-4 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
          <div>
            <h2 className="text-xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              Last response
            </h2>
            {result ? (
              <div className="mt-4 space-y-2 text-sm text-[var(--fog)]">
                <p>
                  Status:{" "}
                  <span className="text-[var(--paper)]">{statusLabel(String(result.status))}</span>
                </p>
                <ul className="space-y-1">
                  {(Array.isArray(result.results) ? (result.results as DeliveryRow[]) : []).map((row) => (
                    <li key={`${row.channel}-${row.error || "ok"}`}>
                      {row.channel}:{" "}
                      {row.delivered ? (
                        <span className="text-[var(--signal)]">delivered</span>
                      ) : (
                        <span className="text-[var(--ember)]">{row.error || "failed"}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="mt-4 text-xs text-[var(--mute)]">Send an alert to see delivery metadata here.</p>
            )}
          </div>
          <div>
            <h2 className="text-xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              History
            </h2>
            <ul className="mt-3 space-y-2 text-sm text-[var(--fog)]">
              {history.map((item) => (
                <li key={String(item.id)} className="border-b border-white/10 pb-2">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-[var(--paper)]">{String(item.title)}</span>
                    <span className="text-xs text-[var(--mute)]">{statusLabel(item.status)}</span>
                  </div>
                  {item.deliveries?.length ? (
                    <ul className="mt-1 text-xs text-[var(--mute)]">
                      {item.deliveries.map((delivery) => (
                        <li key={`${item.id}-${delivery.channel}`}>
                          {delivery.channel}:{" "}
                          {delivery.delivered ? "ok" : delivery.error || "failed"}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
              {history.length === 0 ? <li className="text-[var(--mute)]">No stored alerts yet.</li> : null}
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}
