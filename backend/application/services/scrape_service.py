from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.sources import PUBLIC_SOURCES, SOURCE_REGISTRY
from app.integrations.apify_marketplaces import (
    SourceNotConfiguredError as ApifyNotConfigured,
)
from app.integrations.freelancer import SourceNotConfiguredError as FreelancerNotConfigured
from app.integrations.serpapi_discovery import SourceNotConfiguredError as SerpApiNotConfigured
from app.integrations.upwork import SourceNotConfiguredError as UpworkNotConfigured
from database.models.preference import UserPreferences
from database.models.user import User
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from backend.application.services.job_ingestion import JobIngestionService
from backend.application.services.billing import destinations_from_preferences
from backend.application.services.matching import MatchingService
from backend.application.services.notification_service import NotificationChannel, NotificationPayload, NotificationPriority
from backend.application.services.persistent_notifications import PersistentNotificationService


class ScrapeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion = JobIngestionService(session)

    async def run(
        self,
        sources: list[str] | None = None,
        *,
        limit: int = 40,
        notify_matches: bool = False,
        query: str | None = None,
    ) -> dict[str, object]:
        # Default to public boards; marketplaces are opt-in via request or SCRAPE_SOURCES.
        selected = sources or list(PUBLIC_SOURCES)
        summary: dict[str, object] = {
            "sources": {},
            "total_fetched": 0,
            "total_ingested": 0,
            "total_merged": 0,
            "total_skipped": 0,
            "alerts_sent": 0,
            "new_job_ids": [],
        }

        for source_name in selected:
            cls = SOURCE_REGISTRY.get(source_name)
            if cls is None:
                summary["sources"][source_name] = {"error": "unknown_source"}
                continue

            source = cls()
            try:
                fetch = source.fetch
                try:
                    candidates = await fetch(limit=limit, query=query)
                except TypeError:
                    candidates = await fetch(limit=limit)
            except (
                UpworkNotConfigured,
                FreelancerNotConfigured,
                ApifyNotConfigured,
                SerpApiNotConfigured,
            ) as exc:
                summary["sources"][source_name] = {"error": "not_configured", "detail": str(exc), "fetched": 0}
                continue
            except Exception as exc:  # noqa: BLE001
                summary["sources"][source_name] = {"error": str(exc), "fetched": 0}
                continue

            counts = {"fetched": len(candidates), "ingested": 0, "merged": 0, "linked": 0, "skipped": 0}
            for candidate in candidates:
                result = await self.ingestion.ingest(
                    candidate,
                    location=(candidate.metadata or {}).get("location"),
                    tags=(candidate.metadata or {}).get("tags"),
                )
                action = str(result.get("action"))
                if action in counts:
                    counts[action] += 1
                summary["total_fetched"] = int(summary["total_fetched"]) + 1
                if action == "ingested":
                    summary["total_ingested"] = int(summary["total_ingested"]) + 1
                    job_id = result.get("job_id")
                    if isinstance(job_id, int):
                        summary["new_job_ids"].append(job_id)  # type: ignore[union-attr]
                elif action == "merged":
                    summary["total_merged"] = int(summary["total_merged"]) + 1
                elif action in {"skipped", "linked"}:
                    summary["total_skipped"] = int(summary["total_skipped"]) + 1

            summary["sources"][source_name] = counts

        if notify_matches and summary["new_job_ids"]:
            summary["alerts_sent"] = await self._notify_users_of_new_jobs(summary["new_job_ids"])  # type: ignore[arg-type]

        return summary

    async def _notify_users_of_new_jobs(self, job_ids: list[int]) -> int:
        repo = SQLAlchemyJobRepository(self.session)
        jobs = []
        for job_id in job_ids:
            job = await repo.get_by_id(job_id)
            if job:
                jobs.append(job)
        if not jobs:
            return 0

        users_result = await self.session.execute(select(User).where(User.is_active.is_(True)))
        users = list(users_result.scalars().all())
        matcher = MatchingService()
        notifier = PersistentNotificationService(self.session)
        sent = 0

        for user in users:
            prefs_result = await self.session.execute(select(UserPreferences).where(UserPreferences.user_id == user.id))
            prefs = prefs_result.scalar_one_or_none()
            if prefs is None:
                continue
            matches = matcher.rank_jobs(jobs, prefs)
            for match in matches[:5]:
                channels = []
                for channel_name in prefs.notification_channels or ["email"]:
                    try:
                        channels.append(NotificationChannel(channel_name))
                    except ValueError:
                        continue
                if not channels:
                    channels = [NotificationChannel.EMAIL]
                await notifier.send(
                    NotificationPayload(
                        user_id=user.id,
                        title=f"Match: {match.job.title}",
                        body=match.job.analysis_summary or match.job.description[:400],
                        channels=channels,
                        priority=NotificationPriority.HIGH if match.score >= 0.6 else NotificationPriority.NORMAL,
                        ai_summary=match.job.analysis_summary,
                        metadata={"match_score": match.score, "matched_keywords": match.matched_keywords},
                        destinations=destinations_from_preferences(prefs)
                        | {"email": prefs.alert_email or user.email},
                    ),
                    job_id=match.job.id,
                )
                sent += 1
        return sent
