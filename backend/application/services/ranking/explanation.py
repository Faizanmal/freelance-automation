"""Versioned score explanations — factual, evidence-linked, not calibrated probability."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ConfidenceBand = Literal["high", "medium", "low", "unknown"]


@dataclass(slots=True)
class ScoreComponent:
    name: str
    weight: float
    contribution: float
    evidence: str | None = None


@dataclass(slots=True)
class ScoreExplanation:
    score_version: str
    fit_score: float
    components: list[ScoreComponent] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    missing_qualifications: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)
    hard_filters_passed: list[str] = field(default_factory=list)
    hard_filters_failed: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    why_shown: str = ""
    retrieval_path: str = "keyword"
    confidence_band: ConfidenceBand = "medium"
    confidence_note: str = (
        "Heuristic confidence band — not a calibrated probability of hire or success."
    )
    eligibility: str = "eligible"

    def to_dict(self) -> dict[str, Any]:
        return {
            "score_version": self.score_version,
            "fit_score": self.fit_score,
            "components": [asdict(c) for c in self.components],
            "matched_keywords": list(self.matched_keywords),
            "missing_qualifications": list(self.missing_qualifications),
            "mismatches": list(self.mismatches),
            "hard_filters_passed": list(self.hard_filters_passed),
            "hard_filters_failed": list(self.hard_filters_failed),
            "reasons": list(self.reasons),
            "why_shown": self.why_shown,
            "retrieval_path": self.retrieval_path,
            "confidence_band": self.confidence_band,
            "confidence_note": self.confidence_note,
            "eligibility": self.eligibility,
            "calibrated_probability": None,
        }


def confidence_from_evidence(
    *,
    matched: int,
    total_terms: int,
    missing: list[str],
    mismatches: list[str],
    cold_start: bool,
) -> ConfidenceBand:
    if cold_start or total_terms == 0:
        return "unknown"
    if mismatches or len(missing) >= max(2, total_terms // 2):
        return "low"
    if matched >= max(2, int(0.6 * total_terms)) and not mismatches:
        return "high"
    return "medium"


def build_why_shown(
    *,
    matched_keywords: list[str],
    reasons: list[str],
    retrieval_path: str,
    learning: bool,
) -> str:
    parts: list[str] = []
    if matched_keywords:
        parts.append(f"skills overlap ({', '.join(matched_keywords[:4])})")
    for reason in reasons:
        if reason.startswith("saved-skill") or reason.startswith("skipped-skill"):
            if learning:
                parts.append(reason)
            continue
        if reason in {"no_skills_configured", "saved_or_actioned_lead"}:
            parts.append(reason.replace("_", " "))
            continue
        if "experience" in reason or "engagement" in reason or "fresh" in reason.lower():
            parts.append(reason)
    if retrieval_path == "semantic":
        parts.append("semantic similarity shortlist")
    elif retrieval_path == "hybrid":
        parts.append("keyword + semantic shortlist")
    if not parts:
        return "Shown from Hunt Rules keyword ranking."
    return "Shown because: " + "; ".join(parts[:5]) + "."
