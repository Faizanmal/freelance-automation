from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from app.ingestion.sources import MARKETPLACE_SOURCES, SOURCE_ATTRIBUTION

from backend.application.services.listing_presentation import make_excerpt
from backend.application.services.matching import JobMatch, MatchingService
from database.models.job import JobRecord
from database.models.preference import UserPreferences

Action = Literal["draft_bid", "watch", "skip"]

FREELANCE_POSITIVE = (
    (r"\bfreelance\b", "Freelance-labeled"),
    (r"\bcontractor\b", "Contractor-friendly"),
    (r"\bcontract\b", "Contract role"),
    (r"\bhourly\b", "Hourly engagement"),
    (r"\bfixed[\s-]?price\b", "Fixed-price project"),
    (r"\bshort[\s-]?term\b", "Short-term"),
    (r"\bproject[\s-]?based\b", "Project-based"),
    (r"\bgig\b", "Gig-style work"),
    (r"\bindependent\s+contractor\b", "Independent contractor"),
    (r"\bpart[\s-]?time\b", "Part-time flexibility"),
)

FREELANCE_NEGATIVE = (
    (r"\bfull[\s-]?time\b", "Full-time employee posting"),
    (r"\bw-?2\b", "W2 employment"),
    (r"\bsalary\b", "Salary role"),
    (r"\bbenefits\s+package\b", "Employee benefits package"),
    (r"\bpermanent\b", "Permanent hire"),
    (r"\b401\(?k\)?\b", "Employee benefits signal"),
    (r"\bpaternity\s+leave\b", "Employee benefits signal"),
    (r"\bopen\s+enrollment\b", "Employee benefits signal"),
)

REMOTE_PATTERNS = (
    (r"\bremote\b", "Remote-friendly"),
    (r"\bworldwide\b", "Worldwide / async-friendly"),
    (r"\bwork\s+from\s+home\b", "Work from home"),
    (r"\bdistributed\b", "Distributed team"),
)


@dataclass(slots=True)
class LeadFinding:
    job: JobRecord
    score: float
    why: str
    signals: list[str]
    risks: list[str]
    action: Action
    matched_keywords: list[str]
    freshness_score: float
    client_quality_score: float
    red_flags: list[str]
    freelance_fit: float = 0.0
    freelance_benefits: list[str] | None = None
    employment_risks: list[str] | None = None


