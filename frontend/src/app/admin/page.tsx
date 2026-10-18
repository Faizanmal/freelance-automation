"use client";

import { useEffect, useState, useTransition } from "react";
import { adminListUsers, adminUpdateUser, me, type User } from "@/lib/api";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function AdminDashboardPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, startTransition] = useTransition();

  const loadUsers = () => {
    adminListUsers()
      .then(setUsers)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    me()
      .then((user) => {
        if (!user.is_superuser) {
          router.push("/");
        } else {
          loadUsers();
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

  if (loading) {
    return <p className="text-center text-[var(--mute)] mt-20">Loading admin dashboard...</p>;
  }

  return (
    <motion.main 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-8 max-w-6xl mx-auto w-full pt-12"
    >
      <div>
        <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>
          Admin Dashboard
        </h1>
        <p className="mt-2 text-[var(--fog)]">Manage users, subscriptions, and system health.</p>
      </div>

      {error && <p className="text-[var(--ember)]">{error}</p>}

      <Card className="overflow-x-auto">
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
