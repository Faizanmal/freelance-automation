from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.domain.interfaces import IJobMatchService
from backend.domain.models import JobOpportunity, UserPreferences, MatchResult, ScoreResult

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


class DomainJobMatchService(IJobMatchService):
    """Score jobs against user preferences."""

    async def match(self, job: JobOpportunity, preferences: UserPreferences) -> MatchResult | None:
        keywords = [k.strip().lower() for k in (preferences.keywords or []) if k and k.strip()]
        sources = [s.strip().lower() for s in (preferences.preferred_sources or []) if s and s.strip()]

        if sources and job.source.lower() not in sources:
            return None

        # Build haystack from JobOpportunity
        tags = " ".join([str(t) for t in job.metadata.get("tags") or []])
        skills = " ".join([str(s) for s in (job.metadata.get("enrichment") or {}).get("skills", [])])
        analysis = str(job.metadata.get("analysis_summary") or "")
        seniority = str(job.metadata.get("seniority") or "")

        haystack = " ".join([
            job.title or "",
            job.description or "",
            job.company or "",
            job.location or "",
            tags,
            skills,
            analysis,
            seniority
        ]).lower()

        min_budget = preferences.min_budget
        job_max = job.metadata.get("budget_max")
        if min_budget is not None and job_max is not None:
            if float(job_max) < min_budget:
                return None

        red_flags = self._detect_red_flags(haystack)
        matched: list[str] = []
        reasons: list[str] = []

        if not keywords:
            keyword_score = 0.45
            reasons.append("no_keywords_configured")
        else:
            for keyword in keywords:
                if self._contains_keyword(haystack, keyword):
                    matched.append(keyword)
            if not matched:
                return None
            keyword_score = len(matched) / len(keywords)
            reasons.append(f"matched {len(matched)}/{len(keywords)} keywords")

        freshness = self._freshness_score(job)
        client_quality = self._client_quality_score(job)
        red_flag_penalty = min(0.35, 0.12 * len(red_flags))

        score = (0.62 * keyword_score) + (0.20 * freshness) + (0.18 * client_quality) - red_flag_penalty
        score = max(0.0, min(1.0, score))

        if freshness >= 0.75:
            reasons.append("fresh posting")
        if client_quality >= 0.7:
            reasons.append("stronger client/budget signal")
        if red_flags:
            reasons.append(f"red flags: {', '.join(red_flags)}")

        threshold = 0.35
        if score < threshold:
            return None

        score_result = ScoreResult(
            score=round(score, 3),
            reasoning="; ".join(reasons),
            matched_keywords=matched
        )

        return MatchResult(
            job=job,
            score_result=score_result,
            matched_at=datetime.utcnow()
        )

    async def batch_match(self, job_ids: list[str], user_id: str) -> list[MatchResult]:
        # Typically we would fetch the jobs and preferences from repositories here.
        # This implementation requires DI of repositories, which can be done via __init__.
        # For simplicity in this adaptation, we leave it returning empty or NotImplemented.
        raise NotImplementedError("Batch match needs repository injections")

    def _contains_keyword(self, haystack: str, keyword: str) -> bool:
        if not keyword:
            return False
        if " " in keyword or len(keyword) <= 2:
            pattern = WORD_BOUNDARY_TEMPLATE.format(keyword=re.escape(keyword))
            return re.search(pattern, haystack) is not None
        pattern = WORD_BOUNDARY_TEMPLATE.format(keyword=re.escape(keyword))
        return re.search(pattern, haystack) is not None

    def _detect_red_flags(self, haystack: str) -> list[str]:
        flags: list[str] = []
        for pattern in RED_FLAG_PATTERNS:
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                flags.append(pattern.replace(r"\b", "").replace(r"\s+", " ").replace("\\", ""))
        return flags[:5]

    def _freshness_score(self, job: JobOpportunity) -> float:
        if not job.posted_at:
            return 0.45
        age_hours = max(0.0, (datetime.now(timezone.utc) - job.posted_at.astimezone(timezone.utc)).total_seconds() / 3600)
        if age_hours <= 6:
            return 1.0
        if age_hours <= 24:
            return 0.85
        if age_hours <= 72:
            return 0.65
        if age_hours <= 168:
            return 0.4
        return 0.2

    def _client_quality_score(self, job: JobOpportunity) -> float:
        score = 0.4
        if job.company:
            score += 0.15
        
        budget_min = job.metadata.get("budget_min")
        budget_max = job.metadata.get("budget_max")
        if budget_min or budget_max:
            score += 0.2
            top = budget_max or budget_min or 0
            if top >= 2000:
                score += 0.1
            if top >= 5000:
                score += 0.05
        
        seniority = str(job.metadata.get("seniority") or "")
        if seniority and any(token in seniority.lower() for token in ("senior", "lead", "principal", "staff")):
            score += 0.05
        
        enrichment = job.metadata.get("enrichment") or {}
        if enrichment.get("skills"):
            score += 0.05
        if enrichment.get("summary"):
            score += 0.05
        return min(1.0, score)
