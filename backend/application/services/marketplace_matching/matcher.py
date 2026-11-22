"""Phase 15 — Fair two-sided marketplace matching engine with architectural firewall.

Architectural Firewall:
- Entitlement, subscription, paid plan, or ad spend data is STRICTLY PROHIBITED
  from entering the organic matching feature vector.
- Verified in code and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Strict Organic Talent Feature Vector
# ---------------------------------------------------------------------------


class TalentFeatureVector(BaseModel):
    """Organic candidate signals for matching.

    Architectural Firewall Rule:
    Any attempt to pass paid subscription tiers, pro status, or ad spend
    raises an immediate ValueError.
    """

    freelancer_id: str
    headline: str
    skills: list[dict[str, Any]] = Field(default_factory=list)  # [{"skill_name": ..., "years": ..., "verification_status": ...}]
    min_rate: float = Field(default=0.0, ge=0.0)
    max_rate: float = Field(default=0.0, ge=0.0)
    rate_type: str = "hourly"  # "hourly", "fixed"
    currency: str = "USD"
    hours_per_week: int = Field(default=40, ge=0, le=168)
    availability_status: str = "available"  # "available", "limited", "unavailable"
    work_type_preference: str = "remote"  # "remote", "hybrid", "onsite"
    years_experience: float = Field(default=1.0, ge=0.0)
    verification_level: int = Field(default=1, ge=1, le=4)
    is_newcomer: bool = False
    portfolio_verified_count: int = Field(default=0, ge=0)
    reputation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    completed_projects_count: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def enforce_entitlement_firewall(cls, values: Any) -> Any:
        if isinstance(values, dict):
            prohibited_keys = {
                "plan",
                "is_pro",
                "subscription_status",
                "subscription_tier",
                "ad_credits",
                "sponsored",
                "stripe_subscription_id",
                "paid_tier",
                "boost_credits",
            }
            violated = prohibited_keys.intersection(values.keys())
            if violated:
                raise ValueError(
                    f"Firewall violation: Entitlement fields {sorted(violated)} "
                    f"must never be passed into the organic talent feature vector."
                )
        return values


@dataclass
class MatchBreakdown:
    skill_score: float
    budget_score: float
    availability_score: float
    work_pref_score: float
    newcomer_boost: float
    overall_score: float
    reasons: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    hard_filter_passed: bool = True


@dataclass
class CandidateMatch:
    freelancer_id: str
    headline: str
    overall_score: float
    breakdown: MatchBreakdown
    is_newcomer: bool
    verification_level: int


# ---------------------------------------------------------------------------
# Fair Marketplace Matcher
# ---------------------------------------------------------------------------


class FairMarketplaceMatcher:
    """Computes fair, explainable two-sided matches between native projects and talent profiles."""

    @classmethod
    def rank_candidates(
        cls,
        project: Any,  # NativeProject instance or dict
        talent_vectors: list[TalentFeatureVector],
        limit: int = 5,
        request_more: bool = False,
        more_reason: str | None = None,
    ) -> list[CandidateMatch]:
        """Rank candidates using organic fit, explaining hard filters and preferences.

        Shortlist size defaults to a configurable small set (e.g. 3-5 candidates).
        If request_more is true, allows expansion with a documented reason.
        If no candidates meet the fit threshold, returns 0 matches (no forced filler).
        """
        # Read project properties safely
        p_skills = getattr(project, "skills_required", None) or []
        p_min_budget = float(getattr(project, "budget_min", 0.0) or 0.0)
        p_max_budget = float(getattr(project, "budget_max", 0.0) or 0.0)
        p_rate_period = str(getattr(project, "rate_period", "fixed"))
        p_work_type = str(getattr(project, "work_type", "remote"))
        p_hours_per_week = int(getattr(project, "required_hours_per_week", 20) or 20)
        p_scope_level = str(getattr(project, "scope_level", "medium"))

        matches: list[CandidateMatch] = []

        for tv in talent_vectors:
            # 1. Hard Filters
            hard_filter_passed = True
            missing_info: list[str] = []

            # Availability hard filter: 0 hours or unavailable
            if tv.availability_status == "unavailable" or tv.hours_per_week <= 0:
                hard_filter_passed = False
                missing_info.append("Candidate marked currently unavailable")

            # Work type hard filter: onsite requirement vs remote-only preference
            if p_work_type == "onsite" and tv.work_type_preference == "remote":
                hard_filter_passed = False
                missing_info.append("Candidate prefers remote-only work, project requires on-site")

            if not hard_filter_passed:
                continue

            # 2. Skill Compatibility (Weight: 45%)
            skill_score, skill_reasons, skill_gaps = cls._evaluate_skills(p_skills, tv.skills)
            missing_info.extend(skill_gaps)

            # 3. Budget / Rate Compatibility (Weight: 25%)
            budget_score, budget_reasons = cls._evaluate_budget(
                project_min=p_min_budget,
                project_max=p_max_budget,
                project_period=p_rate_period,
                candidate_min=tv.min_rate,
                candidate_max=tv.max_rate,
                candidate_period=tv.rate_type,
            )

            # 4. Availability Compatibility (Weight: 15%)
            avail_score, avail_reasons = cls._evaluate_availability(
                project_hours=p_hours_per_week,
                candidate_hours=tv.hours_per_week,
                status=tv.availability_status,
            )

            # 5. Work Preference & Scope Compatibility (Weight: 15%)
            work_pref_score, work_reasons = cls._evaluate_work_pref(
                project_work_type=p_work_type,
                candidate_work_type=tv.work_type_preference,
                project_scope=p_scope_level,
                candidate_exp_years=tv.years_experience,
            )

            # 6. Equitable Rotation & Newcomer Exposure Boost (up to +0.06)
            # Give qualified newcomers fair exposure so they aren't drowned out by sample size alone
            newcomer_boost = 0.0
            reasons = skill_reasons + budget_reasons + avail_reasons + work_reasons

            if tv.is_newcomer and skill_score >= 0.5:
                # Apply newcomer boost
                newcomer_boost = 0.06
                reasons.append("Equitable newcomer exposure rotation applied for qualified profile")

            # Base weighted score
            raw_score = (
                (skill_score * 0.45)
                + (budget_score * 0.25)
                + (avail_score * 0.15)
                + (work_pref_score * 0.15)
                + newcomer_boost
            )
            overall_score = round(min(1.0, max(0.0, raw_score)), 4)

            # Candidate must achieve minimum threshold (0.35) to be considered a viable match
            if overall_score < 0.35:
                continue

            breakdown = MatchBreakdown(
                skill_score=round(skill_score, 4),
                budget_score=round(budget_score, 4),
                availability_score=round(avail_score, 4),
                work_pref_score=round(work_pref_score, 4),
                newcomer_boost=round(newcomer_boost, 4),
                overall_score=overall_score,
                reasons=reasons,
                missing_information=missing_info,
                hard_filter_passed=True,
            )

            matches.append(
                CandidateMatch(
                    freelancer_id=tv.freelancer_id,
                    headline=tv.headline,
                    overall_score=overall_score,
                    breakdown=breakdown,
                    is_newcomer=tv.is_newcomer,
                    verification_level=tv.verification_level,
                )
            )

        # Sort descending by overall score; tie-break deterministically by verification level, then newcomer status
        matches.sort(
            key=lambda m: (m.overall_score, m.verification_level, m.is_newcomer),
            reverse=True,
        )

        # Determine cutoff limit: default between 3 and 5
        effective_limit = limit
        if not request_more:
            effective_limit = min(5, max(3, limit))
        else:
            effective_limit = min(20, max(1, limit))

        return matches[:effective_limit]

    # -----------------------------------------------------------------------
    # Helper Evaluators
    # -----------------------------------------------------------------------

    @classmethod
    def _evaluate_skills(
        cls,
        required_skills: list[str],
        candidate_skills: list[dict[str, Any]],
    ) -> tuple[float, list[str], list[str]]:
        if not required_skills:
            return 1.0, ["Project specifies general deliverables with no specific skill restriction"], []

        req_set = {s.strip().lower() for s in required_skills if s.strip()}
        if not req_set:
            return 1.0, ["All skills compatible"], []

        matched_skills: list[str] = []
        verified_matched: list[str] = []
        unmatched: list[str] = []

        cand_skill_map = {
            s.get("skill_name", "").strip().lower(): s
            for s in candidate_skills
            if s.get("skill_name")
        }

        for r in req_set:
            if r in cand_skill_map:
                matched_skills.append(r)
                if cand_skill_map[r].get("verification_status") == "verified":
                    verified_matched.append(r)
            else:
                unmatched.append(r)

        match_ratio = len(matched_skills) / len(req_set)
        # Extra confidence bonus if skills are independently verified
        verification_ratio = len(verified_matched) / len(req_set) if req_set else 0.0
        final_skill_score = min(1.0, (match_ratio * 0.8) + (verification_ratio * 0.2))

        reasons = []
        if matched_skills:
            if verified_matched:
                reasons.append(
                    f"Verified evidence for required skill(s): {', '.join(sorted(verified_matched))}"
                )
            else:
                reasons.append(
                    f"Demonstrated background in required skill(s): {', '.join(sorted(matched_skills))}"
                )

        gaps = [f"Missing direct experience in {u}" for u in unmatched]
        return final_skill_score, reasons, gaps

    @classmethod
    def _evaluate_budget(
        cls,
        project_min: float,
        project_max: float,
        project_period: str,
        candidate_min: float,
        candidate_max: float,
        candidate_period: str,
    ) -> tuple[float, list[str]]:
        if candidate_min <= 0 and candidate_max <= 0:
            # Candidate did not specify, neutral match
            return 0.7, ["Candidate rates flexible or open to negotiation"]

        # If both are hourly or both are fixed
        if project_period == candidate_period:
            if candidate_max <= project_max and candidate_min <= project_max:
                return 1.0, [f"Rate preferences (${candidate_min:g}-${candidate_max:g}) within project budget"]
            elif candidate_min <= project_max:
                return 0.8, ["Rate overlaps with upper budget range"]
            elif candidate_min <= project_max * 1.25:
                return 0.5, ["Rate slightly exceeds budget but within 25% negotiation window"]
            else:
                return 0.2, ["Rate significantly exceeds current project budget"]

        # Estimated conversion between fixed and hourly (assuming 40 hours standard milestone)
        c_min_equiv = candidate_min * 40 if candidate_period == "hourly" else candidate_min
        p_max_equiv = project_max * 40 if project_period == "hourly" else project_max

        if c_min_equiv <= p_max_equiv:
            return 0.85, ["Rate structures compatible across period types"]
        else:
            return 0.45, ["Rate preference requires period alignment during negotiation"]

    @classmethod
    def _evaluate_availability(
        cls,
        project_hours: int,
        candidate_hours: int,
        status: str,
    ) -> tuple[float, list[str]]:
        if status == "limited":
            if candidate_hours >= project_hours:
                return 0.75, ["Candidate has limited hours available but meets project requirements"]
            return 0.5, ["Candidate has limited availability below full project hours"]

        if candidate_hours >= project_hours:
            return 1.0, [f"Available for {candidate_hours}h/wk (exceeds required {project_hours}h/wk)"]
        elif candidate_hours >= project_hours * 0.75:
            return 0.8, [f"Available for {candidate_hours}h/wk (close to required {project_hours}h/wk)"]
        else:
            return 0.5, [f"Candidate available for {candidate_hours}h/wk vs required {project_hours}h/wk"]

    @classmethod
    def _evaluate_work_pref(
        cls,
        project_work_type: str,
        candidate_work_type: str,
        project_scope: str,
        candidate_exp_years: float,
    ) -> tuple[float, list[str]]:
        pref_score = 1.0
        reasons = []

        if project_work_type == candidate_work_type:
            reasons.append(f"Work arrangement preference matches ({project_work_type})")
        elif project_work_type == "remote" or candidate_work_type == "remote":
            pref_score = 0.9
            reasons.append("Remote flexibility matches work arrangement")
        else:
            pref_score = 0.6

        # Scope fit
        scope_year_expectations = {
            "small": 1.0,
            "medium": 2.5,
            "large": 5.0,
            "enterprise": 7.0,
        }
        expected_years = scope_year_expectations.get(project_scope, 2.0)
        if candidate_exp_years >= expected_years:
            reasons.append(f"{candidate_exp_years:g}+ years experience aligns with {project_scope} scope")
        else:
            pref_score *= 0.85

        return min(1.0, pref_score), reasons
