"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getErrorMessage } from "@/lib/errors";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  Clock,
  Globe,
  Key,
  Plus,
  RefreshCw,
  Shield,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";
import {
  createEmployerOrg,
  getEmployerOrgAuditLogs,
  getEmployerOrgDetails,
  getEmployerOrgs,
  inviteEmployerOrgMember,
  revokeEmployerOrgSeat,
  updateEmployerOrgMemberRole,
} from "@/lib/api";

export default function EmployerSettingsPage() {
  const [orgs, setOrgs] = useState<Awaited<ReturnType<typeof getEmployerOrgs>>["organizations"]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [orgDetails, setOrgDetails] = useState<Awaited<ReturnType<typeof getEmployerOrgDetails>>["organization"] | null>(null);
  const [auditLogs, setAuditLogs] = useState<Awaited<ReturnType<typeof getEmployerOrgAuditLogs>>["audit_logs"]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New Org Form
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [orgWebsite, setOrgWebsite] = useState("");
  const [orgIndustry, setOrgIndustry] = useState("technology");
  const [orgDomain, setOrgDomain] = useState("");

  // Invite Member Form
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [generatedInviteToken, setGeneratedInviteToken] = useState<string | null>(null);

  // Audit Logs Drawer
  const [showAuditLogs, setShowAuditLogs] = useState(false);

  useEffect(() => {
    loadOrganizations();
  }, []);

  useEffect(() => {
    if (selectedOrgId) {
      loadOrgDetails(selectedOrgId);
    }
  }, [selectedOrgId]);

  async function loadOrganizations() {
    try {
      setLoading(true);
      setError(null);
      const res = await getEmployerOrgs();
      setOrgs(res.organizations || []);
      if (res.organizations?.length > 0 && !selectedOrgId) {
        setSelectedOrgId(res.organizations[0].org_id);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load organizations");
    } finally {
      setLoading(false);
    }
  }

  async function loadOrgDetails(orgId: string) {
    try {
      setSaving(true);
      const res = await getEmployerOrgDetails(orgId);
      setOrgDetails(res.organization);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load organization details");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    if (!orgName.trim()) return;
    try {
      setSaving(true);
      setError(null);
      const res = await createEmployerOrg({
        name: orgName.trim(),
        website: orgWebsite.trim() || undefined,
        industry: orgIndustry,
        org_domain: orgDomain.trim() || undefined,
      });
      setMessage("Organization created successfully.");
      setShowCreateModal(false);
      setOrgName("");
      setOrgWebsite("");
      setOrgDomain("");
      await loadOrganizations();
      setSelectedOrgId(res.organization.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to create organization");
    } finally {
      setSaving(false);
    }
  }

  async function handleInviteMember(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim() || !selectedOrgId) return;
    try {
      setSaving(true);
      setError(null);
      const res = await inviteEmployerOrgMember(selectedOrgId, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      setGeneratedInviteToken(res.invitation.invitation_token);
      setMessage("Member invited. Share the invitation token or link.");
      await loadOrgDetails(selectedOrgId);
      setInviteEmail("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to invite member");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdateRole(membershipId: string, newRole: string) {
    if (!selectedOrgId) return;
    try {
      await updateEmployerOrgMemberRole(selectedOrgId, membershipId, newRole);
      setMessage("Role updated successfully.");
      await loadOrgDetails(selectedOrgId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to update role");
    }
  }

  async function handleRevokeSeat(membershipId: string) {
    if (!selectedOrgId) return;
    try {
      await revokeEmployerOrgSeat(selectedOrgId, membershipId);
      setMessage("Member seat revoked.");
      await loadOrgDetails(selectedOrgId);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to revoke seat");
    }
  }

  async function handleOpenAuditLogs() {
    if (!selectedOrgId) return;
    try {
      setSaving(true);
      const res = await getEmployerOrgAuditLogs(selectedOrgId);
      setAuditLogs(res.audit_logs || []);
      setShowAuditLogs(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load audit logs");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="size-8 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-[var(--text)]">
            Employer Organization Workspace
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Manage your company profile, domain verification, team seats, and access logs.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus className="size-4" /> New Organization
          </button>
        </div>
      </div>

      {/* Status Messages */}
      {message && (
        <div className="flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-400">
          <CheckCircle2 className="size-5 shrink-0" />
          <span>{message}</span>
        </div>
      )}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-400">
          <AlertCircle className="size-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {orgs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-12 text-center">
          <Building2 className="mx-auto size-12 text-zinc-600" />
          <h3 className="mt-4 text-base font-semibold text-[var(--text)]">No Organizations Found</h3>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Create an employer organization to invite hiring managers and source verified talent.
          </p>
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus className="size-4" /> Onboard Organization
          </button>
        </div>
      ) : (
        <>
          {/* Org Selector Pill Tabs */}
          <div className="flex flex-wrap items-center gap-2">
            {orgs.map((o) => (
              <button
                key={o.org_id}
                type="button"
                onClick={() => setSelectedOrgId(o.org_id)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                  selectedOrgId === o.org_id
                    ? "bg-[var(--accent)] text-white"
                    : "border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-hover)]"
                }`}
              >
                {o.name} ({o.role})
              </button>
            ))}
          </div>

          {orgDetails && (
            <div className="space-y-6">
              {/* Org Details Card */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-[var(--text)]">{orgDetails.name}</h2>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      Slug: <code className="text-zinc-400">{orgDetails.slug}</code> • Industry:{" "}
                      {orgDetails.industry}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {orgDetails.domain_verified ? (
                      <span className="flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/20">
                        <ShieldCheck className="size-4" /> Domain Verified
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-400 border border-amber-500/20">
                        <Shield className="size-4" /> Domain Unverified
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={handleOpenAuditLogs}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-xs font-semibold text-[var(--text)] hover:bg-[var(--border)]"
                    >
                      Audit Logs
                    </button>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs">
                  <div>
                    <span className="text-[var(--text-secondary)]">Website:</span>{" "}
                    <span className="font-semibold text-[var(--text)]">
                      {orgDetails.website || "Not specified"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-secondary)]">Corporate Domain:</span>{" "}
                    <span className="font-semibold text-[var(--text)]">
                      {orgDetails.org_domain || "Not specified"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Team Members & Seats Card */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
                  <div>
                    <h3 className="text-base font-bold text-[var(--text)]">Team Seats & Access</h3>
                    <p className="text-xs text-[var(--text-secondary)]">
                      Role-based workspace permissions: owner, admin, hiring_manager, member.
                    </p>
                  </div>
                  {["owner", "admin"].includes(orgDetails.my_role) && (
                    <button
                      type="button"
                      onClick={() => setShowInviteModal(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
                    >
                      <UserPlus className="size-3.5" /> Invite Member
                    </button>
                  )}
                </div>

                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-[var(--text-secondary)] font-semibold uppercase tracking-wider">
                        <th className="py-2.5">Email</th>
                        <th className="py-2.5">Role</th>
                        <th className="py-2.5">Seat Status</th>
                        <th className="py-2.5">Invited</th>
                        <th className="py-2.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {orgDetails.members?.map((m) => (
                        <tr key={m.id} className="text-[var(--text)]">
                          <td className="py-3 font-medium">{m.email}</td>
                          <td className="py-3">
                            {["owner", "admin"].includes(orgDetails.my_role) && m.role !== "owner" ? (
                              <select
                                value={m.role}
                                onChange={(e) => handleUpdateRole(m.id, e.target.value)}
                                className="rounded border border-[var(--border)] bg-[var(--surface-hover)] px-2 py-1 text-xs"
                              >
                                <option value="admin">Admin</option>
                                <option value="hiring_manager">Hiring Manager</option>
                                <option value="member">Member</option>
                              </select>
                            ) : (
                              <span className="capitalize font-semibold">{m.role}</span>
                            )}
                          </td>
                          <td className="py-3">
                            <span
                              className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                                m.seat_status === "active"
                                  ? "bg-emerald-500/20 text-emerald-400"
                                  : m.seat_status === "invited"
                                  ? "bg-amber-500/20 text-amber-400"
                                  : "bg-rose-500/20 text-rose-400"
                              }`}
                            >
                              {m.seat_status}
                            </span>
                          </td>
                          <td className="py-3 text-[var(--text-secondary)]">
                            {m.invited_at ? new Date(m.invited_at).toLocaleDateString() : "—"}
                          </td>
                          <td className="py-3 text-right">
                            {["owner", "admin"].includes(orgDetails.my_role) &&
                              m.role !== "owner" &&
                              m.seat_status !== "revoked" && (
                                <button
                                  type="button"
                                  onClick={() => handleRevokeSeat(m.id)}
                                  className="text-rose-400 hover:underline text-xs"
                                >
                                  Revoke Seat
                                </button>
                              )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create Org Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
              <h3 className="text-base font-bold text-[var(--text)]">Onboard New Organization</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateOrg} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-[var(--text-secondary)]">
                  Company Name
                </label>
                <input
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Apex AI Systems"
                  className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-secondary)]">
                  Website
                </label>
                <input
                  type="url"
                  value={orgWebsite}
                  onChange={(e) => setOrgWebsite(e.target.value)}
                  placeholder="https://apexai.example.com"
                  className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-secondary)]">
                  Corporate Domain
                </label>
                <input
                  type="text"
                  value={orgDomain}
                  onChange={(e) => setOrgDomain(e.target.value)}
                  placeholder="apexai.com"
                  className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
                >
                  Create Organization
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
              <h3 className="text-base font-bold text-[var(--text)]">Invite Team Member</h3>
              <button
                type="button"
                onClick={() => {
                  setShowInviteModal(false);
                  setGeneratedInviteToken(null);
                }}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            {generatedInviteToken ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-400">
                  Invitation generated successfully! Share this token with your colleague:
                </div>
                <div className="rounded-lg bg-[var(--surface-hover)] p-3 font-mono text-xs text-[var(--text)] select-all break-all">
                  {generatedInviteToken}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setShowInviteModal(false);
                    setGeneratedInviteToken(null);
                  }}
                  className="w-full rounded-lg bg-[var(--accent)] py-2 text-xs font-semibold text-white"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleInviteMember} className="mt-4 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-secondary)]">
                    Colleague&apos;s Work Email
                  </label>
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="hiring.lead@company.com"
                    className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-secondary)]">
                    Assigned Role
                  </label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
                  >
                    <option value="hiring_manager">Hiring Manager (Source & Review)</option>
                    <option value="admin">Admin (Manage Members & Seats)</option>
                    <option value="member">Member (View Only)</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="rounded-lg px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
                  >
                    Send Invitation
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Audit Logs Drawer Modal */}
      {showAuditLogs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
              <h3 className="text-base font-bold text-[var(--text)]">Organization Seat Audit Trail</h3>
              <button
                type="button"
                onClick={() => setShowAuditLogs(false)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 space-y-3">
              {auditLogs.length === 0 ? (
                <p className="text-xs text-zinc-500">No seat audit records found.</p>
              ) : (
                auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] p-3 text-xs"
                  >
                    <div>
                      <div className="font-semibold text-[var(--text)] uppercase tracking-wider text-[11px]">
                        {log.action}
                      </div>
                      <div className="text-[10px] text-[var(--text-secondary)]">
                        Actor: {log.actor_id || "System"} • IP: {log.ip_address || "local"}
                      </div>
                    </div>
                    <div className="text-right text-[10px] text-[var(--text-secondary)]">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : ""}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
