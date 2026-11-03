"use client";

import { useEffect, useState, useTransition } from "react";
import {
  adminGetSystemTelemetry,
  adminListUsers,
  adminTriggerStaleSweep,
  adminUpdateUser,
  me,
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
  const [sweepResult, setSweepResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, startTransition] = useTransition();

  const loadData = () => {
    Promise.all([adminListUsers(), adminGetSystemTelemetry()])
      .then(([usersData, telemetryData]) => {
        setUsers(usersData);
        setTelemetry(telemetryData);
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

  if (loading) {
    return <p className="text-center text-[var(--mute)] mt-20">Loading admin dashboard...</p>;
  }

  return (
    <motion.main 
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
    </motion.main>
  );
}
