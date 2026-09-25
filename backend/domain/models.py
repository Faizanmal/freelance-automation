from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobOpportunity(BaseModel):
    source: str
    external_id: str
    title: str
    company: str
    location: str | None = None
    description: str
    url: str
    posted_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnrichedJob(JobOpportunity):
    skills_required: list[str] = Field(default_factory=list)
    budget_estimate: float | None = None
    is_freelance: bool = True
    match_score_hints: dict[str, Any] = Field(default_factory=dict)


class UserPreferences(BaseModel):
    user_id: str
    keywords: list[str] = Field(default_factory=list)
    min_budget: float | None = None
    preferred_sources: list[str] = Field(default_factory=list)
    freelance_only: bool = True


class ScoreResult(BaseModel):
    score: float
    reasoning: str
    matched_keywords: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    job: JobOpportunity
    score_result: ScoreResult
    matched_at: datetime = Field(default_factory=datetime.utcnow)


class SourceHealthStatus(BaseModel):
    source: str
    is_healthy: bool
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    error_message: str | None = None
