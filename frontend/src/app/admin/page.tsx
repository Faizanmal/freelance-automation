"use client";

import { useEffect, useState, useTransition } from "react";
import {
  adminDisableSource,
  adminGetSystemTelemetry,
  adminInventoryQuality,
  adminListSources,
  adminListUsers,
  adminModerationQueue,
  adminReviewListingReport,
  adminSourceQuarantine,
  adminTriggerStaleSweep,
  adminUpdateUser,
  me,
  type AdminSourcePolicy,
  type AdminSystemTelemetry,
  type User,
} from "@/lib/api";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function AdminDashboardPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [telemetry, setTelemetry] = useState<AdminSystemTelemetry | null>(null);
  const [sources, setSources] = useState<AdminSourcePolicy[]>([]);
  const [spendToday, setSpendToday] = useState<Record<string, number>>({});
  const [quarantineOpen, setQuarantineOpen] = useState(0);
  const [quarantinePreview, setQuarantinePreview] = useState<Array<Record<string, unknown>>>([]);
  const [modQueue, setModQueue] = useState<Array<Record<string, unknown>>>([]);
  const [quality, setQuality] = useState<Record<string, number> | null>(null);
  const [sweepResult, setSweepResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, startTransition] = useTransition();

  const loadData = () => {
    Promise.all([
      adminListUsers(),
      adminGetSystemTelemetry(),
      adminListSources(),
      adminInventoryQuality(),
      adminSourceQuarantine(10),
      adminModerationQueue("open", 20),
    ])
      .then(([usersData, telemetryData, sourcesData, qualityData, quarantineData, modData]) => {
        setUsers(usersData);
        setTelemetry(telemetryData);
        setSources(sourcesData.sources || []);
        setSpendToday(sourcesData.spend_today_usd || {});
        setQuarantineOpen(sourcesData.quarantine_open || 0);
        setQuality(qualityData.quality || null);
        setQuarantinePreview(quarantineData.items || []);
        setModQueue(modData.items || []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    me()
      .then((user) => {
        if (!user.is_superuser) {
          router.push("/");
        } else {
          loadData();
        }
      })
      .catch(() => router.push("/auth"));
  }, [router]);

  const handleUpdate = (
    userId: string,
    data: { is_active?: boolean; is_superuser?: boolean; is_verified?: boolean; plan?: string },
  ) => {
    startTransition(async () => {
      try {
        setError(null);
        const updated = await adminUpdateUser(userId, data);
        setUsers(users.map((u) => (u.id === userId ? updated : u)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update user");
      }
    });
  };

  const handleTriggerSweep = () => {
    startTransition(async () => {
      try {
        setError(null);
        setSweepResult("Running sweep…");
        const res = await adminTriggerStaleSweep();
        setSweepResult(`Sweep complete: ${res.expired_count} stale/expired jobs pruned.`);
        const updatedTelemetry = await adminGetSystemTelemetry();
        setTelemetry(updatedTelemetry);
      } catch (err) {
        setSweepResult(null);
        setError(err instanceof Error ? err.message : "Failed to trigger stale sweep");
      }
    });
  };

  const handleToggleSource = (key: string, currentlyDisabled: boolean) => {
    startTransition(async () => {
      try {
        setError(null);
        await adminDisableSource(key, !currentlyDisabled);
        const sourcesData = await adminListSources();
        setSources(sourcesData.sources || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update source");
      }
    });
  };

  const handleReviewReport = (reportId: number, outcome: string) => {
    startTransition(async () => {
      try {
        setError(null);
        await adminReviewListingReport(reportId, { outcome, status: "resolved" });
        const modData = await adminModerationQueue("open", 20);
        setModQueue(modData.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to review report");
      }
    });
  };

  if (loading) {
    return <p className="text-center text-[var(--mute)] mt-20">Loading admin dashboard...</p>;
  }

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-8 max-w-6xl mx-auto w-full pt-12 pb-16"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Admin Operations
          </h1>
          <p className="mt-2 text-[var(--fog)]">Manage platform users, subscriptions, and hunter telemetry.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={handleTriggerSweep}
          className="border-white/15"
        >
          {pending ? "Working…" : "Trigger Stale Link Sweep"}
        </Button>
      </div>

      {sweepResult && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-400">
          {sweepResult}
        </div>
      )}

      {error && <p className="text-[var(--ember)]">{error}</p>}

      {/* Telemetry Overview */}
      {telemetry && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4 border-white/10 bg-white/[0.02]">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Active Opportunities</p>
            <p className="mt-2 text-2xl font-bold text-[var(--paper)]">{telemetry.active_jobs}</p>
            <p className="mt-1 text-xs text-[var(--fog)]">{telemetry.expired_jobs} pruned as expired</p>
          </Card>
          <Card className="p-4 border-white/10 bg-white/[0.02]">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Registered Freelancers</p>
            <p className="mt-2 text-2xl font-bold text-[var(--paper)]">{telemetry.total_users}</p>
            <p className="mt-1 text-xs text-[var(--signal)]">{telemetry.pro_users} on Pro plan</p>
          </Card>
          <Card className="p-4 border-white/10 bg-white/[0.02] sm:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Opportunities by Hunter</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(telemetry.jobs_by_source).map(([source, count]) => (
                <Badge key={source} variant="outline" className="text-xs py-1 px-2 border-white/10">
                  {source}: <span className="ml-1 font-bold text-[var(--paper)]">{count}</span>
                </Badge>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Source governance */}
      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-2xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
            Source governance
          </h2>
          <p className="mt-1 text-sm text-[var(--fog)]">
            Shared inventory only. Restricted and experimental sources stay off unless licensed.
            Quarantine open: {quarantineOpen}.
          </p>
        </div>
        {quality && (
          <div className="grid gap-3 sm:grid-cols-3">
            <Card className="p-4 border-white/10 bg-white/[0.02]">
              <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Sample URL coverage</p>
              <p className="mt-2 text-xl text-[var(--paper)]">
                {Math.round((quality.url_coverage || 0) * 100)}%
              </p>
            </Card>
            <Card className="p-4 border-white/10 bg-white/[0.02]">
              <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Work-type known</p>
              <p className="mt-2 text-xl text-[var(--paper)]">
                {Math.round((quality.work_type_known_rate || 0) * 100)}%
              </p>
            </Card>
            <Card className="p-4 border-white/10 bg-white/[0.02]">
              <p className="text-xs uppercase tracking-wider text-[var(--text-muted)]">Stale marked</p>
              <p className="mt-2 text-xl text-[var(--paper)]">
                {Math.round((quality.stale_marked_rate || 0) * 100)}%
              </p>
            </Card>
          </div>
        )}
        <Card className="overflow-x-auto border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 border-b border-white/10 text-[var(--mute)]">
              <tr>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Permission</th>
                <th className="px-4 py-3 font-medium">Health</th>
                <th className="px-4 py-3 font-medium">Spend today</th>
                <th className="px-4 py-3 font-medium text-right">Control</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {sources.map((src) => (
                <tr key={src.key} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="font-medium text-[var(--paper)]">{src.display_name}</div>
                    <div className="text-[11px] text-[var(--mute)]">{src.key} · {src.category}</div>
                  </td>
                  <td className="px-4 py-3 capitalize text-[var(--fog)]">{src.permission}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="border-white/10 text-xs">
                      {src.operator_disabled ? "disabled" : src.health}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--fog)]">
                    ${(spendToday[src.key] || 0).toFixed(2)}
                    {src.daily_budget_usd != null ? ` / $${src.daily_budget_usd}` : ""}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="outline"
                      disabled={pending}
                      className="text-xs py-1 h-7"
                      onClick={() => handleToggleSource(src.key, src.operator_disabled)}
                    >
                      {src.operator_disabled ? "Enable" : "Disable"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        {quarantinePreview.length > 0 && (
          <Card className="p-4 border-white/10 bg-white/[0.02]">
            <p className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">
              Dead letter / quarantine (latest)
            </p>
            <ul className="space-y-2 text-xs text-[var(--fog)]">
              {quarantinePreview.map((item, idx) => (
                <li key={String(item.id || idx)}>
                  {String(item.source_name)} · {String(item.reason)} · {String(item.created_at || "")}
                </li>
              ))}
            </ul>
          </Card>
        )}
        <Card className="p-4 border-white/10 bg-white/[0.02]">
          <p className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">
            Listing trust moderation queue
          </p>
          <p className="text-[11px] text-[var(--fog)] mb-3">
            Human review only — reports never auto-exclude listings from a model score.
          </p>
          {modQueue.length === 0 ? (
            <p className="text-xs text-[var(--mute)]">No open reports.</p>
          ) : (
            <ul className="space-y-3 text-xs text-[var(--fog)]">
              {modQueue.map((item) => (
                <li key={String(item.id)} className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
                  <span>
                    #{String(item.id)} job {String(item.job_id)} · {String(item.reason_code)} ·{" "}
                    {String(item.severity_hint || "")}
                  </span>
                  <span className="space-x-2">
                    <Button
                      variant="outline"
                      className="text-xs py-1 h-7"
                      disabled={pending}
                      onClick={() => handleReviewReport(Number(item.id), "confirmed_concern")}
                    >
                      Confirm
                    </Button>
                    <Button
                      variant="outline"
                      className="text-xs py-1 h-7"
                      disabled={pending}
                      onClick={() => handleReviewReport(Number(item.id), "no_action")}
                    >
                      No action
                    </Button>
                    <Button
                      variant="outline"
                      className="text-xs py-1 h-7"
                      disabled={pending}
                      onClick={() => handleReviewReport(Number(item.id), "dismissed_abuse")}
                    >
                      Dismiss abuse
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {/* User Management Table */}
      <Card className="overflow-x-auto border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 border-b border-white/10 text-[var(--mute)]">
            <tr>
              <th className="px-6 py-4 font-medium">User</th>
              <th className="px-6 py-4 font-medium">Plan</th>
              <th className="px-6 py-4 font-medium">Role</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium">Verified</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-white/[0.02] transition">
                <td className="px-6 py-4">
                  <div className="font-medium text-[var(--paper)]">{user.email}</div>
                  <div className="text-[11px] text-[var(--mute)] mt-1">ID: {user.id.slice(0, 8)}...</div>
                </td>
                <td className="px-6 py-4 capitalize text-[var(--signal)]">
                  {user.plan}
                </td>
                <td className="px-6 py-4">
                  {user.is_superuser ? (
                    <span className="text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-md">Admin</span>
                  ) : (
                    <span className="text-[var(--mute)]">User</span>
                  )}
                </td>
                <td className="px-6 py-4">
                  {user.is_active ? (
                    <span className="text-blue-400 bg-blue-400/10 px-2 py-1 rounded-md">Active</span>
                  ) : (
                    <span className="text-rose-400 bg-rose-400/10 px-2 py-1 rounded-md">Suspended</span>
                  )}
                </td>
                <td className="px-6 py-4">
                  {user.is_verified ? (
                    <span className="text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-md">Yes</span>
                  ) : (
                    <span className="text-[var(--mute)]">No</span>
                  )}
                </td>
                <td className="px-6 py-4 text-right space-x-2">
                  <select 
                    value={user.plan}
                    onChange={(e) => handleUpdate(user.id, { plan: e.target.value })}
                    disabled={pending}
                    className="bg-black/40 border border-white/10 rounded-md px-2 py-1 outline-none text-[var(--fog)] text-xs"
                  >
                    <option value="free">Free</option>
                    <option value="pro">Pro</option>
                  </select>

                  {!user.is_verified ? (
                    <Button
                      variant="outline"
                      disabled={pending}
                      className="text-xs py-1 h-7"
                      onClick={() => handleUpdate(user.id, { is_verified: true })}
                    >
                      Verify
                    </Button>
                  ) : null}

                  <Button 
                    variant="outline" 
                    disabled={pending}
                    className="text-xs py-1 h-7"
                    onClick={() => handleUpdate(user.id, { is_active: !user.is_active })}
                  >
                    {user.is_active ? "Suspend" : "Activate"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </motion.div>
  );
}
