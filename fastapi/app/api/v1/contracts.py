"""Phase 16 contract-only workflows. Provider funding and payouts are unavailable."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from backend.application.services.trust.listing_reports import sanitize_report_text
from backend.application.services.network.org_service import OrgService
from database.core.session import get_db
from database.models.contracts import ContractChangeOrder, ContractDispute, ContractDisputeAddendum, ContractEvent, ContractMilestone, ProjectContract
from database.models.matching import ProjectOffer
from database.models.user import User

router = APIRouter(prefix="/contracts", tags=["contracts"])
FUNDING_STATES = {"funding_pending", "provider_confirmed_funded", "payout_pending", "paid"}
ALLOWED = {
    "draft": {"ready", "canceled"}, "ready": {"in_progress", "canceled"},
    "in_progress": {"submitted", "canceled", "disputed"},
    "submitted": {"changes_requested", "approved", "disputed"},
    "changes_requested": {"submitted", "canceled", "disputed"},
    "approved": set(), "canceled": set(), "disputed": set(),
}


class MilestoneTransition(BaseModel):
    state: Literal["ready", "in_progress", "submitted", "changes_requested", "approved", "canceled", "funding_pending", "provider_confirmed_funded", "payout_pending", "paid"]
    note: str | None = Field(default=None, max_length=2000)


class DisputeCreate(BaseModel):
    reason: Literal["scope", "quality", "timing", "payment_expectation", "conduct", "other"]
    statement: str = Field(min_length=10, max_length=5000)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class AddendumCreate(BaseModel):
    statement: str = Field(min_length=10, max_length=5000)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class ChangeOrderCreate(BaseModel):
    change_summary: str = Field(min_length=5, max_length=2000)
    scope: str = Field(min_length=5, max_length=4000)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)
    milestones: list[dict[str, Any]] = Field(default_factory=list, max_length=30)


class QuoteRequest(BaseModel):
    gross_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)


async def _contract_for_party(contract_id: str, actor: User, db: AsyncSession) -> tuple[ProjectContract, str]:
    contract = await db.get(ProjectContract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    role = "freelancer" if actor.id == contract.freelancer_id else None
    if role is None and await OrgService(db).verify_user_in_org(contract.org_id, actor.id):
        role = "client"
    if role is None:
        raise HTTPException(403, "Only contract participants may access this contract")
    return contract, role


@router.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {"mode": "contract_only", "live_payments_enabled": False,
            "provider": None, "supported": {"checkout": False, "connected_accounts": False,
            "authorized_hold": False, "funding": False, "release": False, "payout": False,
            "refund": False, "webhook_verification": False, "reconciliation": False},
            "disclosure": "No funds are collected, held, transferred, or protected by this platform. Contract templates and legal enforceability require qualified review."}


@router.post("/quote")
async def quote(payload: QuoteRequest) -> dict[str, Any]:
    """Return a transparent, explicitly hypothetical fee illustration; never a payment authorization."""
    gross = payload.gross_amount
    client_fee = (gross * Decimal("0.03")).quantize(Decimal("0.01"))
    return {"currency": payload.currency.upper(), "gross_contract_amount": format(gross, "f"),
            "client_platform_fee": {"amount": format(client_fee, "f"), "rate": "3%", "status": "hypothesis_only", "payer": "client"},
            "freelancer_platform_fee": {"amount": "0", "rate": "0%", "status": "target_only", "payer": "freelancer"},
            "processor_fee": {"amount": None, "status": "unavailable", "payer": "unknown"},
            "fx": {"rate": None, "status": "unavailable", "spread": None},
            "tax": {"amount": None, "status": "not_calculated", "payer": "requires_professional_review"},
            "estimated_client_total": format(gross + client_fee, "f"),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "payment_authorized": False, "disclosure": "Illustration only. No payment provider is connected; no amount is charged or guaranteed."}


@router.get("/by-offer/{offer_id}")
async def get_by_offer(offer_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    offer = await db.get(ProjectOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Offer not found")
    role = "freelancer" if actor.id == offer.freelancer_id else None
    if role is None and await OrgService(db).verify_user_in_org(offer.org_id, actor.id):
        role = "client"
    if role is None:
        raise HTTPException(403, "Only offer participants may access this contract")
    contract = (await db.execute(select(ProjectContract).where(ProjectContract.offer_id == offer_id))).scalar_one_or_none()
    if not contract:
        raise HTTPException(404, "Contract not found for this offer")
    return await get_contract(contract.id, actor, db)


@router.post("/from-offer/{offer_id}", status_code=201)
async def create_from_offer(offer_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    offer = await db.get(ProjectOffer, offer_id)
    if not offer or offer.status != "accepted":
        raise HTTPException(409, "A contract can only be created from an accepted offer")
    role = "freelancer" if actor.id == offer.freelancer_id else None
    if role is None and await OrgService(db).verify_user_in_org(offer.org_id, actor.id):
        role = "client"
    if role is None:
        raise HTTPException(403, "Only offer participants may create this contract")
    existing = (await db.execute(select(ProjectContract).where(ProjectContract.offer_id == offer.id))).scalar_one_or_none()
    if existing:
        return {"contract_id": existing.id, "state": existing.state, "snapshot": existing.snapshot}
    amount = Decimal(str(offer.agreed_amount))
    milestone_terms = [{**item, "acceptance_criteria": item.get("acceptance_criteria") or item.get("deliverable", "Deliverables accepted against the written scope"),
                       "included_revisions": item.get("included_revisions", 1)} for item in (offer.milestones or [])]
    snapshot = {"offer_id": offer.id, "offer_version": offer.version, "project_id": offer.project_id,
                "org_id": offer.org_id, "freelancer_id": offer.freelancer_id, "contract_type": offer.contract_type,
                "amount": format(amount, "f"), "currency": offer.currency.upper(), "scope": offer.scope_summary,
                "milestones": milestone_terms, "captured_at": datetime.now(timezone.utc).isoformat(),
                "legal_review": "required"}
    contract = ProjectContract(id=str(uuid4()), offer_id=offer.id, project_id=offer.project_id, org_id=offer.org_id,
                               freelancer_id=offer.freelancer_id, snapshot=snapshot)
    db.add(contract)
    await db.flush()
    for i, terms in enumerate(milestone_terms, 1):
        db.add(ContractMilestone(id=str(uuid4()), contract_id=contract.id, position=i, terms=terms, state="draft"))
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id, event_type="contract_created", payload={"offer_version": offer.version}))
    await db.commit()
    return {"contract_id": contract.id, "state": contract.state, "snapshot": snapshot}


@router.get("/{contract_id}")
async def get_contract(contract_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, _ = await _contract_for_party(contract_id, actor, db)
    milestones = (await db.execute(select(ContractMilestone).where(ContractMilestone.contract_id == contract_id).order_by(ContractMilestone.position))).scalars().all()
    return {"contract_id": contract.id, "state": contract.state, "snapshot": contract.snapshot,
            "acknowledgments": {"client": contract.client_ack_at is not None, "freelancer": contract.freelancer_ack_at is not None},
            "milestones": [{"id": m.id, "position": m.position, "terms": m.terms, "state": m.state} for m in milestones]}


@router.get("/{contract_id}/events")
async def contract_events(contract_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    await _contract_for_party(contract_id, actor, db)
    rows = (await db.execute(select(ContractEvent).where(ContractEvent.contract_id == contract_id).order_by(ContractEvent.created_at, ContractEvent.id))).scalars().all()
    return {"events": [{"id": event.id, "actor_id": event.actor_id, "type": event.event_type,
                         "payload": event.payload, "created_at": event.created_at.isoformat()} for event in rows]}


@router.post("/{contract_id}/acknowledge")
async def acknowledge(contract_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, role = await _contract_for_party(contract_id, actor, db)
    if contract.state not in {"awaiting_acknowledgments", "active"}:
        raise HTTPException(409, "Contract is not awaiting acknowledgment")
    now = datetime.now(timezone.utc)
    if role == "client": contract.client_ack_at = contract.client_ack_at or now
    else: contract.freelancer_ack_at = contract.freelancer_ack_at or now
    if contract.client_ack_at and contract.freelancer_ack_at:
        contract.state = "active"
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id, event_type="terms_acknowledged", payload={"role": role, "snapshot_offer_version": contract.snapshot["offer_version"]}))
    await db.commit()
    return {"contract_id": contract.id, "state": contract.state}


@router.post("/{contract_id}/terminate")
async def request_termination(contract_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, _ = await _contract_for_party(contract_id, actor, db)
    now = datetime.now(timezone.utc)
    if contract.state == "active":
        contract.state = "pending_termination"
        contract.termination_requested_by = actor.id
        contract.termination_requested_at = now
        result = "pending_counterparty_acknowledgment"
        event_type = "termination_requested"
    elif contract.state == "pending_termination":
        if contract.termination_requested_by == actor.id:
            result = "pending_counterparty_acknowledgment"
            event_type = None
        else:
            contract.state = "terminated"
            result = "terminated"
            event_type = "termination_bilaterally_accepted"
    else:
        raise HTTPException(409, "Only active contracts can request termination")
    if event_type:
        db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id, event_type=event_type, payload={"state": contract.state}))
    await db.commit()
    return {"contract_id": contract.id, "state": contract.state, "result": result}


@router.post("/{contract_id}/milestones/{milestone_id}/transition")
async def transition_milestone(contract_id: str, milestone_id: str, payload: MilestoneTransition, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, role = await _contract_for_party(contract_id, actor, db)
    milestone = await db.get(ContractMilestone, milestone_id)
    if not milestone or milestone.contract_id != contract.id:
        raise HTTPException(404, "Milestone not found")
    if payload.state in FUNDING_STATES:
        raise HTTPException(409, "Payment provider capability is unavailable; funding and payout are disabled")
    if contract.state != "active":
        raise HTTPException(409, "Both parties must acknowledge the contract before milestone work")
    if payload.state not in ALLOWED.get(milestone.state, set()):
        raise HTTPException(409, f"Milestone cannot transition from {milestone.state} to {payload.state}")
    if payload.state in {"submitted"} and role != "freelancer": raise HTTPException(403, "Only the freelancer may submit delivery")
    if payload.state in {"approved", "changes_requested"} and role != "client": raise HTTPException(403, "Only the client may review delivery")
    if payload.state == "in_progress" and role != "freelancer": raise HTTPException(403, "Only the freelancer may start milestone work")
    previous_state = milestone.state
    milestone.state = payload.state
    milestone.updated_at = datetime.now(timezone.utc)
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id, event_type="milestone_transition", payload={"milestone_id": milestone.id, "from": previous_state, "to": payload.state, "note": payload.note}))
    await db.commit()
    return {"milestone_id": milestone.id, "state": milestone.state, "payment_state": "unsupported"}


@router.post("/{contract_id}/disputes", status_code=201)
async def file_dispute(contract_id: str, payload: DisputeCreate, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, _ = await _contract_for_party(contract_id, actor, db)
    if contract.state not in {"active", "disputed"}:
        raise HTTPException(409, "Disputes can be filed only for active contracts")
    statement = sanitize_report_text(payload.statement, limit=4500) or "Dispute report submitted"
    # Evidence is retained for human review only and never echoed in the API response.
    private_evidence = list(payload.evidence or [])
    dispute = ContractDispute(
        id=str(uuid4()),
        contract_id=contract.id,
        reporter_id=actor.id,
        reason=payload.reason,
        statement=statement,
        evidence=private_evidence,
    )
    contract.state = "disputed"
    db.add(dispute)
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id, event_type="dispute_filed", payload={"dispute_id": dispute.id, "reason": payload.reason, "review": "human_required"}))
    await db.commit()
    return {"dispute_id": dispute.id, "state": "open", "contract_state": contract.state, "review": "human_required", "provider_escalation": "unsupported"}


@router.post("/{contract_id}/change-orders", status_code=201)
async def propose_change_order(contract_id: str, payload: ChangeOrderCreate, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, _ = await _contract_for_party(contract_id, actor, db)
    if contract.state != "active":
        raise HTTPException(409, "Change orders require an active contract")
    if payload.currency.upper() != contract.snapshot["currency"]:
        raise HTTPException(400, "Change order currency must match the contract currency")
    change = ContractChangeOrder(id=str(uuid4()), contract_id=contract.id, author_id=actor.id,
        snapshot={"change_summary": payload.change_summary, "scope": payload.scope,
                  "amount": format(payload.amount, "f"), "currency": payload.currency.upper(),
                  "milestones": payload.milestones, "captured_at": datetime.now(timezone.utc).isoformat()})
    db.add(change)
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id,
                         event_type="change_order_proposed", payload={"change_order_id": change.id}))
    await db.commit()
    return {"change_order_id": change.id, "state": change.state, "snapshot": change.snapshot}


@router.get("/{contract_id}/change-orders")
async def list_change_orders(contract_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    await _contract_for_party(contract_id, actor, db)
    rows = (await db.execute(select(ContractChangeOrder).where(ContractChangeOrder.contract_id == contract_id).order_by(ContractChangeOrder.created_at))).scalars().all()
    return {"change_orders": [{"id": c.id, "author_id": c.author_id, "snapshot": c.snapshot, "state": c.state,
                               "client_accepted": c.client_accepted_at is not None, "freelancer_accepted": c.freelancer_accepted_at is not None,
                               "created_at": c.created_at.isoformat()} for c in rows]}


@router.post("/{contract_id}/change-orders/{change_order_id}/reject")
async def reject_change_order(contract_id: str, change_order_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, role = await _contract_for_party(contract_id, actor, db)
    change = await db.get(ContractChangeOrder, change_order_id)
    if not change or change.contract_id != contract.id:
        raise HTTPException(404, "Change order not found")
    if change.state != "awaiting_acceptance":
        raise HTTPException(409, "Change order is no longer open")
    change.state = "rejected"
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id,
        event_type="change_order_rejected", payload={"change_order_id": change.id, "role": role}))
    await db.commit()
    return {"change_order_id": change.id, "state": change.state}


@router.get("/{contract_id}/disputes")
async def list_disputes(contract_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    await _contract_for_party(contract_id, actor, db)
    rows = (await db.execute(select(ContractDispute).where(ContractDispute.contract_id == contract_id).order_by(ContractDispute.created_at))).scalars().all()
    return {"disputes": [{"id": d.id, "reporter_id": d.reporter_id, "reason": d.reason, "statement": sanitize_report_text(d.statement, limit=4500), "state": d.state, "created_at": d.created_at.isoformat()} for d in rows]}


@router.get("/{contract_id}/disputes/{dispute_id}/addenda")
async def list_dispute_addenda(contract_id: str, dispute_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    await _contract_for_party(contract_id, actor, db)
    dispute = await db.get(ContractDispute, dispute_id)
    if not dispute or dispute.contract_id != contract_id:
        raise HTTPException(404, "Dispute not found")
    rows = (await db.execute(select(ContractDisputeAddendum).where(ContractDisputeAddendum.dispute_id == dispute_id).order_by(ContractDisputeAddendum.created_at))).scalars().all()
    return {"addenda": [{"id": a.id, "author_id": a.author_id, "statement": sanitize_report_text(a.statement, limit=2500), "created_at": a.created_at.isoformat()} for a in rows]}


@router.post("/{contract_id}/disputes/{dispute_id}/addenda", status_code=201)
async def add_dispute_addendum(contract_id: str, dispute_id: str, payload: AddendumCreate, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, _ = await _contract_for_party(contract_id, actor, db)
    dispute = await db.get(ContractDispute, dispute_id)
    if not dispute or dispute.contract_id != contract.id:
        raise HTTPException(404, "Dispute not found")
    statement = sanitize_report_text(payload.statement, limit=2500) or "Dispute addendum submitted"
    # Evidence stays private for reviewers; response never includes the payload.
    addendum = ContractDisputeAddendum(
        id=str(uuid4()),
        dispute_id=dispute.id,
        author_id=actor.id,
        statement=statement,
        evidence=list(payload.evidence or []),
    )
    db.add(addendum)
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id,
                         event_type="dispute_addendum_filed", payload={"dispute_id": dispute.id, "addendum_id": addendum.id}))
    await db.commit()
    return {"addendum_id": addendum.id, "dispute_id": dispute.id, "immutable": True, "review": "human_required"}


@router.post("/{contract_id}/change-orders/{change_order_id}/accept")
async def accept_change_order(contract_id: str, change_order_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    contract, role = await _contract_for_party(contract_id, actor, db)
    change = await db.get(ContractChangeOrder, change_order_id)
    if not change or change.contract_id != contract.id:
        raise HTTPException(404, "Change order not found")
    if change.state != "awaiting_acceptance":
        raise HTTPException(409, "Change order is no longer open")
    now = datetime.now(timezone.utc)
    if role == "client": change.client_accepted_at = change.client_accepted_at or now
    else: change.freelancer_accepted_at = change.freelancer_accepted_at or now
    if change.client_accepted_at and change.freelancer_accepted_at:
        change.state = "accepted"
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id,
        event_type="change_order_acknowledged", payload={"change_order_id": change.id, "role": role, "state": change.state}))
    await db.commit()
    return {"change_order_id": change.id, "state": change.state,
            "acknowledgments": {"client": change.client_accepted_at is not None, "freelancer": change.freelancer_accepted_at is not None}}
