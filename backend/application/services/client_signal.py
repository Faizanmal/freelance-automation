from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

AGENCY_KEYWORDS = (
    r"\bour client\b",
    r"\bon behalf of\b",
    r"\bclient of ours\b",
    r"\bclient is (a|an|looking|seeking)\b",
    r"\bstaffing agency\b",
    r"\brecruiting agency\b",
    r"\brecruitment agency\b",
    r"\btalent agency\b",
    r"\btalent partners\b",
    r"\bcontingent workforce\b",
    r"\bconfidential client\b",
    r"\bstealth client\b",
    r"\bleading client\b",
    r"\bundisclosed client\b",
    r"\bthird[\s-]?party agency\b",
    r"\bstaffing partner\b",
    r"\btalent acquisition partner\b",
    r"\bcorp[\s-]?to[\s-]?corp only\b",
    r"\bc2c only\b",
)

AGENCY_COMPANIES = {
    "cybercoders",
    "robert half",
    "teksystems",
    "apex systems",
    "insight global",
    "kelly services",
    "hays",
    "randstad",
    "adecco",
    "michael page",
    "korn ferry",
    "manpower",
    "aerotek",
    "beacon hill",
    "modis",
    "kforce",
    "allegis",
    "judge group",
}

FOUNDER_KEYWORDS = (
    r"\bi('?m| am) the founder\b",
    r"\bco-?founder\b",
    r"\bfounder here\b",
    r"\bmy startup\b",
    r"\bour startup\b",
    r"\bfounding engineer\b",
    r"\bfounding team\b",
    r"\bwe just raised\b",
    r"\bbootstrapped startup\b",
    r"\bsmall team of\b",
    r"\bworking directly with (me|the founder)\b",
    r"\breporting to the founder\b",
    r"\bearly[\s-]?stage startup\b",
)

URGENCY_HIGH_KEYWORDS = (
    (r"\bimmediate(ly)? start\b", "Immediate start"),
    (r"\bstart immediately\b", "Immediate start"),
    (r"\basap\b", "ASAP start"),
    (r"\burgent(ly)?\b", "Urgent hire"),
    (r"\bstart this week\b", "Starts this week"),
    (r"\bpaid trial\b", "Paid trial"),
    (r"\bquick turnaround\b", "Quick turnaround"),
    (r"\binterviewing (today|this week)\b", "Fast-track interview"),
    (r"\bwithin 24 hours\b", "Fast turnaround"),
)

URGENCY_MEDIUM_KEYWORDS = (
    (r"\bread(y)? to hire\b", "Ready to hire"),
    (r"\bshort[\s-]?term project\b", "Short-term"),
    (r"\bquick fix\b", "Quick turnaround"),
)


@dataclass(frozen=True, slots=True)
class ClientSignal:
    poster_type: str  # "direct_founder" | "company_direct" | "agency_recruiter" | "community_post" | "verified"
    poster_label: str
    poster_badge: str  # "founder" | "company" | "agency" | "community" | "verified"
    urgency: str  # "high" | "medium" | "normal"
    urgency_label: str | None
    is_agency: bool
    score: int  # 0 to 100
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "poster_type": self.poster_type,
            "poster_label": self.poster_label,
            "poster_badge": self.poster_badge,
            "urgency": self.urgency,
            "urgency_label": self.urgency_label,
            "is_agency": self.is_agency,
            "score": self.score,
            "reasons": list(self.reasons),
        }


def detect_client_signal(
    *,
    title: str = "",
    description: str = "",
    company: str | None = None,
    source_name: str = "",
    enrichment: dict[str, Any] | None = None,
) -> ClientSignal:
    """Analyze listing attributes to categorize poster type, agency risks, and urgency."""
    haystack = f"{title} {description}".lower()
    company_lower = (company or "").strip().lower()
    source = (source_name or "").lower()
    reasons: list[str] = []

    # 1. Check for Staffing Agency indicators
    is_agency = False
    if any(agency in company_lower for agency in AGENCY_COMPANIES):
        is_agency = True
        reasons.append(f"Company '{company}' matches known staffing/recruitment firm")

    if not is_agency:
        for kw in AGENCY_KEYWORDS:
            if re.search(kw, haystack, re.IGNORECASE):
                is_agency = True
                reasons.append("Mentions staffing intermediary ('on behalf of' or 'our client')")
                break

    if is_agency:
        urgency, urgency_label = _detect_urgency(haystack)
        return ClientSignal(
            poster_type="agency_recruiter",
            poster_label="Staffing Agency",
            poster_badge="agency",
            urgency=urgency,
            urgency_label=urgency_label,
            is_agency=True,
            score=45,
            reasons=tuple(reasons),
        )

    # 2. Check for Direct Founder signals
    is_founder = False
    for kw in FOUNDER_KEYWORDS:
        if re.search(kw, haystack, re.IGNORECASE):
            is_founder = True
            reasons.append("Direct founder or early founding team statement in listing")
            break

    if source in {"hn_hiring", "github_bounties"}:
        is_founder = True
        reasons.append("Direct community post from project creator / founder")

    if is_founder:
        urgency, urgency_label = _detect_urgency(haystack)
        return ClientSignal(
            poster_type="direct_founder",
            poster_label="Direct Founder",
            poster_badge="founder",
            urgency=urgency,
            urgency_label=urgency_label,
            is_agency=False,
            score=95,
            reasons=tuple(reasons),
        )

    # 3. Check for Direct Company (ATS / Corporate career listings)
    if source in {"serpapi_companies", "serpapi_jobs"} or "boards.greenhouse.io" in haystack or "jobs.lever.co" in haystack:
        reasons.append("Direct company careers / ATS listing")
        urgency, urgency_label = _detect_urgency(haystack)
        return ClientSignal(
            poster_type="company_direct",
            poster_label="Direct Company",
            poster_badge="company",
            urgency=urgency,
            urgency_label=urgency_label,
            is_agency=False,
            score=85,
            reasons=tuple(reasons),
        )

    # 4. Check for Community / Forum posts (Reddit, etc.)
    if source == "reddit_hiring":
        reasons.append("Direct community hiring post")
        urgency, urgency_label = _detect_urgency(haystack)
        return ClientSignal(
            poster_type="community_post",
            poster_label="Community Post",
            poster_badge="community",
            urgency=urgency,
            urgency_label=urgency_label,
            is_agency=False,
            score=80,
            reasons=tuple(reasons),
        )

    # 5. Default verified listing
    if company_lower:
        reasons.append(f"Named employer: {company}")
    urgency, urgency_label = _detect_urgency(haystack)
    return ClientSignal(
        poster_type="company_direct" if company_lower else "verified",
        poster_label="Direct Company" if company_lower else "Verified Listing",
        poster_badge="company" if company_lower else "verified",
        urgency=urgency,
        urgency_label=urgency_label,
        is_agency=False,
        score=75 if company_lower else 70,
        reasons=tuple(reasons),
    )


def _detect_urgency(haystack: str) -> tuple[str, str | None]:
    for pattern, label in URGENCY_HIGH_KEYWORDS:
        if re.search(pattern, haystack, re.IGNORECASE):
            return "high", label
    for pattern, label in URGENCY_MEDIUM_KEYWORDS:
        if re.search(pattern, haystack, re.IGNORECASE):
            return "medium", label
    return "normal", None

