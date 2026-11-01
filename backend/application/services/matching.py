from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from database.models.job import JobRecord
from database.models.preference import UserPreferences

RED_FLAG_PATTERNS = (
    r"\bunpaid\b",
    r"\bequity\s+only\b",
    r"\bexposure\b",
    r"\bfor\s+exposure\b",
    r"\bcrypto\s+airdrop\b",
    r"\bsend\s+(?:me\s+)?(?:your\s+)?(?:bank|wallet|seed)\b",
    r"\burgent!!!+\b",
    r"\bguaranteed\s+income\b",
    r"\bno\s+experience\s+needed\b.*\b\$\d{4,}",
)

WORD_BOUNDARY_TEMPLATE = r"(?<![a-z0-9]){keyword}(?![a-z0-9])"

EXPERIENCE_LEVELS = frozenset({"any", "junior", "mid", "senior", "lead"})

# Tokens that signal a seniority band in title / seniority / description.
SENIORITY_BANDS: dict[str, tuple[str, ...]] = {
    "junior": ("junior", "entry", "associate", "intern", "graduate", "jr"),
    "mid": ("mid-level", "mid level", "intermediate", "midlevel", "regular"),
    "senior": ("senior", "sr."),
    "lead": ("lead", "principal", "staff", "architect", "head of", "director"),
}


@dataclass(slots=True)
class JobMatch:
    job: JobRecord
    score: float
    matched_keywords: list[str]
    reasons: list[str]
    freshness_score: float = 0.0
    client_quality_score: float = 0.0
    red_flags: list[str] | None = None


