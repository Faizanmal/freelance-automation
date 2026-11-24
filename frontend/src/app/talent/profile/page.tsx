"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getErrorMessage } from "@/lib/errors";
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  Globe,
  Lock,
  Plus,
  RefreshCw,
  Save,
  Shield,
  ShieldCheck,
  Trash2,
  Unlock,
} from "lucide-react";
import {
  addNetworkArtifact,
  addNetworkSkill,
  deleteNetworkArtifact,
  deleteNetworkSkill,
  getNetworkPreview,
  getNetworkProfile,
  publishNetworkProfile,
  runSandboxVerification,
  unpublishNetworkProfile,
  updateNetworkAvailability,
  updateNetworkConsent,
  updateNetworkProfile,
  updateNetworkRates,
  type NetworkArtifactItem,
} from "@/lib/api";

export default function TalentProfileEditorPage() {
  const [profile, setProfile] = useState<Awaited<ReturnType<typeof getNetworkProfile>>["profile"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");
  const [primarySegment, setPrimarySegment] = useState("ai_software_automation");
  const [yearsExperience, setYearsExperience] = useState(1);
  const [locationDisplay, setLocationDisplay] = useState("");

  // Skills
  const [skillName, setSkillName] = useState("");
  const [skillCategory, setSkillCategory] = useState("software");
  const [skillYears, setSkillYears] = useState(1);

  // Artifacts
  const [artifactTitle, setArtifactTitle] = useState("");
  const [artifactUrl, setArtifactUrl] = useState("");
  const [artifactType, setArtifactType] = useState("github_repo");
  const [contributionRole, setContributionRole] = useState("contributor");
  const [artifactDesc, setArtifactDesc] = useState("");

  // Availability
  const [availStatus, setAvailStatus] = useState("available");
  const [hoursPerWeek, setHoursPerWeek] = useState(40);
  const [availExpires, setAvailExpires] = useState("");

  // Rates
  const [minRate, setMinRate] = useState(60);
  const [maxRate, setMaxRate] = useState(120);
  const [currency, setCurrency] = useState("USD");
  const [rateType, setRateType] = useState("hourly");

  // Privacy Consent
  const [optInDirectory, setOptInDirectory] = useState(false);
  const [allowContact, setAllowContact] = useState(false);
  const [searchIndexingConsent, setSearchIndexingConsent] = useState(false);

  // Preview Modal
  const [previewData, setPreviewData] = useState<Awaited<ReturnType<typeof getNetworkPreview>>["preview"] | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  // Sandbox Verification Modal
  const [verificationFeedback, setVerificationFeedback] = useState<string | null>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    try {
      setLoading(true);
      setError(null);
      const res = await getNetworkProfile();
      const p = res.profile;
      setProfile(p);
      setHeadline(p.headline || "");
      setBio(p.bio || "");
      setPrimarySegment(p.primary_segment || "ai_software_automation");
      setYearsExperience(p.years_experience || 1);
      setLocationDisplay(p.location_display || "");

      if (p.availability) {
        setAvailStatus(p.availability.status || "available");
        setHoursPerWeek(p.availability.hours_per_week || 40);
        if (p.availability.expires_at) {
          setAvailExpires(p.availability.expires_at.substring(0, 10));
        }
      }

      if (p.rate_preference) {
        setMinRate(p.rate_preference.min_rate || 50);
        setMaxRate(p.rate_preference.max_rate || 120);
        setCurrency(p.rate_preference.currency || "USD");
        setRateType(p.rate_preference.rate_type || "hourly");
      }

      if (p.listing_consent) {
        setOptInDirectory(Boolean(p.listing_consent.opt_in_directory));
        setAllowContact(Boolean(p.listing_consent.allow_platform_contact));
        setSearchIndexingConsent(Boolean(p.listing_consent.search_indexing_consent));
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load talent profile");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveDetails(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setMessage(null);
      setError(null);
      await updateNetworkProfile({
        headline,
        bio,
        primary_segment: primarySegment,
        years_experience: Number(yearsExperience),
        location_display: locationDisplay,
      });
      setMessage("Profile details saved successfully.");
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to save profile details");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddSkill(e: React.FormEvent) {
    e.preventDefault();
    if (!skillName.trim()) return;
    try {
      setSaving(true);
      await addNetworkSkill({
        skill_name: skillName.trim(),
        category: skillCategory,
        years_of_experience: Number(skillYears),
      });
      setSkillName("");
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to add skill");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteSkill(id: string) {
    try {
      await deleteNetworkSkill(id);
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to remove skill");
    }
  }

  async function handleAddArtifact(e: React.FormEvent) {
    e.preventDefault();
    if (!artifactTitle.trim() || !artifactUrl.trim()) return;
    try {
      setSaving(true);
      await addNetworkArtifact({
        title: artifactTitle.trim(),
        url: artifactUrl.trim(),
        artifact_type: artifactType,
        contribution_role: contributionRole,
        description: artifactDesc.trim(),
      });
      setArtifactTitle("");
      setArtifactUrl("");
      setArtifactDesc("");
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to add portfolio artifact");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteArtifact(id: string) {
    try {
      await deleteNetworkArtifact(id);
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to remove artifact");
    }
  }

  async function handleSaveAvailabilityAndRates() {
    try {
      setSaving(true);
      setMessage(null);
      await updateNetworkAvailability({
        status: availStatus,
        hours_per_week: Number(hoursPerWeek),
        expires_at: availExpires ? new Date(availExpires).toISOString() : undefined,
      });
      await updateNetworkRates({
        min_rate: Number(minRate),
        max_rate: Number(maxRate),
        currency,
        rate_type: rateType,
      });
      setMessage("Availability and rates updated.");
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to update availability or rates");
    } finally {
      setSaving(false);
    }
  }

  async function handleSavePrivacyConsent() {
    try {
      setSaving(true);
      setMessage(null);
      await updateNetworkConsent({
        opt_in_directory: optInDirectory,
        allow_platform_contact: allowContact,
        search_indexing_consent: searchIndexingConsent,
      });
      setMessage("Privacy and consent settings saved.");
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to update privacy consent");
    } finally {
      setSaving(false);
    }
  }

  async function handleTogglePublish() {
    if (!profile) return;
    try {
      setSaving(true);
      setMessage(null);
      setError(null);
      if (profile.is_published) {
        await unpublishNetworkProfile();
        setMessage("Profile unpublished. It is now private and hidden from the directory.");
      } else {
        await publishNetworkProfile();
        setMessage("Profile published! You are now discoverable in the talent directory.");
      }
      await loadProfile();
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Publish action failed. Verify opt-in consent is enabled.");
    } finally {
      setSaving(false);
    }
  }

  async function handleOpenPreview() {
    try {
      const res = await getNetworkPreview();
      setPreviewData(res.preview);
      setShowPreview(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "") || "Failed to load preview");
    }
  }

  async function handleRunSandboxVerification(artifact: NetworkArtifactItem) {
    if (!profile) return;
    try {
      setVerificationFeedback("Verifying GitHub repository and commits via Sandbox...");
      // In sandbox mode, call verification endpoint
      const res = await runSandboxVerification(profile.id, {
        user_handle_or_email: "alice",
        target_resource: artifact.url,
        claimed_role: artifact.contribution_role,
      });
      if (res.success) {
        setVerificationFeedback(
          `Verified! Granted role: ${res.result?.verified_role} (${res.result?.commit_count} commits). Scope: read:user, public_repo.`
        );
        await loadProfile();
      } else {
        setVerificationFeedback(`Verification rejected: ${res.reason}`);
      }
    } catch (err: unknown) {
      setVerificationFeedback(getErrorMessage(err, "") || "Verification failed");
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
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-[var(--text)]">
            Freelancer Talent Profile
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Configure your verified profile, skills, availability, and privacy settings.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleOpenPreview}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-hover)]"
          >
            <Eye className="size-4" />
            Preview Public View
          </button>
          <button
            type="button"
            onClick={handleTogglePublish}
            disabled={saving}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors ${
              profile?.is_published
                ? "bg-amber-600 hover:bg-amber-700"
                : "bg-emerald-600 hover:bg-emerald-700"
            }`}
          >
            {profile?.is_published ? (
              <>
                <Lock className="size-4" /> Unpublish (Make Private)
              </>
            ) : (
              <>
                <Unlock className="size-4" /> Publish to Directory
              </>
            )}
          </button>
        </div>
      </div>

      {/* Status Banners */}
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

      {/* Directory Status Pill */}
      <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-3">
          {profile?.is_published ? (
            <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400">
              <Globe className="size-5" />
            </div>
          ) : (
            <div className="flex size-10 items-center justify-center rounded-lg bg-zinc-800 text-zinc-400">
              <Lock className="size-5" />
            </div>
          )}
          <div>
            <div className="flex items-center gap-2 font-semibold text-[var(--text)]">
              <span>Directory Status:</span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${
                  profile?.is_published
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-zinc-800 text-zinc-400"
                }`}
              >
                {profile?.is_published ? "Published (Opted In)" : "Private (Draft)"}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              {profile?.is_published
                ? "Your profile is active in the talent directory. Private personal details are strictly redacted."
                : "Private by default. Clients cannot see your profile until you grant opt-in consent and publish."}
            </p>
          </div>
        </div>
        <Link
          href="/talent"
          className="text-xs font-semibold text-[var(--accent)] hover:underline"
        >
          View Talent Directory &rarr;
        </Link>
      </div>

      {/* Section 1: Basic Information */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--text)]">Headline & Bio</h2>
        <form onSubmit={handleSaveDetails} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Professional Headline
            </label>
            <input
              type="text"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              placeholder="e.g. Senior AI Automation & Software Engineer"
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Initial Segment
              </label>
              <select
                value={primarySegment}
                onChange={(e) => setPrimarySegment(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              >
                <option value="ai_software_automation">AI / Software / Automation Services</option>
                <option value="data_engineering">Data & ML Engineering</option>
                <option value="cloud_devops">Cloud & DevOps</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Years of Experience
              </label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                value={yearsExperience}
                onChange={(e) => setYearsExperience(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Location Display
              </label>
              <input
                type="text"
                value={locationDisplay}
                onChange={(e) => setLocationDisplay(e.target.value)}
                placeholder="e.g. Remote (UTC+1)"
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Professional Bio
            </label>
            <textarea
              rows={3}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Highlight your verifiable experience, agent workflows, and core technical proficiencies."
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Save className="size-4" /> Save Details
          </button>
        </form>
      </div>

      {/* Section 2: Skills & Experience */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--text)]">Skills & Verification</h2>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Distinguish user-claimed skills from independently verified assessment evidence.
        </p>

        {/* Current skills */}
        <div className="mt-4 flex flex-wrap gap-2">
          {profile?.skills?.map((s) => (
            <div
              key={s.id}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-xs text-[var(--text)]"
            >
              <span className="font-semibold">{s.skill_name}</span>
              <span className="text-[var(--text-secondary)]">({s.years_of_experience}y)</span>
              {s.verification_status === "verified" ? (
                <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-bold text-emerald-400">
                  <ShieldCheck className="size-3" /> Verified
                </span>
              ) : (
                <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                  Claimed
                </span>
              )}
              <button
                type="button"
                onClick={() => handleDeleteSkill(s.id)}
                className="text-zinc-500 hover:text-rose-400"
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
        </div>

        {/* Add Skill Form */}
        <form onSubmit={handleAddSkill} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Skill Name
            </label>
            <input
              type="text"
              value={skillName}
              onChange={(e) => setSkillName(e.target.value)}
              placeholder="e.g. Python, Celery, LangChain"
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-sm text-[var(--text)]"
            />
          </div>
          <div className="w-40">
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Category
            </label>
            <select
              value={skillCategory}
              onChange={(e) => setSkillCategory(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-sm text-[var(--text)]"
            >
              <option value="ai_automation">AI & Automation</option>
              <option value="backend">Backend</option>
              <option value="frontend">Frontend</option>
              <option value="cloud">Cloud / Infrastructure</option>
            </select>
          </div>
          <div className="w-28">
            <label className="block text-xs font-medium text-[var(--text-secondary)]">Years</label>
            <input
              type="number"
              step="0.5"
              min="0.5"
              value={skillYears}
              onChange={(e) => setSkillYears(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-1.5 text-sm text-[var(--text)]"
            />
          </div>
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus className="size-4" /> Add Skill
          </button>
        </form>
      </div>

      {/* Section 3: Portfolio Artifacts with Contribution Role Discrimination */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--text)]">
          Portfolio Artifacts & Proven Contributions
        </h2>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Do not infer repository ownership merely from repository links. Clearly declare your
          contribution role (owner, core contributor, contributor, lead architect).
        </p>

        {/* Artifacts List */}
        <div className="mt-4 space-y-3">
          {profile?.portfolio_artifacts?.map((art) => (
            <div
              key={art.id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] p-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-[var(--text)]">{art.title}</h3>
                  <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-300">
                    Role: {art.contribution_role}
                  </span>
                  {art.verification_status === "verified" ? (
                    <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-400">
                      <ShieldCheck className="size-3.5" /> Verified Evidence
                    </span>
                  ) : (
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-400">
                      Unverified Claim
                    </span>
                  )}
                </div>
                <a
                  href={art.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block text-xs text-[var(--accent)] hover:underline truncate max-w-lg"
                >
                  {art.url}
                </a>
                {art.description && (
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">{art.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {art.verification_status !== "verified" && (
                  <button
                    type="button"
                    onClick={() => handleRunSandboxVerification(art)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/20"
                  >
                    <Shield className="size-3.5" /> Verify via Sandbox
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleDeleteArtifact(art.id)}
                  className="rounded-lg p-2 text-zinc-500 hover:bg-rose-500/10 hover:text-rose-400"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add Artifact Form */}
        <form onSubmit={handleAddArtifact} className="mt-6 space-y-3 rounded-lg border border-[var(--border)] p-4">
          <h4 className="text-sm font-semibold text-[var(--text)]">Add Portfolio Artifact</h4>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Artifact Title
              </label>
              <input
                type="text"
                value={artifactTitle}
                onChange={(e) => setArtifactTitle(e.target.value)}
                placeholder="e.g. Distributed Crawling Worker"
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Repository / Live URL
              </label>
              <input
                type="url"
                value={artifactUrl}
                onChange={(e) => setArtifactUrl(e.target.value)}
                placeholder="https://github.com/..."
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Artifact Type
              </label>
              <select
                value={artifactType}
                onChange={(e) => setArtifactType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              >
                <option value="github_repo">GitHub Repository</option>
                <option value="live_deployment">Live Web Application</option>
                <option value="case_study">Case Study</option>
                <option value="code_sample">Code Sample / Gist</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Declared Contribution Role
              </label>
              <select
                value={contributionRole}
                onChange={(e) => setContributionRole(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
              >
                <option value="contributor">Contributor (Commits/PRs)</option>
                <option value="core_contributor">Core Contributor</option>
                <option value="lead_architect">Lead Architect</option>
                <option value="owner">Project Owner / Author</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Description & Evidence Summary
            </label>
            <input
              type="text"
              value={artifactDesc}
              onChange={(e) => setArtifactDesc(e.target.value)}
              placeholder="e.g. Authored the async dispatch queue and resilience retry loop."
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </div>
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus className="size-4" /> Add Artifact
          </button>
        </form>

        {verificationFeedback && (
          <div className="mt-4 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 text-xs text-blue-300">
            {verificationFeedback}
          </div>
        )}
      </div>

      {/* Section 4: Availability & Rate Preferences */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--text)]">Availability & Rates</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Availability Status
            </label>
            <select
              value={availStatus}
              onChange={(e) => setAvailStatus(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            >
              <option value="available">Available Immediately</option>
              <option value="partially_available">Partially Available</option>
              <option value="busy">Busy / High Load</option>
              <option value="unavailable">Unavailable</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Hours Per Week
            </label>
            <input
              type="number"
              min="1"
              max="168"
              value={hoursPerWeek}
              onChange={(e) => setHoursPerWeek(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Availability Expiry Date
            </label>
            <input
              type="date"
              value={availExpires}
              onChange={(e) => setAvailExpires(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Rate Type
            </label>
            <select
              value={rateType}
              onChange={(e) => setRateType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            >
              <option value="hourly">Hourly Rate</option>
              <option value="fixed">Fixed Project</option>
              <option value="retainer">Monthly Retainer</option>
            </select>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Min Rate
            </label>
            <input
              type="number"
              min="0"
              value={minRate}
              onChange={(e) => setMinRate(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Max Rate (Optional)
            </label>
            <input
              type="number"
              min="0"
              value={maxRate}
              onChange={(e) => setMaxRate(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]">
              Currency
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-hover)] px-3 py-2 text-sm text-[var(--text)]"
            >
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
              <option value="INR">INR (₹)</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <button
            type="button"
            onClick={handleSaveAvailabilityAndRates}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <Save className="size-4" /> Save Availability & Rates
          </button>
        </div>
      </div>

      {/* Section 5: Privacy & Opt-In Settings */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--text)]">
          Privacy Settings & Opt-In Directory Consent
        </h2>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Private by default. Your profile will never appear publicly without explicit opt-in
          consent.
        </p>

        <div className="mt-6 space-y-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={optInDirectory}
              onChange={(e) => setOptInDirectory(e.target.checked)}
              className="mt-1 size-4 rounded border-[var(--border)] text-[var(--accent)]"
            />
            <div>
              <div className="font-semibold text-sm text-[var(--text)]">
                Opt-in to Public Talent Directory
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                Allow verified employers to discover your talent card and skills. Private details
                (email, phone, identity records) remain strictly hidden.
              </p>
            </div>
          </label>

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={allowContact}
              onChange={(e) => setAllowContact(e.target.checked)}
              className="mt-1 size-4 rounded border-[var(--border)] text-[var(--accent)]"
            />
            <div>
              <div className="font-semibold text-sm text-[var(--text)]">
                Allow Contact via Platform
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                Allow authenticated employers to initiate outreach messages within the platform.
                Never reveals your direct email or contact information.
              </p>
            </div>
          </label>

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={searchIndexingConsent}
              onChange={(e) => setSearchIndexingConsent(e.target.checked)}
              className="mt-1 size-4 rounded border-[var(--border)] text-[var(--accent)]"
            />
            <div>
              <div className="font-semibold text-sm text-[var(--text)]">
                Consent to Search Engine Indexing
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                When unchecked, all pages serve <code className="text-xs">X-Robots-Tag: noindex, nofollow</code> headers to keep your profile out of external search engine results.
              </p>
            </div>
          </label>
        </div>

        <div className="mt-6">
          <button
            type="button"
            onClick={handleSavePrivacyConsent}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            <ShieldCheck className="size-4" /> Save Privacy & Consent
          </button>
        </div>
      </div>

      {/* Preview Modal */}
      {showPreview && previewData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
              <h3 className="text-lg font-bold text-[var(--text)]">Public Profile Preview</h3>
              <button
                type="button"
                onClick={() => setShowPreview(false)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 space-y-4">
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
                Notice: This preview demonstrates the exact limited view seen by outside employers.
                Your email, phone, and billing data are strictly hidden.
              </div>
              <div>
                <h4 className="text-xl font-bold text-[var(--text)]">{previewData.headline}</h4>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
                  <span>Segment: {previewData.primary_segment}</span>
                  <span>•</span>
                  <span>Experience: {previewData.years_experience} years</span>
                  {previewData.location_display && (
                    <>
                      <span>•</span>
                      <span>{previewData.location_display}</span>
                    </>
                  )}
                </div>
              </div>
              {previewData.bio && (
                <p className="text-sm text-[var(--text-secondary)]">{previewData.bio}</p>
              )}
              <div className="flex flex-wrap gap-2">
                {previewData.skills?.map((s) => (
                  <span
                    key={s.id}
                    className="rounded bg-[var(--surface-hover)] px-2.5 py-1 text-xs font-semibold text-[var(--text)]"
                  >
                    {s.skill_name} ({s.years_of_experience}y)
                  </span>
                ))}
              </div>
              <div className="border-t border-[var(--border)] pt-4 text-xs text-[var(--text-secondary)]">
                <div>
                  Platform Contact:{" "}
                  <span className="font-semibold text-[var(--text)]">
                    {previewData.contact_allowed ? "Enabled" : "Disabled by Talent"}
                  </span>
                </div>
                <div>
                  Search Engine Indexing:{" "}
                  <span className="font-semibold text-[var(--text)]">
                    {previewData.search_indexing_consent ? "Permitted" : "Strictly noindex, nofollow"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
