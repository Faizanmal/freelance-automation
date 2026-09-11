from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List


class JobAnalysis(BaseModel):
    skills: List[str] = Field(default_factory=list)
    budget: str | None = None
    difficulty: str | None = None
    seniority: str | None = None
    urgency: str | None = None
    timezone: str | None = None
    project_type: str | None = None

    relevance_score: float | None = None
    success_probability: float | None = None
    estimated_hours: float | None = None
    estimated_profit: float | None = None
    missing_skills: List[str] = Field(default_factory=list)
    risk_score: float | None = None

    summary: str | None = None
    proposal_draft: str | None = None
    questions_to_ask: List[str] = Field(default_factory=list)

    raw_json: dict[str, object] | None = None

    class Config:
        extra = "forbid"
