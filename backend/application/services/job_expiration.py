"""Lead expiration, TTL staleness detection, and URL health verification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction

# Source-specific TTL half-lives in days
SOURCE_TTL_DAYS: dict[str, int] = {
    "reddit_hiring": 14,
    "freelancer": 21,
    "upwork": 21,
    "remoteok": 30,
    "serpapi_freelance": 30,
    "serpapi_jobs": 30,
    "serpapi_companies": 30,
}
DEFAULT_TTL_DAYS = 30


class JobExpirationService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def is_stale_by_ttl(self, job: JobRecord) -> bool:
        """Check if job age exceeds source-specific TTL."""
        ttl_days = SOURCE_TTL_DAYS.get(job.source_name, DEFAULT_TTL_DAYS)
        timestamp = job.posted_at or (
            job.created_at.isoformat() if job.created_at else None
        )
        if not timestamp:
            return False

        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds() / 86400.0
            return age_days > ttl_days
        except (ValueError, TypeError):
            return False

    async def check_url_health(
        self, url: str, *, timeout: float = 6.0
    ) -> dict[str, Any]:
        """
        Verify whether an original listing URL is still live.
        Sends a lightweight HTTP HEAD request, falling back to GET on 405.
        """
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return {"is_alive": False, "status_code": None, "reason": "invalid_url"}

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
                verify=True,
            ) as client:
                try:
                    response = await client.head(url)
                    # Some servers return 405 Method Not Allowed for HEAD requests
                    if response.status_code in (405, 501):
                        response = await client.get(url)
                except httpx.TimeoutException:
                    raise
                except httpx.HTTPError:
                    response = await client.get(url)

                code = response.status_code
                if code in (404, 410):
                    return {"is_alive": False, "status_code": code, "reason": "not_found"}
                if code >= 500:
                    return {"is_alive": False, "status_code": code, "reason": "server_error"}
                if 200 <= code < 400:
                    return {"is_alive": True, "status_code": code, "reason": "ok"}
                return {"is_alive": False, "status_code": code, "reason": f"http_{code}"}

        except httpx.TimeoutException:
            return {"is_alive": False, "status_code": None, "reason": "timeout"}
        except httpx.RequestError as exc:
            return {"is_alive": False, "status_code": None, "reason": f"network_error: {type(exc).__name__}"}
        except Exception as exc:  # defensive
            return {"is_alive": False, "status_code": None, "reason": f"unknown_error: {type(exc).__name__}"}

    async def report_expired(
        self,
        job_id: int,
        *,
        user_id: str | None = None,
        reason: str = "dead_link",
    ) -> JobRecord | None:
        """Mark a job as expired and record a skip action for the reporting user."""
        if self.session is None:
            raise RuntimeError("Database session required to report expired job")

        job = await self.session.get(JobRecord, job_id)
        if job is None:
            return None

        job.is_expired = True
        job.expired_at = datetime.now(UTC)
        job.expired_reason = reason
        self.session.add(job)

        if user_id:
            # Also auto-skip this lead for the reporting user so it leaves their view
            res = await self.session.execute(
                select(UserLeadAction).where(
                    UserLeadAction.user_id == user_id,
                    UserLeadAction.job_id == job_id,
                )
            )
            action = res.scalar_one_or_none()
            if action is None:
                self.session.add(
                    UserLeadAction(user_id=user_id, job_id=job_id, status="skip")
                )
            else:
                action.status = "skip"
                self.session.add(action)

        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def sweep_stale_jobs(
        self, *, max_stale_days: int = 45, limit: int = 100
    ) -> int:
        """Find and expire active jobs that have passed maximum TTL."""
        if self.session is None:
            raise RuntimeError("Database session required to sweep stale jobs")

        query = (
            select(JobRecord)
            .where(JobRecord.is_expired == False)
            .order_by(JobRecord.created_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(query)
        candidates = list(res.scalars().all())

        expired_count = 0
        now = datetime.now(UTC)
        for job in candidates:
            if self.is_stale_by_ttl(job):
                job.is_expired = True
                job.expired_at = now
                job.expired_reason = "ttl_expired"
                self.session.add(job)
                expired_count += 1

        if expired_count > 0:
            await self.session.commit()

        return expired_count

