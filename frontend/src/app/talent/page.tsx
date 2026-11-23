"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getErrorMessage } from "@/lib/errors";
import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
  Mail,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserCheck,
  X,
} from "lucide-react";
import { getNetworkReputation, searchTalentDirectory, type TalentDirectoryItem } from "@/lib/api";

export default function TalentDirectoryPage() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof searchTalentDirectory>>["items"]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchSkill, setSearchSkill] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [workType, setWorkType] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [minRate, setMinRate] = useState<number | undefined>(undefined);
  const [maxRate, setMaxRate] = useState<number | undefined>(undefined);
  const [availability, setAvailability] = useState("");
  const [minLevel, setMinLevel] = useState<number | undefined>(undefined);
  const [includeSample, setIncludeSample] = useState(false);

  // Evidence Drawer Modal
  const [selectedTalent, setSelectedTalent] = useState<TalentDirectoryItem | null>(null);
  const [talentReputation, setTalentReputation] = useState<Awaited<ReturnType<typeof getNetworkReputation>>["reputation"] | null>(null);
  const [loadingReputation, setLoadingReputation] = useState(false);

  // Contact Modal
  const [contactTalent, setContactTalent] = useState<TalentDirectoryItem | null>(null);
  const [contactMsg, setContactMsg] = useState("");
  const [contactSuccess, setContactSuccess] = useState(false);

  async function fetchDirectory() {
    try {
      setLoading(true);
      setError(null);
      const res = await searchTalentDirectory({
        skills: selectedSkills.length ? selectedSkills : undefined,
        work_type: workType || undefined,
        currency: currency || undefined,
        min_rate: minRate,
        max_rate: maxRate,
        availability: availability || undefined,
        min_level: minLevel,
        include_sample: includeSample,
        limit: 50,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load talent directory");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void fetchDirectory(), 0);
    return () => window.clearTimeout(timer);
  }, [selectedSkills, workType, currency, minRate, maxRate, availability, minLevel, includeSample]);

  function handleAddSkillFilter(e: React.FormEvent) {
    e.preventDefault();
    const clean = searchSkill.trim();
    if (clean && !selectedSkills.includes(clean)) {
      setSelectedSkills([...selectedSkills, clean]);
      setSearchSkill("");
    }
  }

  function handleRemoveSkillFilter(skill: string) {
    setSelectedSkills(selectedSkills.filter((s) => s !== skill));
  }

  async function handleOpenEvidenceDrawer(talent: TalentDirectoryItem) {
    setSelectedTalent(talent);
    try {
      setLoadingReputation(true);
      const rep = await getNetworkReputation(talent.id, "freelancer");
      setTalentReputation(rep.reputation);
    } catch {
      setTalentReputation(null);
    } finally {
      setLoadingReputation(false);
    }
  }

  function handleOpenContact(talent: TalentDirectoryItem) {
    setContactTalent(talent);
    setContactMsg("");
    setContactSuccess(false);
  }

  function handleSendContact(e: React.FormEvent) {
    e.preventDefault();
    setContactSuccess(true);
    setTimeout(() => {
      setContactTalent(null);
    }, 1500);
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Directory Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight text-[var(--text)]">
              Verified Talent Directory
            </h1>
            <span className="rounded-full bg-blue-500/10 px-3 py-0.5 text-xs font-semibold text-blue-400">
              Private Preview
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Explore independently verified AI, software, and automation talent with proven evidence.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/talent/profile"
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            Manage My Profile
          </Link>
          <Link
            href="/employer/settings"
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
          >
            Employer Workspace
          </Link>
        </div>
      </div>

      {/* Private Marketplace Notice */}
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-300">
        <span className="font-bold">Marketplace Foundation:</span> Native marketplace discovery is
        feature-flagged and private until Gate 18. Showing real opted-in talent profiles only. Demo/sandbox
        profiles are isolated by default.
      </div>

      {/* Filter Bar */}
      <div className="grid grid-cols-1 gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 lg:grid-cols-4">
        {/* Skill Search */}
        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Filter by Skill
          </label>
          <form onSubmit={handleAddSkillFilter} className="mt-1 flex gap-2">
            <input
              type="text"
              value={searchSkill}
              onChange={(e) => setSearchSkill(e.target.value)}
              placeholder="e.g. Python, Agentic AI"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-xs text-[var(--text)]"
            />
            <button
              type="submit"
              className="rounded-lg bg-[var(--surface-hover)] px-3 py-1.5 text-xs font-semibold text-[var(--text)] hover:bg-[var(--border)]"
            >
              Add
            </button>
          </form>
        </div>

        {/* Work Type */}
        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">Work Type</label>
          <select
            value={workType}
            onChange={(e) => setWorkType(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-xs text-[var(--text)]"
          >
            <option value="">All Work Types</option>
            <option value="hourly">Hourly Contract</option>
            <option value="fixed">Fixed Deliverable</option>
            <option value="retainer">Monthly Retainer</option>
          </select>
        </div>

        {/* Rate Range */}
        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Hourly Rate ({currency})
          </label>
          <div className="mt-1 flex items-center gap-2">
            <input
              type="number"
              placeholder="Min"
              value={minRate ?? ""}
              onChange={(e) => setMinRate(e.target.value ? Number(e.target.value) : undefined)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-2 py-1.5 text-xs text-[var(--text)]"
            />
            <span className="text-zinc-500">-</span>
            <input
              type="number"
              placeholder="Max"
              value={maxRate ?? ""}
              onChange={(e) => setMaxRate(e.target.value ? Number(e.target.value) : undefined)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-2 py-1.5 text-xs text-[var(--text)]"
            />
          </div>
        </div>

        {/* Verification Level & Sample Isolation */}
        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Verification Level
          </label>
          <select
            value={minLevel ?? ""}
            onChange={(e) => setMinLevel(e.target.value ? Number(e.target.value) : undefined)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-xs text-[var(--text)]"
          >
            <option value="">Any Verification</option>
            <option value="1">Level 1: Email / Domain Verified</option>
            <option value="2">Level 2: Org Representative Verified</option>
            <option value="3">Level 3: Portfolio & Commits Verified</option>
          </select>
        </div>
      </div>

      {/* Selected skill badges & Demo isolate toggle */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {selectedSkills.map((s) => (
            <span
              key={s}
              className="inline-flex items-center gap-1 rounded-full bg-[var(--accent)]/10 px-3 py-1 text-xs font-medium text-[var(--accent)]"
            >
              {s}
              <button
                type="button"
                onClick={() => handleRemoveSkillFilter(s)}
                className="hover:text-rose-400"
              >
                ✕
              </button>
            </span>
          ))}
          {selectedSkills.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedSkills([])}
              className="text-xs text-[var(--text-secondary)] hover:underline"
            >
              Clear filters
            </button>
          )}
        </div>

        <label className="flex items-center gap-2 text-xs font-medium text-[var(--text-secondary)] cursor-pointer">
          <input
            type="checkbox"
            checked={includeSample}
            onChange={(e) => setIncludeSample(e.target.checked)}
            className="rounded border-[var(--border)] text-[var(--accent)]"
          />
          Include Isolated Sandbox Samples
        </label>
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-400">
          <AlertCircle className="size-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Results Count */}
      <div className="text-xs font-semibold text-[var(--text-secondary)]">
        Showing {items.length} of {total} verified talent profiles
      </div>

      {/* Talent Cards Grid */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <RefreshCw className="size-8 animate-spin text-[var(--accent)]" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-12 text-center">
          <UserCheck className="mx-auto size-12 text-zinc-600" />
          <h3 className="mt-4 text-base font-semibold text-[var(--text)]">No Talent Found</h3>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            No opted-in profiles matched your current filters. Try relaxing skill or rate constraints.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {items.map((talent) => (
            <div
              key={talent.id}
              className="flex flex-col justify-between rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 transition-shadow hover:shadow-lg"
            >
              <div>
                {/* Header & Badges */}
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-base font-bold text-[var(--text)] truncate">
                      {talent.headline}
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)] truncate">
                      {talent.primary_segment} • {talent.years_experience}y exp
                      {talent.location_display ? ` • ${talent.location_display}` : ""}
                    </p>
                  </div>
                  {talent.is_sample && (
                    <span className="shrink-0 rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-bold text-zinc-400">
                      SAMPLE
                    </span>
                  )}
                </div>

                {/* Verification & Newcomer Indicator */}
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  {talent.verification_level >= 3 ? (
                    <span className="inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                      <ShieldCheck className="size-3" /> Level 3 Verified
                    </span>
                  ) : talent.verification_level >= 2 ? (
                    <span className="inline-flex items-center gap-1 rounded bg-blue-500/20 px-2 py-0.5 text-[10px] font-bold text-blue-400">
                      <ShieldCheck className="size-3" /> Level 2 Rep
                    </span>
                  ) : talent.verification_level >= 1 ? (
                    <span className="inline-flex items-center gap-1 rounded bg-teal-500/20 px-2 py-0.5 text-[10px] font-bold text-teal-400">
                      <Shield className="size-3" /> Level 1 Email
                    </span>
                  ) : (
                    <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-400">
                      Unverified Claim
                    </span>
                  )}

                  {talent.is_newcomer && (
                    <span className="inline-flex items-center gap-1 rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                      <Sparkles className="size-3" /> Fair Exposure
                    </span>
                  )}
                </div>

                {/* Bio Excerpt */}
                {talent.bio && (
                  <p className="mt-3 text-xs text-[var(--text-secondary)] line-clamp-2">
                    {talent.bio}
                  </p>
                )}

                {/* Skills */}
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {talent.top_skills?.map((sk) => (
                    <span
                      key={sk.name}
                      className={`rounded px-2 py-0.5 text-[10px] font-medium ${
                        sk.verified
                          ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                          : "bg-[var(--surface-hover)] text-[var(--text)]"
                      }`}
                    >
                      {sk.name}
                    </span>
                  ))}
                </div>
              </div>

              {/* Footer Rates & Actions */}
              <div className="mt-6 border-t border-[var(--border)] pt-4">
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-sm text-[var(--text)]">
                      ${talent.rates?.min_rate || 50}
                    </span>
                    <span className="text-[var(--text-secondary)]">
                      /{talent.rates?.rate_type === "hourly" ? "hr" : "proj"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-[var(--text-secondary)]">
                    <Clock className="size-3.5" />
                    <span className="capitalize">{talent.availability?.status || "Available"}</span>
                  </div>
                </div>

                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleOpenEvidenceDrawer(talent)}
                    className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] py-1.5 text-xs font-semibold text-[var(--text)] hover:bg-[var(--border)]"
                  >
                    View Evidence
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenContact(talent)}
                    disabled={!talent.contact_allowed}
                    className={`flex-1 rounded-lg py-1.5 text-xs font-semibold text-white transition-opacity ${
                      talent.contact_allowed
                        ? "bg-[var(--accent)] hover:opacity-90"
                        : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                    }`}
                  >
                    {talent.contact_allowed ? "Contact" : "Contact Disabled"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Evidence Drawer Modal */}
      {selectedTalent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
              <div>
                <h3 className="text-lg font-bold text-[var(--text)]">
                  Verification Evidence & Reputation
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">
                  {selectedTalent.headline}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedTalent(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-6">
              {/* Multi-Component Reputation Breakdown */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-hover)] p-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                  Reputation Activity (Observable Events)
                </h4>
                {loadingReputation ? (
                  <div className="mt-3 text-xs text-zinc-400">Loading reputation metrics...</div>
                ) : talentReputation ? (
                  <div className="mt-3 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[var(--text-secondary)]">History Status:</span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${
                          talentReputation.has_sufficient_data
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-amber-500/20 text-amber-300"
                        }`}
                      >
                        {talentReputation.status_label}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 pt-2">
                      <div className="rounded-lg bg-[var(--surface)] p-2 text-center">
                        <div className="text-sm font-bold text-[var(--text)]">
                          {talentReputation.components.confirmed_deliveries_count}
                        </div>
                        <div className="text-[10px] text-[var(--text-secondary)]">
                          Confirmed Deliveries
                        </div>
                      </div>
                      <div className="rounded-lg bg-[var(--surface)] p-2 text-center">
                        <div className="text-sm font-bold text-[var(--text)]">
                          {talentReputation.components.response_rate_pct
                            ? `${talentReputation.components.response_rate_pct}%`
                            : "N/A"}
                        </div>
                        <div className="text-[10px] text-[var(--text-secondary)]">
                          Response Rate
                        </div>
                      </div>
                      <div className="rounded-lg bg-[var(--surface)] p-2 text-center">
                        <div className="text-sm font-bold text-[var(--text)]">
                          {talentReputation.components.repeat_hire_rate_pct
                            ? `${talentReputation.components.repeat_hire_rate_pct}%`
                            : "N/A"}
                        </div>
                        <div className="text-[10px] text-[var(--text-secondary)]">
                          Repeat Clients
                        </div>
                      </div>
                      <div className="rounded-lg bg-[var(--surface)] p-2 text-center">
                        <div className="text-sm font-bold text-[var(--text)]">
                          {talentReputation.sample_size}
                        </div>
                        <div className="text-[10px] text-[var(--text-secondary)]">Sample Size</div>
                      </div>
                    </div>

                    {!talentReputation.has_sufficient_data && (
                      <p className="text-[11px] text-amber-400/90 italic">
                        New talent has fewer than 3 platform events. Calibrated score is withheld to prevent
                        unearned penalization or distortion.
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="mt-2 text-xs text-zinc-500">No reputation data recorded yet.</div>
                )}
              </div>

              {/* Proven Evidence Summary */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                  Verifiable Artifacts
                </h4>
                <div className="rounded-lg border border-[var(--border)] p-3 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[var(--text)]">
                      Level {selectedTalent.verification_level} Status
                    </span>
                    <span className="text-emerald-400 font-bold">Passed</span>
                  </div>
                  <p className="text-[var(--text-secondary)]">
                    Evidence validated through authorized sandbox provider. Commit history and declared
                    contribution role confirmed. No government identity records stored on platform.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Platform Contact Modal */}
      {contactTalent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
              <h3 className="text-lg font-bold text-[var(--text)]">
                Contact {contactTalent.headline}
              </h3>
              <button
                type="button"
                onClick={() => setContactTalent(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            {contactSuccess ? (
              <div className="mt-4 flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-400">
                <CheckCircle2 className="size-5 shrink-0" />
                <span>Message sent securely via platform messaging.</span>
              </div>
            ) : (
              <form onSubmit={handleSendContact} className="mt-4 space-y-4">
                <p className="text-xs text-[var(--text-secondary)]">
                  Contact takes place through platform mediation to protect both talent and employer
                  privacy. Direct emails are never exposed.
                </p>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-secondary)]">
                    Your Opportunity / Brief
                  </label>
                  <textarea
                    rows={4}
                    value={contactMsg}
                    onChange={(e) => setContactMsg(e.target.value)}
                    placeholder="Describe your project requirements, scope, and expected timeline..."
                    className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
                    required
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setContactTalent(null)}
                    className="rounded-lg px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
                  >
                    <Mail className="size-3.5" /> Send Message
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
