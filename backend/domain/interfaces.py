from __future__ import annotations

from typing import Protocol, Any

from .models import (
    JobOpportunity,
    UserPreferences,
    MatchResult,
    EnrichedJob,
    ScoreResult,
    SourceHealthStatus
)


class IJobSourceAdapter(Protocol):
    """Adapter for fetching and normalizing jobs from an external source."""
    
    async def fetch_jobs(self, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        ...

    async def normalize(self, raw_job: dict[str, Any]) -> JobOpportunity:
        ...

    async def health_check(self) -> SourceHealthStatus:
        ...


class IJobRepository(Protocol):
    """Repository for persisting and querying JobOpportunities."""
    
    async def save(self, job: JobOpportunity) -> Any:
        ...

    async def find_by_external_id(self, source_id: str, external_id: str) -> JobOpportunity | None:
        ...

    async def find_pending_for_match(self) -> list[JobOpportunity]:
        ...


class IUserPreferenceRepository(Protocol):
    """Repository for managing User Preferences."""
    
    async def get_preferences(self, user_id: str) -> UserPreferences:
        ...

    async def save_preferences(self, preferences: UserPreferences) -> None:
        ...


class IJobMatchService(Protocol):
    """Service to score and match jobs to user preferences."""
    
    async def match(self, job: JobOpportunity, preferences: UserPreferences) -> MatchResult:
        ...

    async def batch_match(self, job_ids: list[str], user_id: str) -> list[MatchResult]:
        ...


class IJobEnrichmentService(Protocol):
    """Service to enrich jobs with AI or external data."""
    
    async def enrich(self, job: JobOpportunity) -> EnrichedJob:
        ...


class IAIPreferenceService(Protocol):
    """Service to model AI preferences."""
    
    async def score(self, job: JobOpportunity, preferences: UserPreferences) -> ScoreResult:
        ...

    async def retrain(self, user_id: str, feedback: Any) -> None:
        ...


class INotificationSender(Protocol):
    """Adapter for sending notifications."""
    
    async def send(self, notification: Any) -> bool:
        ...

    async def batch_send(self, payloads: list[Any]) -> list[bool]:
        ...


class IConfigProvider(Protocol):
    """Configuration provider."""
    
    def get(self, key: str, default: Any = None) -> Any:
        ...
