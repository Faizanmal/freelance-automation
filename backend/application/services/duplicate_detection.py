from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from hashlib import sha1
from typing import Any


@dataclass(slots=True)
class JobSource:
    source_name: str
    source_id: str
    url: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class JobCandidate:
    source_name: str
    source_id: str
    title: str
    description: str
    url: str
    company: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    posted_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DuplicateDecision:
    is_duplicate: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MergedJob:
    source_history: list[JobSource] = field(default_factory=list)
    title: str = ""
    description: str = ""
    company: str | None = None
    url: str = ""
    budget_min: float | None = None
    budget_max: float | None = None
    posted_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SimpleEmbeddingProvider:
    def __call__(self, text: str) -> list[float]:
        return self.embed(text)

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * 64
        tokens = [token for token in self._tokenize(text) if token]
        for token in tokens:
            index = int(sha1(token.encode("utf-8")).hexdigest()[:8], 16) % 64
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _tokenize(self, value: str) -> set[str]:
        return {
            token
            for token in value.lower().replace("&", " ").replace("-", " ").split()
            if token
        }


class DuplicateDetectionService:
    """Duplicate engine with URL, lexical, budget, company, time, and embedding signals."""

    def __init__(
        self,
        duplicate_threshold: float = 0.78,
        embedding_provider: SimpleEmbeddingProvider | None = None,
    ) -> None:
        self.duplicate_threshold = duplicate_threshold
        self.embedding_provider = embedding_provider or SimpleEmbeddingProvider()

    def detect_duplicate(
        self, canonical: JobCandidate, incoming: JobCandidate
    ) -> DuplicateDecision:
        reasons: list[str] = []

        if self._normalize_url(canonical.url) and self._normalize_url(
            canonical.url
        ) == self._normalize_url(incoming.url):
            return DuplicateDecision(
                is_duplicate=True, confidence=0.99, reasons=["same_url"]
            )

        title_score = self._similarity(canonical.title, incoming.title)
        description_score = self._similarity(
            canonical.description, incoming.description
        )
        budget_score = self._budget_similarity(canonical, incoming)
        company_score = self._company_similarity(canonical.company, incoming.company)
        time_score = self._time_similarity(canonical.posted_at, incoming.posted_at)
        embedding_score = self._embedding_proxy(canonical, incoming)

        total = (
            0.25 * title_score
            + 0.20 * description_score
            + 0.15 * embedding_score
            + 0.15 * budget_score
            + 0.15 * company_score
            + 0.10 * time_score
        )

        if total >= self.duplicate_threshold:
            if title_score >= 0.65:
                reasons.append("title_similarity")
            if description_score >= 0.55:
                reasons.append("description_similarity")
            if embedding_score >= 0.6:
                reasons.append("embedding_similarity")
            if budget_score >= 0.7:
                reasons.append("budget_similarity")
            if company_score >= 0.7:
                reasons.append("company_similarity")
            if time_score >= 0.6:
                reasons.append("time_similarity")
            return DuplicateDecision(
                is_duplicate=True,
                confidence=round(min(total, 0.99), 4),
                reasons=reasons,
            )

        return DuplicateDecision(
            is_duplicate=False,
            confidence=round(total, 4),
            reasons=["insufficient_signal"],
        )

    def merge_duplicate(
        self,
        canonical: JobCandidate,
        incoming: JobCandidate,
        decision: DuplicateDecision,
    ) -> MergedJob:
        history = [
            JobSource(
                source_name=canonical.source_name,
                source_id=canonical.source_id,
                url=canonical.url,
            ),
            JobSource(
                source_name=incoming.source_name,
                source_id=incoming.source_id,
                url=incoming.url,
            ),
        ]

        merged = MergedJob(
            source_history=history,
            title=self._pick_best(canonical.title, incoming.title),
            description=self._pick_best(canonical.description, incoming.description),
            company=self._choose_value(canonical.company, incoming.company),
            url=self._choose_value(canonical.url, incoming.url),
            budget_min=self._pick_numeric(canonical.budget_min, incoming.budget_min),
            budget_max=self._pick_numeric(canonical.budget_max, incoming.budget_max),
            posted_at=self._choose_value(canonical.posted_at, incoming.posted_at),
            metadata={
                "duplicate_confidence": decision.confidence,
                "duplicate_reasons": decision.reasons,
                "source_count": 2,
            },
        )
        return merged

    def _similarity(self, left: str | None, right: str | None) -> float:
        left_text = (left or "").strip().lower()
        right_text = (right or "").strip().lower()
        if not left_text or not right_text:
            return 0.0
        return round(SequenceMatcher(None, left_text, right_text).ratio(), 4)

    def _budget_similarity(
        self, canonical: JobCandidate, incoming: JobCandidate
    ) -> float:
        if canonical.budget_min is None or incoming.budget_min is None:
            return 0.5
        if canonical.budget_max is None or incoming.budget_max is None:
            return 0.5
        overlap = self._range_overlap(
            canonical.budget_min,
            canonical.budget_max,
            incoming.budget_min,
            incoming.budget_max,
        )
        if overlap <= 0:
            return 0.0
        return round(
            min(
                1.0,
                overlap
                / max(
                    abs(canonical.budget_max - canonical.budget_min),
                    abs(incoming.budget_max - incoming.budget_min),
                    1,
                ),
            ),
            4,
        )

    def _company_similarity(self, left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0.0
        left_tokens = self._tokenize(left)
        right_tokens = self._tokenize(right)
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens) / min(
            len(left_tokens), len(right_tokens)
        )
        return round(overlap, 4)

    def _time_similarity(self, left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0.5
        try:
            left_dt = self._parse_datetime(left)
            right_dt = self._parse_datetime(right)
        except ValueError:
            return 0.5
        delta = abs((left_dt - right_dt).total_seconds())
        if delta <= 86400:
            return 1.0
        if delta <= 7 * 86400:
            return 0.7
        return 0.0

    def _parse_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _embedding_proxy(
        self, canonical: JobCandidate, incoming: JobCandidate
    ) -> float:
        left_text = " ".join(filter(None, [canonical.title, canonical.description]))
        right_text = " ".join(filter(None, [incoming.title, incoming.description]))
        if not left_text or not right_text:
            return 0.0
        left_vector = self.embedding_provider.embed(left_text)
        right_vector = self.embedding_provider.embed(right_text)
        dot = sum(left * right for left, right in zip(left_vector, right_vector))
        return round(min(1.0, max(0.0, dot)), 4)

    def _normalize_url(self, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().lower().rstrip("/")

    def _tokenize(self, value: str) -> set[str]:
        return {
            token
            for token in value.lower().replace("&", " ").replace("-", " ").split()
            if token
        }

    def _range_overlap(
        self, a_min: float, a_max: float, b_min: float, b_max: float
    ) -> float:
        return max(0.0, min(a_max, b_max) - max(a_min, b_min))

    def _pick_best(self, left: str, right: str) -> str:
        return left if len(left) >= len(right) else right

    def _pick_numeric(self, left: float | None, right: float | None) -> float | None:
        if left is None:
            return right
        if right is None:
            return left
        return max(left, right)

    def _choose_value(self, left: str | None, right: str | None) -> str | None:
        return left or right
