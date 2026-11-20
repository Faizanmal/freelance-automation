"""Listing report → moderator queue with abuse / PII guards."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.job import JobRecord
from database.models.listing_report import ListingReport, ListingReportCorrection

ALLOWED_REASONS = frozenset(
    {
        "payment_before_work",
        "sensitive_data_request",
        "misleading_or_duplicate",
        "unclear_scope_budget",
        "excessive_unpaid_test",
        "suspicious_link",
        "other_trust_concern",
        "correction_request",
    }
)

# External platform report paths (when we know them)
EXTERNAL_REPORT_PATHS: dict[str, str] = {
    "upwork": "https://support.upwork.com/hc/en-us/articles/211068358",
    "freelancer": "https://www.freelancer.com/support/projects/report-a-project",
    "remoteok": "https://remoteok.com/",
    "reddit_hiring": "https://www.reddit.com/report",
}


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def sanitize_report_text(text: str | None, *, limit: int = 1000) -> str | None:
    if not text:
        return None
    cleaned = _EMAIL_RE.sub("[redacted-email]", text)
    cleaned = _PHONE_RE.sub("[redacted-phone]", cleaned)
    cleaned = _SSN_RE.sub("[redacted-id]", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


def external_report_path(source_name: str | None) -> str | None:
    if not source_name:
        return None
    return EXTERNAL_REPORT_PATHS.get(source_name)


class ListingReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _recent_report_count(self, user_id: str, *, hours: int = 24) -> int:
        # Abuse throttle: count open/recent reports
        result = await self.session.execute(
            select(func.count(ListingReport.id)).where(
                ListingReport.reporter_user_id == user_id
            )
        )
        return int(result.scalar() or 0)

    async def submit(
        self,
        *,
        user_id: str,
        job_id: int,
        reason_code: str,
        details: str | None = None,
        correction_requested: bool = False,
        evidence_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if reason_code not in ALLOWED_REASONS:
            return {"ok": False, "error": "invalid_reason"}

        # Soft abuse cap (retaliatory / spam reporting)
        if await self._recent_report_count(user_id) >= 30:
            return {"ok": False, "error": "rate_limited"}

        job = await self.session.get(JobRecord, job_id)
        if not job:
            return {"ok": False, "error": "job_not_found"}

        # High-risk native → queue for human review (never auto-ban from model)
        severity = "medium"
        if reason_code in {"payment_before_work", "sensitive_data_request"}:
            severity = "high"

        report = ListingReport(
            job_id=job_id,
            reporter_user_id=user_id,
            reason_code=reason_code,
            details=None,  # raw not stored
            sanitized_details=sanitize_report_text(details),
            status="open",
            severity_hint=severity,
            external_report_path=external_report_path(job.source_name),
            correction_requested=correction_requested
            or reason_code == "correction_request",
            evidence_snapshot=evidence_snapshot,
        )
        self.session.add(report)
        try:
            await self.session.commit()
            await self.session.refresh(report)
        except IntegrityError:
            await self.session.rollback()
            return {
                "ok": False,
                "error": "duplicate_report",
                "detail": "You already filed this reason for this listing.",
            }

        return {
            "ok": True,
            "report": self.to_dict(report),
            "message": (
                "Report queued for human review. This is not an automatic exclusion. "
                "Prefer the source platform’s report path when available."
            ),
        }

    async def list_queue(
        self, *, status: str | None = "open", limit: int = 50
    ) -> list[dict[str, Any]]:
        q = select(ListingReport).order_by(ListingReport.created_at.desc()).limit(limit)
        if status:
            q = q.where(ListingReport.status == status)
        result = await self.session.execute(q)
        return [self.to_dict(r) for r in result.scalars().all()]

    async def review(
        self,
        *,
        report_id: int,
        moderator_user_id: str,
        outcome: str,
        notes: str | None = None,
        new_status: str = "resolved",
    ) -> dict[str, Any]:
        report = await self.session.get(ListingReport, report_id)
        if not report:
            return {"ok": False, "error": "not_found"}
        if outcome not in {
            "confirmed_concern",
            "no_action",
            "corrected",
            "dismissed_abuse",
            "needs_more_info",
        }:
            return {"ok": False, "error": "invalid_outcome"}
        report.moderator_user_id = moderator_user_id
        report.moderator_outcome = outcome
        report.moderator_notes = sanitize_report_text(notes, limit=2000)
        report.status = new_status if new_status in {
            "resolved",
            "dismissed",
            "corrected",
            "in_review",
        } else "resolved"
        report.resolved_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(report)
        return {"ok": True, "report": self.to_dict(report)}

    async def request_correction(
        self, *, report_id: int, user_id: str, message: str
    ) -> dict[str, Any]:
        report = await self.session.get(ListingReport, report_id)
        if not report:
            return {"ok": False, "error": "not_found"}
        if report.reporter_user_id != user_id:
            return {"ok": False, "error": "forbidden"}
        clean = sanitize_report_text(message, limit=1500)
        if not clean:
            return {"ok": False, "error": "empty_message"}
        row = ListingReportCorrection(
            report_id=report_id,
            requester_user_id=user_id,
            message=clean,
            status="open",
        )
        report.correction_requested = True
        report.status = "in_review"
        self.session.add(row)
        await self.session.commit()
        return {"ok": True, "correction_id": row.id}

    @staticmethod
    def to_dict(report: ListingReport) -> dict[str, Any]:
        return {
            "id": report.id,
            "job_id": report.job_id,
            "reason_code": report.reason_code,
            "status": report.status,
            "severity_hint": report.severity_hint,
            "sanitized_details": report.sanitized_details,
            "external_report_path": report.external_report_path,
            "moderator_outcome": report.moderator_outcome,
            "correction_requested": report.correction_requested,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "resolved_at": report.resolved_at.isoformat()
            if report.resolved_at
            else None,
            # Never expose raw reporter PII beyond id to operators
            "reporter_user_id": report.reporter_user_id,
        }