class MatchingService:
    """Score jobs with skills/keywords fit, experience, freshness, and red flags."""

    def score_job(
        self,
        job: JobRecord,
        preferences: UserPreferences,
        *,
        skill_weights: dict[str, float] | None = None,
    ) -> JobMatch | None:
        terms = self._match_terms(preferences)
        excludes = [
            k.strip().lower()
            for k in (preferences.exclude_keywords or [])
            if k and k.strip()
        ]
        sources = [
            s.strip().lower() for s in (preferences.sources or []) if s and s.strip()
        ]

        if sources and job.source_name.lower() not in sources:
            return None

        haystack = " ".join(
            [
                job.title or "",
                job.description or "",
                job.company or "",
                job.location or "",
                " ".join(job.tags or []),
                " ".join((job.enrichment or {}).get("skills") or []),
                job.analysis_summary or "",
                job.seniority or "",
            ]
        ).lower()

        for exclude in excludes:
            if self._contains_keyword(haystack, exclude):
                return None

        if (
            preferences.min_budget is not None
            and job.budget_max is not None
            and job.budget_max < preferences.min_budget
        ):
            return None
        if (
            preferences.max_budget is not None
            and job.budget_min is not None
            and job.budget_min > preferences.max_budget
        ):
            return None

        location = (getattr(preferences, "location", None) or "").strip().lower()
        if location and location not in {"remote", "anywhere", "worldwide"}:
            # Soft preference only — do not hard-filter when location is absent on the job.
            job_loc = (job.location or "").lower()
            if job_loc and location not in job_loc and "remote" not in job_loc:
                # Keep candidate but score will not get a location boost (handled below).
                pass

        red_flags = self._detect_red_flags(haystack)
        matched: list[str] = []
        reasons: list[str] = []

        if not terms:
            keyword_score = 0.45
            reasons.append("no_skills_configured")
        else:
            for term in terms:
                if self._contains_keyword(haystack, term):
                    matched.append(term)
            if not matched:
                return None
            keyword_score = len(matched) / len(terms)
            reasons.append(f"matched {len(matched)}/{len(terms)} skills")

        if job.tags and terms:
            term_set = set(terms)
            tag_hits = [tag for tag in job.tags if str(tag).lower() in term_set]
            if tag_hits:
                keyword_score = min(1.0, keyword_score + 0.08 * len(tag_hits))
                reasons.append(f"tag overlap: {', '.join(map(str, tag_hits))}")

        freshness = self._freshness_score(job)
        client_quality = self._client_quality_score(job)
        red_flag_penalty = min(0.35, 0.12 * len(red_flags))
        experience_delta, experience_reason = self._experience_adjustment(
            preferences, haystack, job.seniority
        )
        location_boost = 0.0
        if location:
            job_loc = (job.location or "").lower()
            if location in job_loc or (
                location in {"remote", "anywhere", "worldwide"}
                and ("remote" in job_loc or "worldwide" in job_loc or not job_loc)
            ):
                location_boost = 0.05
                reasons.append("location fit")

        engagement_delta, engagement_reason = self._engagement_adjustment(
            preferences, job
        )
        quality_penalty, quality_reason = self._quality_penalty(job)
        feedback_delta, feedback_reason = self._feedback_adjustment(
            job, skill_weights or {}
        )

        score = (
            (0.54 * keyword_score)
            + (0.16 * freshness)
            + (0.14 * client_quality)
            + experience_delta
            + engagement_delta
            + location_boost
            + feedback_delta
            - red_flag_penalty
            - quality_penalty
        )
        score = max(0.0, min(1.0, score))

        if experience_reason:
            reasons.append(experience_reason)
        if engagement_reason:
            reasons.append(engagement_reason)
        if quality_reason:
            reasons.append(quality_reason)
        if feedback_reason:
            reasons.append(feedback_reason)
        if freshness >= 0.75:
            reasons.append("fresh posting")
        if client_quality >= 0.7:
            reasons.append("stronger client/budget signal")
        if red_flags:
            reasons.append(f"red flags: {', '.join(red_flags)}")

        threshold = (
            preferences.match_threshold
            if preferences.match_threshold is not None
            else 0.35
        )
        if score < threshold:
            return None

        return JobMatch(
            job=job,
            score=round(score, 3),
            matched_keywords=matched,
            reasons=reasons,
            freshness_score=round(freshness, 3),
            client_quality_score=round(client_quality, 3),
            red_flags=red_flags,
        )

    def rank_jobs(
        self,
        jobs: list[JobRecord],
        preferences: UserPreferences,
        *,
        skill_weights: dict[str, float] | None = None,
    ) -> list[JobMatch]:
        matches = [
            match
            for job in jobs
            if (
                match := self.score_job(
                    job, preferences, skill_weights=skill_weights
                )
            )
            is not None
        ]
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches

    def _match_terms(self, preferences: UserPreferences) -> list[str]:
        """Skills first, then extra keywords/requirements — de-duplicated."""
        skills = [
            k.strip().lower()
            for k in (getattr(preferences, "skills", None) or [])
            if k and str(k).strip()
        ]
        keywords = [
            k.strip().lower()
            for k in (preferences.keywords or [])
            if k and str(k).strip()
        ]
        # Legacy rows often only have keywords; treat them as skills.
        ordered = skills + keywords if skills else keywords
        seen: set[str] = set()
        terms: list[str] = []
        for term in ordered:
            if term not in seen:
                seen.add(term)
                terms.append(term)
        return terms

    def _experience_adjustment(
        self,
        preferences: UserPreferences,
        haystack: str,
        seniority: str | None,
    ) -> tuple[float, str | None]:
        raw = (getattr(preferences, "experience_level", None) or "any").strip().lower()
        level = raw if raw in EXPERIENCE_LEVELS else "any"
        if level == "any":
            return 0.0, None

        detected = self._detect_seniority_band(haystack, seniority)
        if detected is None:
            return 0.0, None
        if detected == level:
            return 0.1, f"experience fit ({level})"

        order = ("junior", "mid", "senior", "lead")
        try:
            distance = abs(order.index(detected) - order.index(level))
        except ValueError:
            return 0.0, None
        if distance == 1:
            return -0.04, f"nearby experience ({detected} vs {level})"
        return -0.12, f"experience mismatch ({detected} vs {level})"

    def _engagement_adjustment(
        self, preferences: UserPreferences, job: JobRecord
    ) -> tuple[float, str | None]:
        enrichment = job.enrichment or {}
        engagement = str(
            enrichment.get("engagement_type") or enrichment.get("project_type") or ""
        ).lower()
        if not engagement or engagement == "unknown":
            return 0.0, None
        freelance_focus = bool(getattr(preferences, "freelance_focus", True))
        if freelance_focus and engagement in {"freelance", "contract"}:
            return 0.06, f"engagement fit ({engagement})"
        if freelance_focus and engagement == "full_time":
            return -0.08, "full-time vs freelance focus"
        return 0.0, None

    def _quality_penalty(self, job: JobRecord) -> tuple[float, str | None]:
        flags = list((job.enrichment or {}).get("quality_flags") or [])
        if not flags:
            return 0.0, None
        penalty = min(0.25, 0.08 * len(flags))
        return penalty, f"quality flags: {', '.join(flags)}"

    def _feedback_adjustment(
        self, job: JobRecord, skill_weights: dict[str, float]
    ) -> tuple[float, str | None]:
        if not skill_weights:
            return 0.0, None
        enrichment = job.enrichment or {}
        skills = {
            str(s).lower()
            for s in list(enrichment.get("skills") or []) + list(job.tags or [])
            if s
        }
        delta = 0.0
        hits: list[str] = []
        for skill in skills:
            weight = skill_weights.get(skill)
            if weight:
                delta += weight
                hits.append(skill)
        delta = max(-0.15, min(0.15, delta))
        if not hits or abs(delta) < 0.02:
            return 0.0, None
        label = "saved-skill boost" if delta > 0 else "skipped-skill penalty"
        return delta, f"{label}: {', '.join(hits[:4])}"

    def _detect_seniority_band(
        self, haystack: str, seniority: str | None
    ) -> str | None:
        text = f"{seniority or ''} {haystack}".lower()
        # Check lead before senior so "staff/principal" does not also count as senior-only.
        for band in ("lead", "senior", "junior", "mid"):
            for token in SENIORITY_BANDS[band]:
                if token in text:
                    return band
        return None

    def _contains_keyword(self, haystack: str, keyword: str) -> bool:
        if not keyword:
            return False
        pattern = WORD_BOUNDARY_TEMPLATE.format(keyword=re.escape(keyword))
        return re.search(pattern, haystack) is not None

    def _detect_red_flags(self, haystack: str) -> list[str]:
        flags: list[str] = []
        for pattern in RED_FLAG_PATTERNS:
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                flags.append(
                    pattern.replace(r"\b", "").replace(r"\s+", " ").replace("\\", "")
                )
        return flags[:5]

    def _freshness_score(self, job: JobRecord) -> float:
        stamp = job.posted_at or (
            job.created_at.isoformat() if job.created_at else None
        )
        if not stamp:
            return 0.45
        try:
            parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age_hours = max(
                0.0,
                (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds() / 3600,
            )
        except ValueError:
            return 0.45
        if age_hours <= 6:
            return 1.0
        if age_hours <= 24:
            return 0.85
        if age_hours <= 72:
            return 0.65
        if age_hours <= 168:
            return 0.4
        return 0.2

    def _client_quality_score(self, job: JobRecord) -> float:
        score = 0.4
        if job.company:
            score += 0.15
        if job.budget_min or job.budget_max:
            score += 0.2
            top = job.budget_max or job.budget_min or 0
            if top >= 2000:
                score += 0.1
            if top >= 5000:
                score += 0.05
        if job.seniority and any(
            token in job.seniority.lower()
            for token in ("senior", "lead", "principal", "staff")
        ):
            score += 0.05
        enrichment = job.enrichment or {}
        if enrichment.get("skills"):
            score += 0.05
        if enrichment.get("summary"):
            score += 0.05
        return min(1.0, score)
