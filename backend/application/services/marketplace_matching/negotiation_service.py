"""Phase 15 — Negotiation assistant, bilateral offers, milestone agreements, and concurrency guards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.network.org_service import OrgService
from database.models.matching import (
    OFFER_STATUSES,
    ProjectApplication,
    ProjectOffer,
    ProjectOfferRevision,
)
from database.models.project import NativeProject, ProjectStatusHistory


class ConflictError(Exception):
    """Raised when an offer cannot be accepted due to conflicting filled position."""
    pass


class NegotiationAssistant:
    """Helper assistant that standardizes contract milestone schedules and scope clarity."""

    @classmethod
    def draft_negotiated_terms(
        cls,
        base_title: str,
        agreed_amount: float,
        contract_type: str = "fixed_price",
        proposed_milestones: list[dict[str, Any]] | None = None,
        custom_scope: str | None = None,
    ) -> dict[str, Any]:
        """Draft a structured bilateral agreement with milestone payment breakdown."""
        if agreed_amount <= 0:
            raise ValueError("Agreed amount must be positive")

        milestones = []
        if proposed_milestones:
            for i, m in enumerate(proposed_milestones, 1):
                milestones.append({
                    "step": i,
                    "title": str(m.get("title", f"Milestone {i}")),
                    "amount": float(m.get("amount", round(agreed_amount / len(proposed_milestones), 2))),
                    "deliverable": str(m.get("deliverable", "Agreed milestone artifact")),
                    "days": int(m.get("days", 7)),
                })
        else:
            # Standard 2-milestone default: 50% Architecture/MVP, 50% Integration/Delivery
            half = round(agreed_amount / 2, 2)
            rem = round(agreed_amount - half, 2)
            milestones = [
                {
                    "step": 1,
                    "title": "Core Architecture & MVP Milestone",
                    "amount": half,
                    "deliverable": "Working baseline code, schema setup, and unit test suite",
                    "days": 10,
                },
                {
                    "step": 2,
                    "title": "Final Integration, Documentation & Verification",
                    "amount": rem,
                    "deliverable": "Full end-to-end integration, API documentation, and sign-off",
                    "days": 14,
                },
            ]

        summary = custom_scope or f"Bilateral agreement for {base_title}. Total agreed: ${agreed_amount:g} under {contract_type} terms."
        return {
            "contract_type": contract_type,
            "agreed_amount": agreed_amount,
            "milestones": milestones,
            "scope_summary": summary,
        }


class ProjectNegotiationService:
    """Manages bilateral offer proposals, counter-proposals, and concurrency-safe acceptance."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_service = OrgService(session)

    async def create_offer(
        self,
        project_id: str,
        application_id: str,
        actor_id: str,
        agreed_amount: float,
        contract_type: str = "fixed_price",
        milestones: list[dict[str, Any]] | None = None,
        scope_summary: str | None = None,
        decision_deadline_days: int = 7,
        conversation_id: str | None = None,
    ) -> ProjectOffer:
        """Create a new formal offer (starts in pending_review)."""
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        app_res = await self.session.execute(
            select(ProjectApplication).where(ProjectApplication.id == application_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ValueError("Application not found")

        # Determine creator role
        is_client = await self.org_service.verify_user_in_org(project.org_id, actor_id)
        if is_client:
            creator_role = "client"
        elif actor_id == application.freelancer_id:
            creator_role = "freelancer"
        else:
            raise PermissionError("Access denied: only client org members or candidate can make offers")

        if agreed_amount <= 0:
            raise ValueError("Offer amount must be greater than 0")

        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=max(1, decision_deadline_days))

        terms = NegotiationAssistant.draft_negotiated_terms(
            base_title=project.title,
            agreed_amount=agreed_amount,
            contract_type=contract_type,
            proposed_milestones=milestones,
            custom_scope=scope_summary,
        )

        offer = ProjectOffer(
            id=str(uuid4()),
            project_id=project_id,
            application_id=application_id,
            conversation_id=conversation_id,
            org_id=project.org_id,
            freelancer_id=application.freelancer_id,
            creator_id=actor_id,
            creator_role=creator_role,
            version=1,
            status="pending_review",
            contract_type=terms["contract_type"],
            agreed_amount=terms["agreed_amount"],
            currency=project.currency or "USD",
            milestones=terms["milestones"],
            scope_summary=terms["scope_summary"],
            decision_deadline=deadline,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        self.session.add(offer)

        # Update application status to negotiating
        if application.status in {"submitted", "shortlisted"}:
            application.status = "negotiating"

        await self.session.commit()
        await self.session.refresh(offer)
        return offer

    async def counter_propose_offer(
        self,
        offer_id: str,
        actor_id: str,
        revised_amount: float,
        change_summary: str,
        contract_type: str | None = None,
        milestones: list[dict[str, Any]] | None = None,
        scope_summary: str | None = None,
    ) -> ProjectOffer:
        """Submit a counter-proposal revision, incrementing version and resetting review status."""
        offer_res = await self.session.execute(
            select(ProjectOffer).where(ProjectOffer.id == offer_id)
        )
        offer = offer_res.scalar_one_or_none()
        if not offer:
            raise ValueError("Offer not found")

        if offer.status != "pending_review":
            raise ValueError(f"Cannot counter-propose an offer in status '{offer.status}'")

        # Verify actor access
        is_client = await self.org_service.verify_user_in_org(offer.org_id, actor_id)
        if is_client:
            author_role = "client"
        elif actor_id == offer.freelancer_id:
            author_role = "freelancer"
        else:
            raise PermissionError("Access denied: unauthorized to revise this offer")

        if revised_amount <= 0:
            raise ValueError("Revised amount must be greater than 0")

        now = datetime.now(timezone.utc)
        c_type = contract_type or offer.contract_type
        c_scope = scope_summary or offer.scope_summary
        c_milestones = milestones or offer.milestones

        # 1. Create Revision Audit record for previous version
        revision = ProjectOfferRevision(
            id=str(uuid4()),
            offer_id=offer.id,
            version=offer.version,
            author_id=actor_id,
            author_role=author_role,
            change_summary=change_summary,
            contract_type=c_type,
            agreed_amount=revised_amount,
            milestones=c_milestones,
            scope_summary=c_scope,
            created_at=now,
        )
        self.session.add(revision)

        # 2. Update offer fields
        offer.version += 1
        offer.creator_id = actor_id
        offer.creator_role = author_role
        offer.contract_type = c_type
        offer.agreed_amount = revised_amount
        offer.milestones = c_milestones
        offer.scope_summary = c_scope
        offer.lock_version += 1
        offer.updated_at = now

        await self.session.commit()
        await self.session.refresh(offer)
        return offer

    async def accept_offer(
        self,
        offer_id: str,
        actor_id: str,
    ) -> ProjectOffer:
        """Bilateral offer acceptance with strict concurrency protection.

        Guarantees:
        - Only 1 offer can be accepted per project seat/position.
        - Concurrent acceptances fail with ConflictError.
        - Project automatically transitions to 'offered_hired'.
        - Other pending offers for this project are automatically marked superseded.
        """
        # Load offer
        offer_res = await self.session.execute(
            select(ProjectOffer).where(ProjectOffer.id == offer_id)
        )
        offer = offer_res.scalar_one_or_none()
        if not offer:
            raise ValueError("Offer not found")

        if offer.status == "superseded":
            raise ConflictError(
                "Conflict (409): Offer has been superseded by another accepted offer or the position has already been filled."
            )
        if offer.status != "pending_review":
            raise ValueError(f"Offer is not in pending review (current: '{offer.status}')")

        # Load project
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == offer.project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        # Check if project position is already filled
        if project.status == "offered_hired":
            raise ConflictError(
                "Conflict (409): Project position has already been filled by another accepted offer."
            )

        # Verify acceptance authorization: Must be the counterpart of the creator
        is_client = await self.org_service.verify_user_in_org(offer.org_id, actor_id)
        if offer.creator_role == "client":
            # Must be accepted by the freelancer
            if actor_id != offer.freelancer_id:
                raise PermissionError("Offer extended by client must be accepted by the freelancer")
        else:
            # Must be accepted by a client org member
            if not is_client:
                raise PermissionError("Offer proposed by freelancer must be accepted by the client organization")

        # Deadline check
        now = datetime.now(timezone.utc)
        deadline = offer.decision_deadline if offer.decision_deadline.tzinfo else offer.decision_deadline.replace(tzinfo=timezone.utc)
        if deadline < now:
            offer.status = "expired"
            await self.session.commit()
            raise ValueError("Offer decision deadline has expired")

        # Mark offer accepted
        offer.status = "accepted"
        offer.accepted_at = now
        offer.updated_at = now
        offer.lock_version += 1

        # Mark project as offered_hired
        prev_proj_status = project.status
        project.status = "offered_hired"
        project.updated_at = now

        # Add project status audit record
        history = ProjectStatusHistory(
            id=str(uuid4()),
            project_id=project.id,
            from_status=prev_proj_status,
            to_status="offered_hired",
            action="accept_offer",
            actor_id=actor_id,
            reason=f"Offer {offer.id} v{offer.version} accepted by {actor_id}",
            metadata_json={"offer_id": offer.id, "amount": offer.agreed_amount},
            created_at=now,
        )
        self.session.add(history)

        # Mark application as accepted
        app_res = await self.session.execute(
            select(ProjectApplication).where(ProjectApplication.id == offer.application_id)
        )
        application = app_res.scalar_one_or_none()
        if application:
            application.status = "accepted"
            application.updated_at = now

        # Concurrency safety: Supersede / cancel any OTHER pending offers for this project
        other_offers_res = await self.session.execute(
            select(ProjectOffer).where(
                ProjectOffer.project_id == project.id,
                ProjectOffer.id != offer.id,
                ProjectOffer.status == "pending_review",
            )
        )
        for other in other_offers_res.scalars().all():
            other.status = "superseded"
            other.rejection_reason = "Position filled by another offer"
            other.updated_at = now

        await self.session.commit()
        await self.session.refresh(offer)
        return offer

    async def decline_offer(
        self,
        offer_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> ProjectOffer:
        """Decline offer. No negative public rating penalty."""
        offer_res = await self.session.execute(
            select(ProjectOffer).where(ProjectOffer.id == offer_id)
        )
        offer = offer_res.scalar_one_or_none()
        if not offer:
            raise ValueError("Offer not found")

        if offer.status != "pending_review":
            raise ValueError(f"Cannot decline offer in status '{offer.status}'")

        is_client = await self.org_service.verify_user_in_org(offer.org_id, actor_id)
        if actor_id != offer.freelancer_id and not is_client:
            raise PermissionError("Access denied: unauthorized to decline this offer")

        now = datetime.now(timezone.utc)
        offer.status = "declined"
        offer.rejected_at = now
        offer.rejection_reason = reason or ("Declined by freelancer" if actor_id == offer.freelancer_id else "Declined by client")
        offer.updated_at = now

        await self.session.commit()
        await self.session.refresh(offer)
        return offer

    async def get_project_offers(
        self,
        project_id: str,
        actor_id: str,
    ) -> list[dict[str, Any]]:
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        is_client = await self.org_service.verify_user_in_org(project.org_id, actor_id)

        stmt = select(ProjectOffer).where(ProjectOffer.project_id == project_id)
        if not is_client:
            # Freelancers can only view offers relating to themselves
            stmt = stmt.where(ProjectOffer.freelancer_id == actor_id)

        stmt = stmt.order_by(ProjectOffer.created_at.desc())
        res = await self.session.execute(stmt)
        offers = res.scalars().all()
        return [
            {
                "id": o.id,
                "project_id": o.project_id,
                "application_id": o.application_id,
                "conversation_id": o.conversation_id,
                "freelancer_id": o.freelancer_id,
                "creator_id": o.creator_id,
                "creator_role": o.creator_role,
                "version": o.version,
                "status": o.status,
                "contract_type": o.contract_type,
                "agreed_amount": o.agreed_amount,
                "currency": o.currency,
                "milestones": o.milestones,
                "scope_summary": o.scope_summary,
                "decision_deadline": o.decision_deadline.isoformat(),
                "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
                "rejection_reason": o.rejection_reason,
                "created_at": o.created_at.isoformat(),
            }
            for o in offers
        ]
