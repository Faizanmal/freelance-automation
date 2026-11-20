from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from app.core.redis_client import get_redis
from app.ingestion.governance import record_source_health
from app.ingestion.normalize import enrich_candidate_classification
from app.ingestion.policy_gate import filter_sources
from app.ingestion.reliability import (
    acquire_source_lease,
    budget_exceeded,
    circuit_is_open,
    quarantine_batch,
    record_source_failure,
    record_source_success,
    record_spend,
    release_source_lease,
)
from app.ingestion.sources import (
    DISCOVERY_SOURCES,
    SOURCE_REGISTRY,
    V1_DEFAULT_HUNTERS,
)
from app.integrations.apify_marketplaces import (
    SourceNotConfiguredError as ApifyNotConfigured,
)
from app.integrations.freelancer import (
    SourceNotConfiguredError as FreelancerNotConfigured,
)
from app.integrations.reddit_hiring import (
    SourceNotConfiguredError as RedditNotConfigured,
)
from app.integrations.serpapi_discovery import (
    SourceNotConfiguredError as SerpApiNotConfigured,
)
from app.integrations.upwork import SourceNotConfiguredError as UpworkNotConfigured
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import destinations_from_preferences
from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.hunt_query_builder import HuntQueryBuilder
from backend.application.services.job_ingestion import JobIngestionService
from backend.application.services.matching import MatchingService
from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
)
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from config.settings import get_settings
from database.models.preference import UserPreferences
from database.models.user import User


class ScrapeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion = JobIngestionService(session)

    async def _get_cached_candidates(
        self, source_name: str, query: str | None, limit: int
    ) -> list[JobCandidate] | None:
        try:
            redis_client = await get_redis()
            if not redis_client:
                return None
            norm_q = (query or "").strip().lower()
            h = hashlib.sha256(f"{norm_q}:{limit}".encode()).hexdigest()
            key = f"hunter_cache:{source_name}:{h}"
            cached_data = await redis_client.get(key)
            if not cached_data:
                return None
            items = json.loads(cached_data)
            return [
                JobCandidate(
                    source_name=item["source_name"],
                    source_id=item["source_id"],
                    title=item["title"],
                    description=item["description"],
                    url=item["url"],
                    company=item.get("company"),
                    budget_min=item.get("budget_min"),
                    budget_max=item.get("budget_max"),
                    posted_at=item.get("posted_at"),
                    metadata=item.get("metadata") or {},
                )
                for item in items
            ]
        except Exception:
            return None

    async def _set_cached_candidates(
        self,
        source_name: str,
        query: str | None,
        limit: int,
        candidates: list[JobCandidate],
        ttl_seconds: int = 7200,
    ) -> None:
        try:
            redis_client = await get_redis()
            if not redis_client or not candidates:
                return
            norm_q = (query or "").strip().lower()
            h = hashlib.sha256(f"{norm_q}:{limit}".encode()).hexdigest()
            key = f"hunter_cache:{source_name}:{h}"
            serialized = [
                {
                    "source_name": c.source_name,
                    "source_id": c.source_id,
                    "title": c.title,
                    "description": c.description,
                    "url": c.url,
                    "company": c.company,
                    "budget_min": c.budget_min,
                    "budget_max": c.budget_max,
                    "posted_at": c.posted_at,
                    "metadata": c.metadata,
                }
                for c in candidates
            ]
            await redis_client.set(key, json.dumps(serialized), ex=ttl_seconds)
        except Exception:
            pass

    async def run(
        self,
        sources: list[str] | None = None,
        *,
        limit: int = 40,
        notify_matches: bool = False,
        query: str | None = None,
    ) -> dict[str, object]:
        # Default to V1 hunter spine. Policy gate drops restricted/experimental/
        # uncredentialed sources. Ranking/digest stay outside this path.
        requested = (
            sources or get_settings().scrape_source_list or list(V1_DEFAULT_HUNTERS)
        )
        selected, gate_decisions = filter_sources(requested)
        query_map = await HuntQueryBuilder(self.session).queries_for_sources(
            selected, explicit=query
        )
        summary: dict[str, object] = {
            "sources": {},
            "gate": {k: v.to_dict() for k, v in gate_decisions.items()},
            "total_fetched": 0,
            "total_ingested": 0,
            "total_merged": 0,
            "total_skipped": 0,
            "alerts_sent": 0,
            "new_job_ids": [],
            "hunt_queries": {k: v for k, v in query_map.items() if v},
            "inventory_mode": "shared_discovery",
        }

        for name, decision in gate_decisions.items():
            if not decision.allowed:
                summary["sources"][name] = {
                    "status": "skipped",
                    "error": decision.reason,
                    "fetched": 0,
                }

        for source_name in selected:
            cls = SOURCE_REGISTRY.get(source_name)
            if cls is None:
                summary["sources"][source_name] = {
                    "status": "error",
                    "error": "unknown_source",
                }
                continue

            policy = gate_decisions.get(source_name).policy if gate_decisions.get(source_name) else None
            if await circuit_is_open(source_name):
                summary["sources"][source_name] = {
                    "status": "circuit_open",
                    "error": "circuit_open",
                    "fetched": 0,
                }
                continue

            if policy and await budget_exceeded(source_name, policy.daily_budget_usd):
                summary["sources"][source_name] = {
                    "status": "budget_capped",
                    "error": "daily_budget_exceeded",
                    "fetched": 0,
                }
                continue

            leased = await acquire_source_lease(source_name)
            if not leased:
                summary["sources"][source_name] = {
                    "status": "lease_held",
                    "error": "source_lease_held",
                    "fetched": 0,
                }
                continue

            source = cls()
            source_query = query_map.get(source_name)

            candidates: list[JobCandidate] | None = None
            is_cacheable = source_name in DISCOVERY_SOURCES
            try:
                if is_cacheable:
                    candidates = await self._get_cached_candidates(
                        source_name, source_query, limit
                    )

                if candidates is None:
                    try:
                        fetch = source.fetch
                        try:
                            candidates = await fetch(limit=limit, query=source_query)
                        except TypeError:
                            candidates = await fetch(limit=limit)
                        if is_cacheable and candidates:
                            await self._set_cached_candidates(
                                source_name, source_query, limit, candidates
                            )
                    except (
                        UpworkNotConfigured,
                        FreelancerNotConfigured,
                        ApifyNotConfigured,
                        SerpApiNotConfigured,
                        RedditNotConfigured,
                    ) as exc:
                        summary["sources"][source_name] = {
                            "status": "error",
                            "error": "not_configured",
                            "detail": str(exc),
                            "fetched": 0,
                        }
                        await record_source_failure(source_name, error=str(exc))
                        record_source_health(source_name, ok=False, detail=str(exc))
                        continue
                    except (
                        httpx.HTTPError,
                        RuntimeError,
                        ValueError,
                        OSError,
                        TimeoutError,
                    ) as exc:
                        qid = await quarantine_batch(
                            source_name=source_name,
                            reason="fetch_error",
                            payload={"error": str(exc)},
                        )
                        opened = await record_source_failure(
                            source_name, error=str(exc)
                        )
                        record_source_health(source_name, ok=False, detail=str(exc))
                        summary["sources"][source_name] = {
                            "status": "error",
                            "error": str(exc),
                            "fetched": 0,
                            "quarantine_id": qid,
                            "circuit_opened": opened,
                        }
                        continue
                    except Exception as exc:
                        # Keep other hunters running if one source blows up.
                        qid = await quarantine_batch(
                            source_name=source_name,
                            reason="unexpected_error",
                            payload={"error": f"{exc.__class__.__name__}: {exc}"},
                        )
                        await record_source_failure(source_name, error=str(exc))
                        record_source_health(source_name, ok=False, detail=str(exc))
                        summary["sources"][source_name] = {
                            "status": "error",
                            "error": f"{exc.__class__.__name__}: {exc}",
                            "fetched": 0,
                            "quarantine_id": qid,
                        }
                        continue

                if not candidates:
                    # Distinguish empty inventory from provider failure.
                    await record_source_success(source_name)
                    record_source_health(source_name, ok=True, fetched=0)
                    summary["sources"][source_name] = {
                        "status": "no_results",
                        "fetched": 0,
                        "ingested": 0,
                        "merged": 0,
                        "linked": 0,
                        "skipped": 0,
                    }
                    continue

                counts = {
                    "status": "ok",
                    "fetched": len(candidates),
                    "ingested": 0,
                    "merged": 0,
                    "linked": 0,
                    "skipped": 0,
                }
                for candidate in candidates:
                    candidate = enrich_candidate_classification(candidate)
                    try:
                        result = await self.ingestion.ingest(
                            candidate,
                            location=(candidate.metadata or {}).get("location"),
                            tags=(candidate.metadata or {}).get("tags"),
                        )
                    except Exception as exc:
                        counts["skipped"] = int(counts.get("skipped", 0)) + 1
                        summary["total_skipped"] = int(summary["total_skipped"]) + 1
                        summary["total_fetched"] = int(summary["total_fetched"]) + 1
                        counts.setdefault("errors", [])
                        if (
                            isinstance(counts["errors"], list)
                            and len(counts["errors"]) < 5
                        ):
                            counts["errors"].append(
                                f"{exc.__class__.__name__}: {str(exc)[:160]}"
                            )
                        continue
                    action = str(result.get("action"))
                    if action in counts:
                        counts[action] = int(counts[action]) + 1
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

                await record_source_success(source_name)
                record_source_health(
                    source_name, ok=True, fetched=int(counts["fetched"])
                )
                if policy and policy.daily_budget_usd and policy.daily_budget_usd > 0:
                    # Approximate unit cost for search providers (~$0.01 / batch).
                    await record_spend(source_name, 0.01)
                summary["sources"][source_name] = counts
            finally:
                await release_source_lease(source_name)

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

        users_result = await self.session.execute(
            select(User, UserPreferences)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .where(User.is_active.is_(True), User.is_verified.is_(True))
        )
        pairs = users_result.all()
        sent = 0
        matching = MatchingService()
        notifier = PersistentNotificationService(self.session)

        for user, prefs in pairs:
            # When digest_mode is enabled, the show-clock digest owns delivery.
            if getattr(prefs, "digest_mode", False):
                continue
            for job in jobs:
                match = matching.score_job(job, prefs)
                if match is None:
                    continue
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
                        priority=(
                            NotificationPriority.HIGH
                            if match.score >= 0.6
                            else NotificationPriority.NORMAL
                        ),
                        ai_summary=match.job.analysis_summary,
                        metadata={
                            "match_score": match.score,
                            "matched_keywords": match.matched_keywords,
                        },
                        destinations=destinations_from_preferences(prefs)
                        | {"email": prefs.alert_email or user.email},
                    ),
                    job_id=match.job.id,
                )
                sent += 1
        return sent
