from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

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
    """Score jobs with keyword fit, freshness, client-quality proxies, and red flags."""

    def score_job(self, job: JobRecord, preferences: UserPreferences) -> JobMatch | None:
        keywords = [k.strip().lower() for k in (preferences.keywords or []) if k and k.strip()]
        excludes = [k.strip().lower() for k in (preferences.exclude_keywords or []) if k and k.strip()]
        sources = [s.strip().lower() for s in (preferences.sources or []) if s and s.strip()]

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

        if preferences.min_budget is not None and job.budget_max is not None and job.budget_max < preferences.min_budget:
            return None
        if preferences.max_budget is not None and job.budget_min is not None and job.budget_min > preferences.max_budget:
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

        if job.tags and keywords:
            keyword_set = set(keywords)
            tag_hits = [tag for tag in job.tags if str(tag).lower() in keyword_set]
            if tag_hits:
                keyword_score = min(1.0, keyword_score + 0.08 * len(tag_hits))
                reasons.append(f"tag overlap: {', '.join(map(str, tag_hits))}")

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

        threshold = preferences.match_threshold if preferences.match_threshold is not None else 0.35
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

    def rank_jobs(self, jobs: list[JobRecord], preferences: UserPreferences) -> list[JobMatch]:
        matches = [match for job in jobs if (match := self.score_job(job, preferences)) is not None]
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches

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

    def _freshness_score(self, job: JobRecord) -> float:
        stamp = job.posted_at or (job.created_at.isoformat() if job.created_at else None)
        if not stamp:
            return 0.45
        try:
            parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600)
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
        if job.seniority and any(token in job.seniority.lower() for token in ("senior", "lead", "principal", "staff")):
            score += 0.05
        enrichment = job.enrichment or {}
        if enrichment.get("skills"):
            score += 0.05
        if enrichment.get("summary"):
            score += 0.05
        return min(1.0, score)
