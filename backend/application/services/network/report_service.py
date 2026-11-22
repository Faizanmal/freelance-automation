"""Phase 13 — Marketplace report and verification appeal procedures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.network import MarketplaceReport
from database.models.user import User

VALID_TARGET_TYPES = {"talent_profile", "org_profile", "verification_claim", "evidence"}
VALID_REPORT_TYPES = {"report", "appeal"}


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_report_or_appeal(
        self,
        reporter_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        details: str,
        report_type: str = "report",
    ) -> MarketplaceReport:
        if target_type not in VALID_TARGET_TYPES:
            raise ValueError(f"Invalid target type. Must be one of {VALID_TARGET_TYPES}")
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Invalid report type. Must be one of {VALID_REPORT_TYPES}")
        if not reason.strip():
            raise ValueError("Reason is required")
        if not details.strip():
            raise ValueError("Details are required")

        now = datetime.now(timezone.utc)
        report = MarketplaceReport(
            id=str(uuid4()),
            reporter_user_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            report_type=report_type,
            reason=reason.strip()[:128],
            details=details.strip(),
            status="opened",
            created_at=now,
            updated_at=now,
        )
        self.session.add(report)
        await self.session.commit()
        return report

    async def resolve_report(
        self,
        report_id: str,
        admin_id: str,
        resolution_notes: str,
        status: str = "resolved",
    ) -> MarketplaceReport:
        stmt = select(MarketplaceReport).where(MarketplaceReport.id == report_id)
        res = await self.session.execute(stmt)
        report = res.scalar_one_or_none()
        if not report:
            raise ValueError("Report not found")

        now = datetime.now(timezone.utc)
        report.status = status
        report.resolution_notes = resolution_notes.strip()
        report.resolved_by_id = admin_id
        report.updated_at = now
        await self.session.commit()
        return report
