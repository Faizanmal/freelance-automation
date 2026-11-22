"""Phase 15 — Mutual interest, expression of interest ($0 fee), anti-spam rate controls, and invitations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.network.org_service import OrgService
from database.models.matching import (
    APPLICATION_STATUSES,
    INVITATION_STATUSES,
    ProjectApplication,
    ProjectInvitation,
)
from database.models.project import NativeProject


class ProjectMutualInterestService:
    """Manages mutual interest applications, client invitations, and anti-spam quality controls."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_service = OrgService(session)

    # -----------------------------------------------------------------------
    # Freelancer Expression of Interest (Application)
    # -----------------------------------------------------------------------

    async def submit_expression_of_interest(
        self,
        project_id: str,
        freelancer_id: str,
        structured_pitch: str,
        relevant_artifacts: list[dict[str, Any]] | None = None,
        proposed_rate: float = 0.0,
        proposed_rate_period: str = "fixed",
        estimated_days: int | None = None,
    ) -> ProjectApplication:
        """Submit expression of interest at zero monetary cost ($0.00 platform fee).

        Enforces quality controls:
        - Max 5 active applications concurrently.
        - Max 3 applications in a rolling 24-hour window.
        - No duplicate application to the same project.
        - Structured pitch (no unpaid custom deliverables required).
        """
        # 1. Project validity
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        if project.status not in {"approved_open", "shortlist"}:
            raise ValueError(f"Project is currently in '{project.status}' status and not accepting expressions of interest")

        # 2. Duplicate Check
        existing_res = await self.session.execute(
            select(ProjectApplication).where(
                ProjectApplication.project_id == project_id,
                ProjectApplication.freelancer_id == freelancer_id,
                ProjectApplication.status.notin_(["withdrawn", "declined", "rejected"]),
            )
        )
        if existing_res.scalar_one_or_none():
            raise ValueError("You have already submitted an active expression of interest for this project")

        # 3. Anti-Spam Rate Control: Max 5 active applications
        active_count_res = await self.session.execute(
            select(func.count(ProjectApplication.id)).where(
                ProjectApplication.freelancer_id == freelancer_id,
                ProjectApplication.status.in_(["submitted", "shortlisted", "negotiating", "offered"]),
            )
        )
        active_count = active_count_res.scalar() or 0
        if active_count >= 5:
            raise ValueError(
                "Active application limit reached (5 active). Please withdraw or conclude an existing expression of interest before submitting another."
            )

        # 4. Anti-Spam Rate Control: Max 3 applications in rolling 24h
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)
        count_24h_res = await self.session.execute(
            select(func.count(ProjectApplication.id)).where(
                ProjectApplication.freelancer_id == freelancer_id,
                ProjectApplication.created_at >= since_24h,
            )
        )
        recent_count = count_24h_res.scalar() or 0
        if recent_count >= 3:
            raise ValueError(
                "Daily inquiry rate limit reached (max 3 submissions per 24 hours). This prevents automated mass outreach and maintains client review quality."
            )

        # 5. Validate pitch
        if len(structured_pitch.strip()) < 15:
            raise ValueError("Structured pitch must contain at least 15 characters outlining relevant experience and availability.")

        # 6. Create application
        application = ProjectApplication(
            id=str(uuid4()),
            project_id=project_id,
            freelancer_id=freelancer_id,
            status="submitted",
            structured_pitch=structured_pitch.strip(),
            relevant_artifacts=relevant_artifacts or [],
            proposed_rate=float(proposed_rate),
            proposed_rate_period=proposed_rate_period,
            estimated_days=estimated_days,
            created_at=now,
            updated_at=now,
        )
        self.session.add(application)
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def withdraw_expression_of_interest(
        self,
        application_id: str,
        freelancer_id: str,
    ) -> ProjectApplication:
        """Allow candidate to gracefully withdraw interest at any time without penalty."""
        res = await self.session.execute(
            select(ProjectApplication).where(ProjectApplication.id == application_id)
        )
        app = res.scalar_one_or_none()
        if not app:
            raise ValueError("Application not found")

        if app.freelancer_id != freelancer_id:
            raise PermissionError("Access denied: you can only withdraw your own expression of interest")

        if app.status in {"accepted", "withdrawn"}:
            raise ValueError(f"Cannot withdraw application in status '{app.status}'")

        app.status = "withdrawn"
        app.withdrawn_at = datetime.now(timezone.utc)
        app.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(app)
        return app

    async def decline_application(
        self,
        application_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> ProjectApplication:
        """Either client or candidate declines application.

        Guaranteed: No negative public reputation score is recorded for a mere rejection.
        """
        res = await self.session.execute(
            select(ProjectApplication).where(ProjectApplication.id == application_id)
        )
        app = res.scalar_one_or_none()
        if not app:
            raise ValueError("Application not found")

        # Determine authorization: either freelancer or client org member
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == app.project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Associated project not found")

        is_client = False
        if app.freelancer_id != actor_id:
            is_client = await self.org_service.verify_user_in_org(project.org_id, actor_id)
            if not is_client:
                raise PermissionError("Unauthorized to decline this application")

        app.status = "declined" if not is_client else "rejected"
        app.decline_reason = reason or ("Declined by freelancer" if not is_client else "Declined by client")
        app.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(app)
        return app

    # -----------------------------------------------------------------------
    # Client Shortlist Invitations
    # -----------------------------------------------------------------------

    async def invite_talent(
        self,
        project_id: str,
        client_user_id: str,
        freelancer_id: str,
    ) -> ProjectInvitation:
        """Client extends an invitation to a candidate from the shortlist."""
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        # Verify client access
        has_access = await self.org_service.verify_user_in_org(project.org_id, client_user_id)
        if not has_access:
            raise PermissionError("Access denied: only organization members can send invitations")

        # Check existing invitation
        existing_res = await self.session.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.freelancer_id == freelancer_id,
                ProjectInvitation.status == "pending",
            )
        )
        if existing_res.scalar_one_or_none():
            raise ValueError("An active invitation is already pending for this candidate")

        now = datetime.now(timezone.utc)
        invitation = ProjectInvitation(
            id=str(uuid4()),
            project_id=project_id,
            org_id=project.org_id,
            freelancer_id=freelancer_id,
            status="pending",
            invited_at=now,
            expires_at=now + timedelta(days=7),
        )
        self.session.add(invitation)
        await self.session.commit()
        await self.session.refresh(invitation)
        return invitation

    async def respond_to_invitation(
        self,
        invitation_id: str,
        freelancer_id: str,
        accept: bool,
        decline_reason: str | None = None,
    ) -> ProjectInvitation:
        """Candidate accepts or declines an invitation at no charge."""
        res = await self.session.execute(
            select(ProjectInvitation).where(ProjectInvitation.id == invitation_id)
        )
        inv = res.scalar_one_or_none()
        if not inv:
            raise ValueError("Invitation not found")

        if inv.freelancer_id != freelancer_id:
            raise PermissionError("Access denied: you can only respond to invitations addressed to your profile")

        if inv.status != "pending":
            raise ValueError(f"Invitation is already in '{inv.status}' status")

        now = datetime.now(timezone.utc)
        inv_expires = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=timezone.utc)
        if inv_expires < now:
            inv.status = "expired"
            await self.session.commit()
            raise ValueError("This invitation has expired")

        inv.status = "accepted" if accept else "declined"
        inv.responded_at = now
        inv.decline_reason = decline_reason if not accept else None
        await self.session.commit()
        await self.session.refresh(inv)
        return inv

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    async def get_project_applications(
        self,
        project_id: str,
        client_user_id: str,
    ) -> list[dict[str, Any]]:
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        has_access = await self.org_service.verify_user_in_org(project.org_id, client_user_id)
        if not has_access:
            raise PermissionError("Access denied to project applications")

        res = await self.session.execute(
            select(ProjectApplication)
            .where(ProjectApplication.project_id == project_id)
            .order_by(ProjectApplication.created_at.desc())
        )
        apps = res.scalars().all()
        return [
            {
                "id": a.id,
                "project_id": a.project_id,
                "freelancer_id": a.freelancer_id,
                "status": a.status,
                "structured_pitch": a.structured_pitch,
                "relevant_artifacts": a.relevant_artifacts,
                "proposed_rate": a.proposed_rate,
                "proposed_rate_period": a.proposed_rate_period,
                "estimated_days": a.estimated_days,
                "decline_reason": a.decline_reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in apps
        ]

    async def get_freelancer_applications(
        self,
        freelancer_id: str,
    ) -> list[dict[str, Any]]:
        res = await self.session.execute(
            select(ProjectApplication)
            .where(ProjectApplication.freelancer_id == freelancer_id)
            .order_by(ProjectApplication.created_at.desc())
        )
        apps = res.scalars().all()
        return [
            {
                "id": a.id,
                "project_id": a.project_id,
                "status": a.status,
                "structured_pitch": a.structured_pitch,
                "proposed_rate": a.proposed_rate,
                "proposed_rate_period": a.proposed_rate_period,
                "estimated_days": a.estimated_days,
                "created_at": a.created_at.isoformat(),
            }
            for a in apps
        ]
