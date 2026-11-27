"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import {
  archiveNotification,
  getInbox,
  getNotificationHistory,
  getProviderStatus,
  getTimezonePreview,
  getToken,
  markAllNotificationsRead,
  markNotificationRead,
  pauseNotifications,
  peekInboxCache,
  previewDigest,
  resumeNotifications,
  sendNotification,
  sendTestDigest,
  unarchiveNotification,
} from "@/lib/api";

type InboxFilter = "all" | "unread" | "archived";

const channelOptions = [
  "in_app",
  "email",
  "slack",
  "telegram",
  "discord",
  "whatsapp",
] as const;
type TabKind = "inbox" | "digest_preview" | "compose" | "providers";

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
  created_at?: string;
};

type InboxItem = {
  id: number;
  public_id: string;
  title: string;
  body: string;
  ai_summary?: string | null;
  priority: string;
  event_type: string;
  group_key?: string | null;
  job_id?: number | null;
  is_read: boolean;
  read_at?: string | null;
  archived_at?: string | null;
  created_at?: string | null;
  metadata?: Record<string, unknown>;
};

function statusLabel(status: string | undefined) {
  if (status === "partial") return "Partial (some channels failed)";
  if (status === "failed") return "Failed";
  if (status === "delivered") return "Delivered";
  return status || "unknown";
}

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState<TabKind>("inbox");
  const [authed] = useState(() => Boolean(getToken()));

  // Inbox state — hydrate from Desk prefetch cache when present.
  const [inboxItems, setInboxItems] = useState<InboxItem[]>(() => {
    const hit = peekInboxCache();
    return (hit?.items || []) as unknown as InboxItem[];
  });
  const [unreadCount, setUnreadCount] = useState<number>(() => {
    const hit = peekInboxCache();
    return hit?.unread_count || 0;
  });
  const [inboxFilter, setInboxFilter] = useState<InboxFilter>("all");
  /** loading | ready | error — empty state only when ready && items.length === 0 */
  const [inboxPhase, setInboxPhase] = useState<"loading" | "ready" | "error">(() =>
    peekInboxCache() ? "ready" : "loading",
  );
  const inboxFilterRef = useRef<InboxFilter>(inboxFilter);
  const inboxInFlightRef = useRef<{
    filter: InboxFilter;
    promise: Promise<{ items: InboxItem[]; unread_count: number }>;
  } | null>(null);
  /** Ids with an in-flight archive/restore — stale All refetches must not resurrect them. */
  const pendingArchiveIdsRef = useRef(new Set<number>());
  const pendingRestoreIdsRef = useRef(new Set<number>());
  const inboxEpochRef = useRef(0);

  // Digest Preview & Schedule state
  const [digestPreview, setDigestPreview] = useState<{
    title?: string;
    leads?: Array<Record<string, unknown>>;
    count?: number;
    text_body?: string;
    local_date?: string;
    schedule?: Record<string, unknown>;
  } | null>(null);
  const [scheduleData, setScheduleData] = useState<Record<string, unknown> | null>(null);
  const [, setTestSendResult] = useState<Record<string, unknown> | null>(null);
  const [isPaused, setIsPaused] = useState<boolean>(false);

  // Compose Alert state
  const [title, setTitle] = useState("New high-priority job match");
  const [body, setBody] = useState("A new job matches your profile and is ready for review.");
  const [channels, setChannels] = useState<string[]>(["email", "in_app"]);
  const [priority] = useState<string>("high");
  const [digest] = useState(false);
  const [, setResult] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Provider Status state
  const [providerData, setProviderData] = useState<Record<string, unknown> | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const loadInbox = useCallback((filter?: InboxFilter, opts?: { silent?: boolean; filterChanged?: boolean }) => {
    const activeFilter = filter ?? inboxFilterRef.current;
    const epoch = ++inboxEpochRef.current;
    // Filter changes must never keep painting the previous filter's rows
    // (Archived was flashing All items with Restore for ~2s).
    if (opts?.filterChanged) {
      setInboxItems([]);
      setInboxPhase("loading");
    } else if (!opts?.silent) {
      setInboxPhase((prev) => (prev === "ready" ? "ready" : "loading"));
    }

    const fetchForFilter = async () => {
      const data = await getInbox({
        unread_only: activeFilter === "unread",
        archived: activeFilter === "archived",
      });
      let items = (data.items || []) as unknown as InboxItem[];
      // Drop rows the user just archived (stale All refetch before DB visible).
      if (activeFilter !== "archived" && pendingArchiveIdsRef.current.size > 0) {
        items = items.filter((item) => !pendingArchiveIdsRef.current.has(item.id));
      }
      if (activeFilter === "archived" && pendingRestoreIdsRef.current.size > 0) {
        items = items.filter((item) => !pendingRestoreIdsRef.current.has(item.id));
      }
      // Defense in depth: never show the wrong archive polarity for this tab.
      if (activeFilter === "archived") {
        items = items.filter((item) => Boolean(item.archived_at));
      } else {
        items = items.filter((item) => !item.archived_at);
      }
      return {
        items,
        unread_count: data.unread_count || 0,
      };
    };

    // Never reuse an in-flight promise from a different filter.
    let promise =
      inboxInFlightRef.current?.filter === activeFilter && !opts?.filterChanged
        ? inboxInFlightRef.current.promise
        : null;
    if (!promise) {
      promise = fetchForFilter();
      inboxInFlightRef.current = { filter: activeFilter, promise };
    }

    void promise
      .then((result) => {
        // Only apply if this filter is still selected — never blank the list for a stale filter.
        if (inboxFilterRef.current !== activeFilter) return;
        if (epoch !== inboxEpochRef.current) return;
        setInboxItems(result.items);
        setUnreadCount(result.unread_count);
        setInboxPhase("ready");
      })
      .catch((err) => {
        if (inboxFilterRef.current !== activeFilter) return;
        if (epoch !== inboxEpochRef.current) return;
        setError(err instanceof Error ? err.message : "Failed loading inbox");
        setInboxPhase("error");
      })
      .finally(() => {
        if (inboxInFlightRef.current?.filter === activeFilter) {
          inboxInFlightRef.current = null;
        }
      });
  }, []);

  const loadPreview = () => {
    startTransition(async () => {
      try {
        const [prev, sched] = await Promise.all([
          previewDigest(),
          getTimezonePreview().catch(() => null),
        ]);
        setDigestPreview(prev);
        setScheduleData(sched);
        setIsPaused(Boolean(sched?.is_paused));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed loading digest preview");
      }
    });
  };

  const loadProviders = () => {
    startTransition(async () => {
      try {
        const data = await getProviderStatus();
        setProviderData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed loading provider status");
      }
    });
  };

  useEffect(() => {
    inboxFilterRef.current = inboxFilter;
  }, [inboxFilter]);

  const prevInboxFilterRef = useRef<InboxFilter | null>(null);
  useEffect(() => {
    if (!authed) return;
    const filterChanged =
      prevInboxFilterRef.current !== null && prevInboxFilterRef.current !== inboxFilter;
    prevInboxFilterRef.current = inboxFilter;
    // Defer so setState inside loadInbox is not synchronous within the effect body.
    // On filter change: clear + loading immediately — never paint the other tab's rows.
    const timer = window.setTimeout(
      () =>
        loadInbox(inboxFilter, {
          silent: !filterChanged,
          filterChanged,
        }),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [authed, inboxFilter, loadInbox]);

  useEffect(() => {
    if (!authed) return;
    if (activeTab === "digest_preview") {
      loadPreview();
    } else if (activeTab === "providers") {
      loadProviders();
    } else if (activeTab === "compose") {
      // History only needed on Compose — keep inbox first paint light.
      startTransition(async () => {
        try {
          const data = await getNotificationHistory();
          setHistory((data.items || []) as unknown as HistoryItem[]);
        } catch {
          /* optional */
        }
      });
    }
  }, [activeTab, authed, startTransition]);

  const toggleChannel = (channel: string) => {
    setChannels((current) =>
      current.includes(channel)
        ? current.filter((item) => item !== channel)
        : [...current, channel],
    );
  };

  const handleMarkRead = (id: number) => {
    const previous = inboxItems;
    // Mark read only flips that item — stays under All; leaves Unread list.
    setInboxItems((prev) => {
      if (inboxFilterRef.current === "unread") {
        return prev.filter((item) => item.id !== id);
      }
      return prev.map((item) =>
        item.id === id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item,
      );
    });
    setUnreadCount((c) => Math.max(0, c - 1));
    void (async () => {
      try {
        await markNotificationRead(id);
      } catch (err) {
        setInboxItems(previous);
        setError(err instanceof Error ? err.message : "Failed marking read");
      }
    })();
  };

  const handleMarkAllRead = () => {
    const previous = inboxItems;
    setInboxItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
    setUnreadCount(0);
    void (async () => {
      try {
        await markAllNotificationsRead();
        setSuccessMsg("All inbox notifications marked as read.");
      } catch (err) {
        setInboxItems(previous);
        setError(err instanceof Error ? err.message : "Failed marking all read");
      }
    })();
  };

  const handleArchive = (id: number) => {
    const previous = inboxItems;
    pendingArchiveIdsRef.current.add(id);
    // Optimistic remove from active view; await durable write before toasting success.
    setInboxItems((prev) => prev.filter((item) => item.id !== id));
    void (async () => {
      try {
        const res = await archiveNotification(id);
        if (!res?.archived || !res.archived_at) {
          pendingArchiveIdsRef.current.delete(id);
          setInboxItems(previous);
          setError("Archive did not persist. Try again.");
          return;
        }
        setSuccessMsg("Moved to Archived. You can restore it anytime.");
        // Confirm Archived tab from server after durable write (not before).
        if (inboxFilterRef.current === "archived") {
          loadInbox("archived", { silent: true });
        }
      } catch (err) {
        pendingArchiveIdsRef.current.delete(id);
        setInboxItems(previous);
        setError(err instanceof Error ? err.message : "Failed archiving");
      }
    })();
  };

  const handleRestore = (id: number) => {
    const previous = inboxItems;
    pendingRestoreIdsRef.current.add(id);
    pendingArchiveIdsRef.current.delete(id);
    setInboxItems((prev) => prev.filter((item) => item.id !== id));
    void (async () => {
      try {
        const res = await unarchiveNotification(id);
        if (res?.archived) {
          pendingRestoreIdsRef.current.delete(id);
          setInboxItems(previous);
          setError("Restore did not persist. Try again.");
          return;
        }
        pendingRestoreIdsRef.current.delete(id);
        setSuccessMsg("Restored to Inbox.");
        if (inboxFilterRef.current === "all") {
          loadInbox("all", { silent: true });
        }
      } catch (err) {
        pendingRestoreIdsRef.current.delete(id);
        setInboxItems(previous);
        setError(err instanceof Error ? err.message : "Failed restoring");
      }
    })();
  };

  const handleTogglePause = () => {
    startTransition(async () => {
      try {
        if (isPaused) {
          await resumeNotifications();
          setIsPaused(false);
          setSuccessMsg("Scheduled digests and alerts resumed.");
        } else {
          await pauseNotifications();
          setIsPaused(true);
          setSuccessMsg("Scheduled digests and alerts paused.");
        }
        loadPreview();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed updating pause state");
      }
    });
  };

  const handleSendTest = () => {
    startTransition(async () => {
      try {
        setError(null);
        setSuccessMsg(null);
        const res = await sendTestDigest();
        setTestSendResult(res);
        setSuccessMsg(
          `Test digest delivered to verified recipient ${res.recipient} (${res.lead_count} leads).`,
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed sending test digest");
      }
    });
  };

  const send = () => {
    if (!getToken()) {
      setError("Sign in to send alerts.");
      return;
    }
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
        const data = await getNotificationHistory();
        setHistory((data.items || []) as unknown as HistoryItem[]);
        loadInbox();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Send failed");
        setResult(null);
      }
    });
  };

  if (!authed) {
    return (
      <div className="flex flex-1 flex-col gap-8">
        <section>
          <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Alerts &amp; Inbox
          </h1>
          <p className="mt-2 max-w-2xl text-[var(--fog)]">
            Multi-channel alerts, scheduled digests, and in-app inbox are available after you sign in.
          </p>
        </section>
        <section className="rounded-2xl border border-white/10 bg-black/20 p-8 text-center">
          <h2 className="text-xl text-[var(--paper)]" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Sign in to manage notifications
          </h2>
          <Link
            href="/auth"
            className="mt-6 inline-flex rounded-full bg-[var(--signal)] px-5 py-2.5 font-semibold text-[var(--ink)]"
          >
            Sign in
          </Link>
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-8">
      <section className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Alerts &amp; In-App Inbox
          </h1>
          <p className="mt-2 max-w-2xl text-[var(--fog)]">
            User-controlled show clock: scheduled digests, high-fit immediate alerts, and accessible delivery safeguards.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/preferences?tab=alerts"
            className="text-xs font-semibold px-4 py-2 rounded-xl border border-white/15 bg-white/5 hover:bg-white/10 text-[var(--paper)]"
          >
            &larr; Notification Settings &amp; Quiet Hours
          </Link>
        </div>
      </section>

      {/* Tabs */}
      <div className="flex border-b border-white/10 gap-6">
        <button
          onClick={() => setActiveTab("inbox")}
          className={`pb-3 text-sm font-semibold relative ${
            activeTab === "inbox" ? "text-[var(--paper)] border-b-2 border-[var(--signal)]" : "text-[var(--fog)] hover:text-white"
          }`}
        >
          In-App Inbox {unreadCount > 0 && <span className="ml-1.5 px-2 py-0.5 text-xs rounded-full bg-[var(--signal)] text-[var(--ink)] font-bold">{unreadCount}</span>}
        </button>
        <button
          onClick={() => setActiveTab("digest_preview")}
          className={`pb-3 text-sm font-semibold relative ${
            activeTab === "digest_preview" ? "text-[var(--paper)] border-b-2 border-[var(--signal)]" : "text-[var(--fog)] hover:text-white"
          }`}
        >
          Scheduled Digest Preview
        </button>
        <button
          onClick={() => setActiveTab("compose")}
          className={`pb-3 text-sm font-semibold relative ${
            activeTab === "compose" ? "text-[var(--paper)] border-b-2 border-[var(--signal)]" : "text-[var(--fog)] hover:text-white"
          }`}
        >
          Multi-Channel Outbox
        </button>
        <button
          onClick={() => setActiveTab("providers")}
          className={`pb-3 text-sm font-semibold relative ${
            activeTab === "providers" ? "text-[var(--paper)] border-b-2 border-[var(--signal)]" : "text-[var(--fog)] hover:text-white"
          }`}
        >
          Provider Observability
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-200">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4 text-sm text-emerald-200">
          {successMsg}
        </div>
      )}

      {/* TAB 1: IN-APP INBOX */}
      {activeTab === "inbox" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex rounded-xl border border-white/10 bg-black/20 p-1">
              {([
                { id: "all" as const, label: "All" },
                { id: "unread" as const, label: "Unread" },
                { id: "archived" as const, label: "Archived" },
              ]).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setInboxFilter(tab.id)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                    inboxFilter === tab.id
                      ? "bg-[var(--signal)] text-[var(--ink)]"
                      : "text-[var(--fog)] hover:text-[var(--paper)]"
                  }`}
                >
                  {tab.label}
                  {tab.id === "unread" && unreadCount > 0 ? ` (${unreadCount})` : ""}
                </button>
              ))}
            </div>
            {inboxFilter !== "archived" && unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={pending}
                className="text-xs font-medium text-[var(--signal)] hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>

          {inboxPhase === "loading" ? (
            <div className="rounded-2xl border border-white/10 bg-black/20 p-12 text-center text-sm text-[var(--fog)]">
              Loading notifications…
            </div>
          ) : inboxPhase === "error" ? (
            <div className="rounded-2xl border border-red-500/20 bg-red-950/20 p-12 text-center text-sm text-red-200">
              Could not load notifications.{" "}
              <button
                type="button"
                className="underline"
                onClick={() => loadInbox(inboxFilter)}
              >
                Retry
              </button>
            </div>
          ) : inboxItems.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-black/20 p-12 text-center text-sm text-[var(--fog)]">
              {inboxFilter === "archived"
                ? "No archived notifications."
                : inboxFilter === "unread"
                  ? "No unread notifications."
                  : "No notifications in your inbox."}
            </div>
          ) : (
            <div className="space-y-3">
              {inboxItems.map((item) => (
                <div
                  key={item.id}
                  className={`rounded-2xl border p-5 transition ${
                    item.is_read
                      ? "border-white/5 bg-black/10 opacity-75"
                      : "border-[var(--signal)]/30 bg-black/30 shadow-md"
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-white/10 text-[var(--paper)]">
                          {item.event_type}
                        </span>
                        {!item.is_read && (
                          <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-[var(--signal)] text-[var(--ink)]">
                            Unread
                          </span>
                        )}
                        <span className="text-xs text-[var(--mute)]">
                          {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
                        </span>
                      </div>
                      <h3 className="text-base font-semibold text-[var(--paper)]">{item.title}</h3>
                      <p className="text-sm text-[var(--fog)] whitespace-pre-line">{item.body}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      {inboxFilter === "archived" ? (
                        <button
                          onClick={() => handleRestore(item.id)}
                          className="text-xs font-medium px-3 py-1 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 text-[var(--paper)]"
                        >
                          Restore
                        </button>
                      ) : (
                        <>
                          {!item.is_read ? (
                            <button
                              onClick={() => handleMarkRead(item.id)}
                              className="text-xs font-medium px-3 py-1 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 text-[var(--paper)]"
                            >
                              Mark Read
                            </button>
                          ) : (
                            <span className="text-xs text-[var(--mute)]">Read</span>
                          )}
                          <button
                            onClick={() => handleArchive(item.id)}
                            className="text-xs text-red-400/80 hover:text-red-400"
                          >
                            Archive
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: SCHEDULED DIGEST PREVIEW */}
      {activeTab === "digest_preview" && (
        <div className="space-y-6">
          {/* Timezone & Next Send Card */}
          <div className="rounded-2xl border border-white/15 bg-black/20 p-6 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-[var(--paper)]">
                  Delivery Clock &amp; Timezone
                </h2>
                <p className="text-xs text-[var(--fog)]">
                  Independent of continuous scraper ingestion. Digests fire strictly on your local schedule.
                </p>
              </div>
              <button
                onClick={handleTogglePause}
                disabled={pending}
                className={`text-xs font-bold px-4 py-2 rounded-xl transition ${
                  isPaused
                    ? "bg-emerald-500 text-black hover:bg-emerald-400"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30"
                }`}
              >
                {isPaused ? "Resume Deliveries" : "Pause Deliveries"}
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs pt-2 border-t border-white/10">
              <div>
                <span className="text-[var(--mute)] block">User Timezone</span>
                <span className="font-mono text-[var(--paper)]">
                  {String(scheduleData?.timezone || "UTC")} ({String(scheduleData?.utc_offset || "+00:00")})
                </span>
              </div>
              <div>
                <span className="text-[var(--mute)] block">Local Time</span>
                <span className="font-mono text-[var(--paper)]">
                  {String(scheduleData?.current_local_time || "—")}
                </span>
              </div>
              <div>
                <span className="text-[var(--mute)] block">Scheduled Time</span>
                <span className="font-mono text-[var(--paper)]">
                  {String(scheduleData?.scheduled_time_local || "09:00")}
                </span>
              </div>
              <div>
                <span className="text-[var(--mute)] block">Next Dispatch (Local)</span>
                <span className="font-mono text-[var(--signal)] font-bold">
                  {String(scheduleData?.next_send_local || "—")}
                </span>
              </div>
            </div>
          </div>

          {/* Test Send Trigger */}
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-[var(--paper)]">
                Explicit Test Dispatch
              </h3>
              <p className="text-xs text-[var(--fog)]">
                Sends a real test email containing actual eligible leads to your verified account only. No unsolicited sends.
              </p>
            </div>
            <button
              onClick={handleSendTest}
              disabled={pending}
              className="px-5 py-2.5 rounded-full bg-[var(--signal)] text-[var(--ink)] font-bold text-xs hover:opacity-90 transition shrink-0"
            >
              Send Test Digest Now &rarr;
            </button>
          </div>

          {/* Actual Eligible Leads Preview */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--paper)]">
                Preview from Ingested Inventory ({digestPreview?.count ?? 0} Eligible Leads)
              </h3>
              <span className="text-xs text-[var(--mute)]">
                Never invent counts &bull; Filtered against seen &amp; expired
              </span>
            </div>

            {(!digestPreview?.leads || digestPreview.leads.length === 0) ? (
              <div className="rounded-2xl border border-white/10 bg-black/20 p-8 text-center text-sm text-[var(--fog)]">
                No leads currently meet your minimum threshold and hunt rules. Empty digest policy will suppress outbound email.
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {digestPreview.leads.map((lead, idx) => (
                  <div
                    key={idx}
                    className="rounded-2xl border border-white/10 bg-black/20 p-5 space-y-3"
                  >
                    <div className="flex justify-between items-start">
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-white/10 text-[var(--paper)]">
                        {String(lead.source_name || "Source")}
                      </span>
                      <span className="text-xs font-bold text-teal-400">
                        {Math.round(Number(lead.score || 0.8) * 100)}% Fit
                      </span>
                    </div>
                    <h4 className="text-sm font-semibold text-[var(--paper)] line-clamp-2">
                      {String(lead.title || "Untitled")}
                    </h4>
                    <div className="text-xs text-[var(--fog)]">
                      <strong>Company:</strong> {String(lead.company || "Direct")} &bull;{" "}
                      <strong>Budget:</strong> {String(lead.budget_display || "Not specified")}
                    </div>
                    <div className="text-xs text-[var(--signal)] bg-white/5 p-2.5 rounded-lg border-l-2 border-[var(--signal)]">
                      {String(lead.why_matched || "Matched hunt criteria")}
                    </div>
                    <div className="text-right pt-1">
                      <a
                        href={String(lead.url || "#")}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-semibold text-[var(--paper)] hover:text-[var(--signal)] inline-flex items-center gap-1"
                      >
                        Inspect Opportunity &rarr;
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: MULTI-CHANNEL OUTBOX */}
      {activeTab === "compose" && (
        <section className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-4">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-2xl border border-white/15 bg-black/20 px-4 py-3 outline-none focus:border-[var(--signal)]/50 text-[var(--paper)]"
              placeholder="Notification title"
            />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="min-h-28 w-full rounded-2xl border border-white/15 bg-black/20 px-4 py-3 outline-none focus:border-[var(--signal)]/50 text-[var(--paper)]"
              placeholder="Notification body"
            />
            <div>
              <label className="text-xs text-[var(--fog)] mb-2 block font-semibold">Channels</label>
              <div className="flex flex-wrap gap-2">
                {channelOptions.map((channel) => (
                  <button
                    key={channel}
                    type="button"
                    onClick={() => toggleChannel(channel)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      channels.includes(channel)
                        ? "bg-[var(--signal)] text-[var(--ink)]"
                        : "border border-white/15 bg-white/5 text-[var(--fog)]"
                    }`}
                  >
                    {channel}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={send}
              disabled={pending}
              className="w-full rounded-full bg-[var(--signal)] py-3 font-semibold text-[var(--ink)] hover:opacity-90 transition"
            >
              Dispatch Notification
            </button>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-[var(--paper)]">Outbound History</h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {history.map((item, idx) => (
                <div key={idx} className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs">
                  <div className="flex justify-between font-semibold text-[var(--paper)]">
                    <span className="truncate">{item.title}</span>
                    <span className="shrink-0">{statusLabel(item.status)}</span>
                  </div>
                  <div className="text-[var(--mute)] mt-1">
                    {item.deliveries?.map((d) => `${d.channel}: ${d.delivered ? 'ok' : d.error || 'err'}`).join(" · ")}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* TAB 4: PROVIDER OBSERVABILITY */}
      {activeTab === "providers" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-6 space-y-4">
            <div>
              <h3 className="text-base font-semibold text-[var(--paper)]">
                Provider Health &amp; Operational Metrics
              </h3>
              <p className="text-xs text-[var(--fog)]">
                Aggregated system health and costs. Recipient identifiers are masked to safeguard privacy.
              </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs pt-4 border-t border-white/10">
              <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                <span className="text-[var(--mute)] block">Delivered (24h)</span>
                <span className="text-xl font-bold text-emerald-400 font-mono">
                  {String(
                    (providerData?.delivery_totals as Record<string, unknown>)
                      ?.delivered ?? 0,
                  )}
                </span>
              </div>
              <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                <span className="text-[var(--mute)] block">Dead Letter Queue</span>
                <span className="text-xl font-bold text-amber-400 font-mono">
                  {String(
                    (providerData?.delivery_totals as Record<string, unknown>)
                      ?.dead_letter ?? 0,
                  )}
                </span>
              </div>
              <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                <span className="text-[var(--mute)] block">Failures</span>
                <span className="text-xl font-bold text-rose-400 font-mono">
                  {String(
                    (providerData?.delivery_totals as Record<string, unknown>)
                      ?.failed ?? 0,
                  )}
                </span>
              </div>
              <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                <span className="text-[var(--mute)] block">Est. Cost (USD)</span>
                <span className="text-xl font-bold text-cyan-400 font-mono">
                  ${String(
                    (providerData?.delivery_totals as Record<string, unknown>)
                      ?.total_estimated_cost_usd ?? "0.00",
                  )}
                </span>
              </div>
            </div>

            <div className="pt-4 space-y-2">
              <h4 className="text-xs font-semibold text-[var(--paper)] uppercase tracking-wider">
                Configured Channels
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                {Object.entries((providerData?.providers as Record<string, { status?: string; configured?: boolean }>) || {}).map(([key, prov]) => (
                  <div key={key} className="flex items-center justify-between p-3 rounded-lg bg-black/40 border border-white/5">
                    <span className="capitalize">{key.replace("_", " ")}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      prov.configured ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-[var(--mute)]"
                    }`}>
                      {prov.status || "unconfigured"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