class LeadFindingsService:
    """Turn ranked matches into decision-oriented lead findings."""

    def __init__(self, matcher: MatchingService | None = None) -> None:
        self.matcher = matcher or MatchingService()

    def build(
        self,
        jobs: list[JobRecord],
        preferences: UserPreferences,
        *,
        limit: int = 10,
        freelance_focus: bool = False,
        skip_job_ids: set[int] | None = None,
        saved_job_ids: set[int] | None = None,
        include_skipped: bool = False,
    ) -> dict[str, Any]:
        skipped = skip_job_ids or set()
        saved = saved_job_ids or set()
        matches = self.matcher.rank_jobs(jobs, preferences)
        findings = [
            self._from_match(match, freelance_focus=freelance_focus)
            for match in matches
        ]

        if freelance_focus:
            findings = [
                finding
                for finding in findings
                if finding.freelance_fit >= 0.35
                or finding.job.source_name in MARKETPLACE_SOURCES
                or finding.job.source_name == "serpapi_freelance"
            ]

        if not include_skipped and skipped:
            findings = [
                finding for finding in findings if finding.job.id not in skipped
            ]

        def _sort_key(item: LeadFinding) -> tuple[float, float, float]:
            boost = 1.0 if item.job.id in saved else 0.0
            if freelance_focus:
                return (
                    boost,
                    (item.freelance_fit * 0.55) + (item.score * 0.45),
                    item.score,
                )
            return (boost, item.score, item.freshness_score)

        findings.sort(key=_sort_key, reverse=True)

        findings = findings[: max(1, min(limit, 25))] if findings else []
        action_counts = {"draft_bid": 0, "watch": 0, "skip": 0}
        for finding in findings:
            action_counts[finding.action] += 1
        items = []
        for finding in findings:
            payload = self.to_dict(finding)
            if finding.job.id in saved:
                payload["user_status"] = "save"
            elif finding.job.id in skipped:
                payload["user_status"] = "skip"
            else:
                payload["user_status"] = None
            items.append(payload)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_scanned": len(jobs),
            "total_matched": len(matches),
            "total_findings": len(findings),
            "freelance_focus": freelance_focus,
            "action_counts": action_counts,
            "keywords": list(preferences.keywords or []),
            "items": items,
        }

    def _from_match(self, match: JobMatch, *, freelance_focus: bool) -> LeadFinding:
        red_flags = list(match.red_flags or [])
        benefits, employment_risks, freelance_fit = self._freelance_profile(match.job)
        score = match.score
        if freelance_focus:
            score = max(
                0.0, min(1.0, round((0.55 * match.score) + (0.45 * freelance_fit), 3))
            )
            if employment_risks and match.job.source_name not in MARKETPLACE_SOURCES:
                score = max(
                    0.0, round(score - min(0.25, 0.08 * len(employment_risks)), 3)
                )

        signals = self._signals(match)
        if freelance_focus and benefits:
            signals = [*benefits[:2], *signals][:7]
        risks = self._risks(match, red_flags)
        if freelance_focus and employment_risks:
            risks = [*employment_risks[:2], *risks][:6]

        action = self._action(
            score,
            red_flags,
            match.freshness_score,
            freelance_focus=freelance_focus,
            freelance_fit=freelance_fit,
            employment_risks=employment_risks,
            source_name=match.job.source_name,
        )
        finding = LeadFinding(
            job=match.job,
            score=score,
            why="",
            signals=signals,
            risks=risks,
            action=action,
            matched_keywords=list(match.matched_keywords or []),
            freshness_score=match.freshness_score,
            client_quality_score=match.client_quality_score,
            red_flags=red_flags,
            freelance_fit=freelance_fit,
            freelance_benefits=benefits,
            employment_risks=employment_risks,
        )
        return replace(
            finding,
            why=self._why(
                match,
                action,
                signals,
                risks,
                freelance_focus=freelance_focus,
                benefits=benefits,
            ),
        )

    def _freelance_profile(self, job: JobRecord) -> tuple[list[str], list[str], float]:
        haystack = " ".join(
            [
                job.title or "",
                job.description or "",
                job.company or "",
                job.location or "",
                " ".join(job.tags or []),
                " ".join((job.enrichment or {}).get("skills") or []),
                job.seniority or "",
                job.source_name or "",
            ]
        ).lower()

        benefits: list[str] = []
        for pattern, label in FREELANCE_POSITIVE:
            if (
                re.search(pattern, haystack, flags=re.IGNORECASE)
                and label not in benefits
            ):
                benefits.append(label)
        for pattern, label in REMOTE_PATTERNS:
            if (
                re.search(pattern, haystack, flags=re.IGNORECASE)
                and label not in benefits
            ):
                benefits.append(label)

        employment_risks: list[str] = []
        for pattern, label in FREELANCE_NEGATIVE:
            if (
                re.search(pattern, haystack, flags=re.IGNORECASE)
                and label not in employment_risks
            ):
                employment_risks.append(label)

        fit = 0.25
        source = (job.source_name or "").lower()
        if source in MARKETPLACE_SOURCES or source == "serpapi_freelance":
            fit += 0.45
            label = (
                "Web freelance discovery"
                if source == "serpapi_freelance"
                else "Marketplace project board"
            )
            if label not in benefits:
                benefits.insert(0, label)
        elif source == "serpapi_jobs":
            fit += 0.1
            if "Google Jobs discovery" not in benefits:
                benefits.insert(0, "Google Jobs discovery")
        elif source == "serpapi_companies":
            fit += 0.2
            if "Company careers page" not in benefits:
                benefits.insert(0, "Company careers page")
        elif source == "serpapi_maps":
            fit += 0.25
            if "Local outreach lead" not in benefits:
                benefits.insert(0, "Local outreach lead")
        elif source in {
            "remoteok",
            "arbeitnow",
            "himalayas",
            "jobicy",
            "remotive",
            "weworkremotely",
        }:
            fit += 0.05

        fit += min(0.28, 0.07 * len(benefits))
        if job.budget_min or job.budget_max:
            fit += 0.12
            if "Clear budget signal" not in benefits:
                benefits.append("Clear budget signal")
        if job.location and re.search(
            r"remote|worldwide|anywhere", job.location, flags=re.IGNORECASE
        ):
            fit += 0.05
        fit -= min(0.35, 0.1 * len(employment_risks))
        if (
            source not in MARKETPLACE_SOURCES
            and employment_risks
            and not any(
                token in " ".join(benefits).lower()
                for token in ("freelance", "contract", "hourly", "fixed")
            )
        ):
            fit -= 0.15

        return benefits[:6], employment_risks[:4], max(0.0, min(1.0, round(fit, 3)))

    def _signals(self, match: JobMatch) -> list[str]:
        signals: list[str] = []
        if match.matched_keywords:
            signals.append(f"Skills overlap: {', '.join(match.matched_keywords[:4])}")
        if match.freshness_score >= 0.85:
            signals.append("Posted in the last day")
        elif match.freshness_score >= 0.65:
            signals.append("Still relatively fresh")
        if match.client_quality_score >= 0.7:
            signals.append("Stronger client/budget signal")
        job = match.job
        if job.budget_min or job.budget_max:
            low = job.budget_min
            high = job.budget_max
            if low and high:
                signals.append(f"Budget range ${low:,.0f}–${high:,.0f}")
            elif high:
                signals.append(f"Budget up to ${high:,.0f}")
            elif low:
                signals.append(f"Budget from ${low:,.0f}")
        if job.company:
            signals.append(f"Named client: {job.company}")
        source = SOURCE_ATTRIBUTION.get(job.source_name, job.source_name)
        if source:
            signals.append(f"Source: {source}")
        return signals[:6]

    def _risks(self, match: JobMatch, red_flags: list[str]) -> list[str]:
        risks: list[str] = []
        for flag in red_flags[:4]:
            risks.append(f"Red flag pattern: {flag}")
        job = match.job
        if not (job.budget_min or job.budget_max):
            risks.append("No explicit budget listed")
        if match.freshness_score <= 0.4:
            risks.append("Older posting — competition may be high")
        if match.score < 0.45:
            risks.append("Borderline fit vs your preferences")
        return risks[:5]

    def _action(
        self,
        score: float,
        red_flags: list[str],
        freshness: float,
        *,
        freelance_focus: bool,
        freelance_fit: float,
        employment_risks: list[str],
        source_name: str,
    ) -> Action:
        if len(red_flags) >= 2 or (red_flags and score < 0.55):
            return "skip"
        if freelance_focus:
            if (
                source_name not in MARKETPLACE_SOURCES
                and len(employment_risks) >= 2
                and freelance_fit < 0.5
            ):
                return "skip"
            if freelance_fit >= 0.55 and score >= 0.5 and not red_flags:
                return "draft_bid"
            if freelance_fit < 0.4 and source_name not in MARKETPLACE_SOURCES:
                return "watch" if score >= 0.55 else "skip"
        if score >= 0.55 and not red_flags and freshness >= 0.4:
            return "draft_bid"
        if score >= 0.7 and len(red_flags) <= 1:
            return "draft_bid"
        return "watch"

    def _why(
        self,
        match: JobMatch,
        action: Action,
        signals: list[str],
        risks: list[str],
        *,
        freelance_focus: bool,
        benefits: list[str],
    ) -> str:
        title = (match.job.title or "This lead").strip()
        if freelance_focus and benefits and action == "draft_bid":
            return f"{title} looks freelance-friendly — {benefits[0].lower()}."
        if freelance_focus and action == "skip":
            focus = risks[0] if risks else "weak freelance fit"
            return f"{title} is better skipped for freelance work — {focus.lower()}."
        if action == "draft_bid":
            focus = signals[0] if signals else "solid preference fit"
            return f"{title} looks actionable now — {focus.lower()}."
        if action == "skip":
            focus = risks[0] if risks else "risk signals outweigh the fit"
            return f"{title} is better skipped — {focus.lower()}."
        focus = (benefits[0] if freelance_focus and benefits else None) or (
            signals[0] if signals else "partial preference fit"
        )
        return f"{title} is worth watching — {focus.lower()}."

    def to_dict(self, finding: LeadFinding) -> dict[str, Any]:
        job = finding.job
        source = str(job.source_name or "")
        attribution = SOURCE_ATTRIBUTION.get(source, source.title() or "Source")
        benefits = finding.freelance_benefits or []
        return {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "source_name": source,
            "source_label": f"Listed on {attribution}",
            "source_attribution": attribution,
            "url": job.url,
            "apply_url": job.url,
            "description_excerpt": make_excerpt(job.description or ""),
            "score": finding.score,
            "why": finding.why,
            "signals": finding.signals,
            "risks": finding.risks,
            "action": finding.action,
            "matched_keywords": finding.matched_keywords,
            "freshness_score": finding.freshness_score,
            "client_quality_score": finding.client_quality_score,
            "red_flags": finding.red_flags,
            "posted_at": job.posted_at,
            "freelance_fit": finding.freelance_fit,
            "freelance_benefits": benefits,
            "freelance_benefits_line": " · ".join(benefits[:4]) if benefits else None,
            "employment_risks": finding.employment_risks or [],
        }
