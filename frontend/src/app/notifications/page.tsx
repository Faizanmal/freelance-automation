"use client";

import { useEffect, useState, useTransition } from "react";
import { getNotificationHistory, sendNotification } from "@/lib/api";

const channelOptions = ["telegram", "whatsapp", "discord", "email", "slack"] as const;
const priorityOptions = ["low", "normal", "high", "urgent"] as const;

export default function NotificationsPage() {
  const [title, setTitle] = useState("New high-priority job match");
  const [body, setBody] = useState("A new job matches your profile and is ready for review.");
  const [channels, setChannels] = useState<string[]>(["email", "slack"]);
  const [priority, setPriority] = useState<string>("high");
  const [digest, setDigest] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const data = await getNotificationHistory();
        setHistory(data.items);
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
        setResult(JSON.stringify(response, null, 2));
        const data = await getNotificationHistory();
        setHistory(data.items);
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
          Compose multi-channel alerts. History is stored in the database.
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
            <pre className="mt-4 overflow-auto whitespace-pre-wrap text-xs text-[var(--mute)]">
              {result || "Send an alert to see delivery metadata here."}
            </pre>
          </div>
          <div>
            <h2 className="text-xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
              History
            </h2>
            <ul className="mt-3 space-y-2 text-sm text-[var(--fog)]">
              {history.map((item) => (
                <li key={String(item.id)} className="border-b border-white/10 pb-2">
                  <span className="text-[var(--paper)]">{String(item.title)}</span>
                  <span className="ml-2 text-xs text-[var(--mute)]">{String(item.status)}</span>
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
