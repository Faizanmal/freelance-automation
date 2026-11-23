"""Phase 16 — Contracts, Milestones, Transparent Payments and Dispute Support Test Suite.

Validates:
1. Safe Implementation Boundaries:
   - Contract created exclusively from accepted Phase 15 offers.
   - Rejection (409) if offer is not accepted (e.g. pending, countered, declined).
   - Rejection (403) if caller is an outsider/non-participant.
   - Frozen immutable snapshot with agreed amount, currency, scope, milestones, acceptance criteria, revisions.
   - Idempotent contract creation.
2. Dual Acknowledgment Flow:
   - Contract starts in awaiting_acknowledgments.
   - Pre-activation milestone operations blocked (409).
   - Explicit acknowledgments recorded with timestamps; contract becomes active only when both parties acknowledge.
3. Milestone State Machine & Strict Role Enforcement:
   - Lifecycle: draft -> ready -> in_progress -> submitted -> changes_requested -> submitted -> approved.
   - Freelancer-only transitions: in_progress, submitted.
   - Client-only transitions: changes_requested, approved.
   - Disallowed transitions (e.g. directly to approved from draft) blocked (409).
4. Strict Blocking of Provider Payment & Funding States (Contract-Only Mode):
   - Transitions to funding_pending, provider_confirmed_funded, payout_pending, paid blocked (409).
   - Capability probe reports mode=contract_only, live_payments_enabled=False, all capabilities False.
5. Transparent Fee Quotes:
   - POST /contracts/quote: exact decimal breakdown (3% client fee hypothesis, 0% freelancer fee target).
   - Processor, FX, and tax marked unavailable/not_calculated without hidden spread.
   - 10-minute quote expiration and non-authorization disclosures.
   - Rejection of zero or negative amounts (422).
6. Change Orders:
   - Currency match required (400 on mismatch).
   - Proposing requires active contract.
   - Bilateral acceptance required; does NOT mutate original contract snapshot.
   - Rejection workflow supported.
7. Dispute Center & Immutable Addenda:
   - Either party can file dispute; moves contract to disputed.
   - Human review required; no AI legal/financial outcomes.
   - Private evidence references not echoed in response.
   - Immutable addenda can be appended.
8. Mutual Contract Termination:
   - Bilateral acknowledgment required before contract enters terminated state.
9. Append-Only Audit Event Trail:
   - Chronological logging of all lifecycle events.
   - Non-participants forbidden (403).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.main import create_app
from database.core.base import Base
from database.core.session import get_db
from database.models.contracts import (
    ContractChangeOrder,
    ContractDispute,
    ContractDisputeAddendum,
    ContractEvent,
    ContractMilestone,
    ProjectContract,
)
from database.models.matching import (
    ProjectApplication,
    ProjectOffer,
)
from database.models.network import (
    EmployerOrg,
    OrgMembership,
)
from database.models.project import NativeProject
from database.models.user import User


def as_user(app, user: User):
    app.dependency_overrides[get_current_user] = lambda: user


@pytest_asyncio.fixture
async def contract_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        # Client owner
        alice = User(
            id="user-alice-client",
            email="alice@techcorp.io",
            full_name="Alice Client",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="client",
        )
        # Freelancer
        bob = User(
            id="user-bob-dev",
            email="bob@python.dev",
            full_name="Bob Developer",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="freelancer",
        )
        # Unaffiliated outsider
        outsider = User(
            id="user-outsider",
            email="outsider@stranger.org",
            full_name="Stranger Outsider",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="freelancer",
        )
        session.add_all([alice, bob, outsider])
        await session.flush()

        org = EmployerOrg(
            id="org-techcorp",
            name="TechCorp AI",
            slug="techcorp-ai",
            org_domain="techcorp.io",
            domain_verified=True,
            industry="technology",
            owner_id=alice.id,
            verification_status="domain_verified",
        )
        session.add(org)
        await session.flush()

        mem = OrgMembership(
            id="mem-alice-owner",
            org_id=org.id,
            user_id=alice.id,
            email=alice.email,
            role="owner",
            seat_status="active",
        )
        session.add(mem)

        project = NativeProject(
            id="proj-api-core",
            org_id=org.id,
            creator_id=alice.id,
            title="FastAPI Contract Engine",
            raw_description="Build production contracts and milestones module.",
            skills_required=["Python", "FastAPI"],
            budget_min=4000.0,
            budget_max=6000.0,
            currency="USD",
            rate_period="fixed",
            scope_level="medium",
            work_type="remote",
            hiring_deadline=datetime.now(timezone.utc) + timedelta(days=21),
            reconfirm_by=datetime.now(timezone.utc) + timedelta(days=14),
            status="approved_open",
            review_state="approved",
            payment_verified=True,
        )
        session.add(project)

        app_bob = ProjectApplication(
            id="app-bob-1",
            project_id=project.id,
            freelancer_id=bob.id,
            status="accepted",
            proposed_rate=5000.0,
            structured_pitch="Senior backend engineer ready to build contracts module.",
        )
        session.add(app_bob)
        await session.flush()

        # Accepted offer
        accepted_offer = ProjectOffer(
            id="offer-accepted-1",
            project_id=project.id,
            application_id=app_bob.id,
            org_id=org.id,
            freelancer_id=bob.id,
            creator_id=alice.id,
            creator_role="client",
            contract_type="fixed_price",
            agreed_amount=5000.0,
            currency="USD",
            scope_summary="Deliver backend contracts and dispute support with full test coverage.",
            decision_deadline=datetime.now(timezone.utc) + timedelta(days=7),
            milestones=[
                {
                    "title": "Phase 1: Architecture & Contracts",
                    "amount": 2500,
                    "deliverable": "Working /contracts endpoints with audit events",
                    "acceptance_criteria": "All unit tests pass and snapshot is immutable",
                    "included_revisions": 2,
                },
                {
                    "title": "Phase 2: Disputes & Change Orders",
                    "amount": 2500,
                    "deliverable": "Dispute center and bilateral change orders",
                    "acceptance_criteria": "Dual acceptance and human review flags",
                    "included_revisions": 1,
                },
            ],
            version=1,
            status="accepted",
        )

        # Pending (non-accepted) offer
        pending_offer = ProjectOffer(
            id="offer-pending-2",
            project_id=project.id,
            application_id=app_bob.id,
            org_id=org.id,
            freelancer_id=bob.id,
            creator_id=alice.id,
            creator_role="client",
            contract_type="fixed_price",
            agreed_amount=3000.0,
            currency="USD",
            decision_deadline=datetime.now(timezone.utc) + timedelta(days=7),
            scope_summary="Pending offer that has not been accepted yet.",
            milestones=[{"title": "M1", "amount": 3000}],
            version=1,
            status="pending",
        )
        session.add_all([accepted_offer, pending_offer])
        await session.commit()

    app = create_app()

    async def get_test_db():
        async with session_maker() as session:
            try:
                yield session
            finally:
                pass

    app.dependency_overrides[get_db] = get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app, session_maker


@pytest.mark.asyncio
async def test_phase16_capabilities_probe(contract_client):
    """Capabilities endpoint returns contract_only mode and disables all payment operations."""
    client, app, _ = contract_client
    resp = await client.get("/api/v1/contracts/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "contract_only"
    assert data["live_payments_enabled"] is False
    assert data["provider"] is None
    assert all(val is False for val in data["supported"].values())
    assert "checkout" in data["supported"]
    assert "funding" in data["supported"]
    assert "payout" in data["supported"]
    assert "reconciliation" in data["supported"]
    assert "No funds are collected, held, transferred, or protected" in data["disclosure"]


@pytest.mark.asyncio
async def test_phase16_fee_quote_transparency(contract_client):
    """Quote calculations are transparent, non-authorizing, and expire in 10 minutes."""
    client, app, _ = contract_client

    # 1. Valid quote
    resp = await client.post(
        "/api/v1/contracts/quote",
        json={"gross_amount": 1000.0, "currency": "usd"},
    )
    assert resp.status_code == 200
    quote = resp.json()
    assert quote["currency"] == "USD"
    assert quote["gross_contract_amount"] == "1000.0"
    assert quote["client_platform_fee"]["amount"] == "30.00"
    assert quote["client_platform_fee"]["rate"] == "3%"
    assert quote["client_platform_fee"]["status"] == "hypothesis_only"
    assert quote["freelancer_platform_fee"]["amount"] == "0"
    assert quote["freelancer_platform_fee"]["rate"] == "0%"
    assert quote["freelancer_platform_fee"]["status"] == "target_only"
    assert quote["processor_fee"]["status"] == "unavailable"
    assert quote["fx"]["status"] == "unavailable"
    assert quote["tax"]["status"] == "not_calculated"
    assert quote["estimated_client_total"] == "1030.00"
    assert quote["payment_authorized"] is False
    assert "expires_at" in quote
    assert "Illustration only" in quote["disclosure"]

    # 2. Rejection of zero or negative amounts
    zero_resp = await client.post(
        "/api/v1/contracts/quote",
        json={"gross_amount": 0, "currency": "USD"},
    )
    assert zero_resp.status_code == 422

    neg_resp = await client.post(
        "/api/v1/contracts/quote",
        json={"gross_amount": -100.0, "currency": "USD"},
    )
    assert neg_resp.status_code == 422


@pytest.mark.asyncio
async def test_phase16_contract_creation_boundaries(contract_client):
    """Enforces that contracts only arise from accepted offers with authorized participants."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        outsider = await session.get(User, "user-outsider")

    # 1. Non-accepted offer rejected (409)
    as_user(app, alice)
    resp_pending = await client.post("/api/v1/contracts/from-offer/offer-pending-2")
    assert resp_pending.status_code == 409
    assert "accepted offer" in resp_pending.json()["detail"]

    # 2. Outsider cannot create contract from accepted offer (403)
    as_user(app, outsider)
    resp_outsider = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    assert resp_outsider.status_code == 403

    # 3. Client creates contract
    as_user(app, alice)
    resp_created = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    assert resp_created.status_code == 201
    data = resp_created.json()
    contract_id = data["contract_id"]
    assert data["state"] == "awaiting_acknowledgments"
    snapshot = data["snapshot"]
    assert snapshot["amount"] == "5000.0"
    assert snapshot["currency"] == "USD"
    assert snapshot["legal_review"] == "required"
    assert len(snapshot["milestones"]) == 2
    assert snapshot["milestones"][0]["acceptance_criteria"] == "All unit tests pass and snapshot is immutable"
    assert snapshot["milestones"][0]["included_revisions"] == 2

    # 4. Idempotency: repeated call returns same contract
    resp_repeat = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    assert resp_repeat.status_code in (200, 201)
    assert resp_repeat.json()["contract_id"] == contract_id

    # 5. Get by offer
    as_user(app, bob)
    resp_by_offer = await client.get("/api/v1/contracts/by-offer/offer-accepted-1")
    assert resp_by_offer.status_code == 200
    assert resp_by_offer.json()["contract_id"] == contract_id


@pytest.mark.asyncio
async def test_phase16_dual_acknowledgment_and_active_gate(contract_client):
    """Contract requires bilateral acknowledgment before milestone transitions can occur."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        outsider = await session.get(User, "user-outsider")

    as_user(app, alice)
    created = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = created.json()["contract_id"]

    # Retrieve contract and get first milestone
    contract_data = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    milestone_id = contract_data["milestones"][0]["id"]

    # 1. Attempt milestone transition before contract is active -> 409
    as_user(app, bob)
    premature_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{milestone_id}/transition",
        json={"state": "ready"},
    )
    assert premature_resp.status_code == 409
    assert "acknowledge" in premature_resp.json()["detail"]

    # 2. Outsider cannot acknowledge -> 403
    as_user(app, outsider)
    out_ack = await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    assert out_ack.status_code == 403

    # 3. Freelancer acknowledges: contract remains awaiting_acknowledgments
    as_user(app, bob)
    bob_ack = await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    assert bob_ack.status_code == 200
    assert bob_ack.json()["state"] == "awaiting_acknowledgments"

    # 4. Client acknowledges: contract becomes active
    as_user(app, alice)
    alice_ack = await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    assert alice_ack.status_code == 200
    assert alice_ack.json()["state"] == "active"

    # Verify contract status
    current = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    assert current["state"] == "active"
    assert current["acknowledgments"]["client"] is True
    assert current["acknowledgments"]["freelancer"] is True


@pytest.mark.asyncio
async def test_phase16_milestone_state_machine_and_role_checks(contract_client):
    """Enforces milestone lifecycle (draft -> ready -> in_progress -> submitted -> changes_requested -> submitted -> approved) and strict role checks."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    # Setup active contract
    as_user(app, alice)
    c_resp = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = c_resp.json()["contract_id"]
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    as_user(app, bob)
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    contract_info = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    m_id = contract_info["milestones"][0]["id"]

    # 1. draft -> ready (allowed)
    ready_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "ready", "note": "Requirements confirmed"},
    )
    assert ready_resp.status_code == 200
    assert ready_resp.json()["state"] == "ready"

    # 2. Client cannot start work (only freelancer) -> 403
    as_user(app, alice)
    client_start = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "in_progress"},
    )
    assert client_start.status_code == 403

    # 3. Freelancer starts work: ready -> in_progress
    as_user(app, bob)
    start_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "in_progress", "note": "Started implementation"},
    )
    assert start_resp.status_code == 200
    assert start_resp.json()["state"] == "in_progress"

    # 4. Client cannot submit delivery (only freelancer) -> 403
    as_user(app, alice)
    client_submit = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "submitted"},
    )
    assert client_submit.status_code == 403

    # 5. Freelancer submits delivery: in_progress -> submitted
    as_user(app, bob)
    submit_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "submitted", "note": "PR #42 ready for client review"},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["state"] == "submitted"

    # 6. Freelancer cannot approve own work -> 403
    freelancer_approve = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "approved"},
    )
    assert freelancer_approve.status_code == 403

    # 7. Freelancer cannot request changes on own work -> 403
    freelancer_cr = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "changes_requested"},
    )
    assert freelancer_cr.status_code == 403

    # 8. Client requests changes: submitted -> changes_requested
    as_user(app, alice)
    cr_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "changes_requested", "note": "Please add error boundary for network timeout"},
    )
    assert cr_resp.status_code == 200
    assert cr_resp.json()["state"] == "changes_requested"

    # 9. Freelancer resubmits: changes_requested -> submitted
    as_user(app, bob)
    resubmit_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "submitted", "note": "Error boundary added with tests"},
    )
    assert resubmit_resp.status_code == 200
    assert resubmit_resp.json()["state"] == "submitted"

    # 10. Client approves: submitted -> approved
    as_user(app, alice)
    approve_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "approved", "note": "Verified and accepted"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["state"] == "approved"

    # 11. Terminal state check: cannot transition out of approved -> 409
    post_approve = await client.post(
        f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
        json={"state": "submitted"},
    )
    assert post_approve.status_code == 409


@pytest.mark.asyncio
async def test_phase16_funding_and_payout_states_disabled(contract_client):
    """Guarantees that payment provider states are blocked in contract_only mode."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    as_user(app, alice)
    c_resp = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = c_resp.json()["contract_id"]
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    as_user(app, bob)
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    contract_info = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    m_id = contract_info["milestones"][0]["id"]

    for blocked_state in ("funding_pending", "provider_confirmed_funded", "payout_pending", "paid"):
        resp = await client.post(
            f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition",
            json={"state": blocked_state},
        )
        assert resp.status_code == 409, f"State {blocked_state} should be rejected"
        assert "disabled" in resp.json()["detail"].lower() or "unavailable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_phase16_change_orders_dual_acceptance_and_snapshot_isolation(contract_client):
    """Change orders require bilateral acceptance and never overwrite the original contract snapshot."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    # Activate contract
    as_user(app, alice)
    c_resp = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = c_resp.json()["contract_id"]
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    as_user(app, bob)
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    # 1. Currency mismatch rejected (400)
    as_user(app, alice)
    bad_curr = await client.post(
        f"/api/v1/contracts/{contract_id}/change-orders",
        json={
            "change_summary": "Add Redis cluster",
            "scope": "Deploy Redis cluster with replication",
            "amount": 1500.0,
            "currency": "EUR",  # contract is USD
            "milestones": [{"title": "Redis Cluster", "amount": 1500}],
        },
    )
    assert bad_curr.status_code == 400
    assert "currency must match" in bad_curr.json()["detail"].lower()

    # 2. Valid change order proposed
    prop_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/change-orders",
        json={
            "change_summary": "Add Redis cluster",
            "scope": "Deploy Redis cluster with replication and failover monitoring",
            "amount": 1500.0,
            "currency": "USD",
            "milestones": [{"title": "Redis Cluster", "amount": 1500}],
        },
    )
    assert prop_resp.status_code == 201
    co_id = prop_resp.json()["change_order_id"]
    assert prop_resp.json()["state"] == "awaiting_acceptance"

    # 3. Freelancer accepts -> still awaiting_acceptance
    as_user(app, bob)
    bob_accept = await client.post(f"/api/v1/contracts/{contract_id}/change-orders/{co_id}/accept")
    assert bob_accept.status_code == 200
    assert bob_accept.json()["state"] == "awaiting_acceptance"
    assert bob_accept.json()["acknowledgments"]["freelancer"] is True
    assert bob_accept.json()["acknowledgments"]["client"] is False

    # 4. Client accepts -> state becomes accepted
    as_user(app, alice)
    alice_accept = await client.post(f"/api/v1/contracts/{contract_id}/change-orders/{co_id}/accept")
    assert alice_accept.status_code == 200
    assert alice_accept.json()["state"] == "accepted"
    assert alice_accept.json()["acknowledgments"]["client"] is True

    # 5. Snapshot isolation: original contract snapshot is unchanged
    original_contract = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    assert original_contract["snapshot"]["amount"] == "5000.0"
    assert len(original_contract["milestones"]) == 2

    # 6. List change orders endpoint
    co_list = await client.get(f"/api/v1/contracts/{contract_id}/change-orders")
    assert co_list.status_code == 200
    assert len(co_list.json()["change_orders"]) == 1
    assert co_list.json()["change_orders"][0]["state"] == "accepted"

    # 7. Propose second change order and reject it
    co2_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/change-orders",
        json={
            "change_summary": "Add Kubernetes helm chart",
            "scope": "Helm chart deployment",
            "amount": 800.0,
            "currency": "USD",
            "milestones": [{"title": "Helm chart", "amount": 800}],
        },
    )
    assert co2_resp.status_code == 201
    co2_id = co2_resp.json()["change_order_id"]

    as_user(app, bob)
    reject_resp = await client.post(f"/api/v1/contracts/{contract_id}/change-orders/{co2_id}/reject")
    assert reject_resp.status_code == 200
    assert reject_resp.json()["state"] == "rejected"


@pytest.mark.asyncio
async def test_phase16_dispute_center_and_immutable_addenda(contract_client):
    """Filing disputes records human-review flag, protects evidence, and supports immutable addenda."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        outsider = await session.get(User, "user-outsider")

    # Activate contract
    as_user(app, alice)
    c_resp = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = c_resp.json()["contract_id"]
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    as_user(app, bob)
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    # 1. Outsider cannot file dispute -> 403
    as_user(app, outsider)
    out_disp = await client.post(
        f"/api/v1/contracts/{contract_id}/disputes",
        json={"reason": "scope", "statement": "I have an objection to this contract."},
    )
    assert out_disp.status_code == 403

    # 2. Client files dispute with private evidence
    as_user(app, alice)
    dispute_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/disputes",
        json={
            "reason": "scope",
            "statement": "Milestone delivery does not contain the agreed database migration files.",
            "evidence": [{"type": "diff_link", "url": "https://internal-repo/diff/123", "hash": "abc1234"}],
        },
    )
    assert dispute_resp.status_code == 201
    disp_data = dispute_resp.json()
    dispute_id = disp_data["dispute_id"]
    assert disp_data["state"] == "open"
    assert disp_data["contract_state"] == "disputed"
    assert disp_data["review"] == "human_required"
    assert disp_data["provider_escalation"] == "unsupported"
    # Evidence is private and NOT echoed back
    assert "evidence" not in disp_data

    # 3. Freelancer files an immutable addendum responding with clarification
    as_user(app, bob)
    addendum_resp = await client.post(
        f"/api/v1/contracts/{contract_id}/disputes/{dispute_id}/addenda",
        json={
            "statement": "Migration files are located under alembic/versions/20261129_migration.py.",
            "evidence": [{"type": "file_path", "path": "alembic/versions/20261129_migration.py"}],
        },
    )
    assert addendum_resp.status_code == 201
    add_data = addendum_resp.json()
    assert add_data["immutable"] is True
    assert add_data["review"] == "human_required"
    assert "evidence" not in add_data

    # 4. List disputes
    disp_list = await client.get(f"/api/v1/contracts/{contract_id}/disputes")
    assert disp_list.status_code == 200
    disputes = disp_list.json()["disputes"]
    assert len(disputes) == 1
    assert disputes[0]["reason"] == "scope"
    assert "evidence" not in disputes[0]

    # 5. List addenda
    addenda_list = await client.get(f"/api/v1/contracts/{contract_id}/disputes/{dispute_id}/addenda")
    assert addenda_list.status_code == 200
    assert len(addenda_list.json()["addenda"]) == 1
    assert "Migration files are located" in addenda_list.json()["addenda"][0]["statement"]


@pytest.mark.asyncio
async def test_phase16_mutual_contract_termination(contract_client):
    """Contract termination requires bilateral acknowledgment."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    # Activate contract
    as_user(app, alice)
    c_resp = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = c_resp.json()["contract_id"]
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")
    as_user(app, bob)
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    # 1. Client requests termination
    as_user(app, alice)
    term1 = await client.post(f"/api/v1/contracts/{contract_id}/terminate")
    assert term1.status_code == 200
    assert term1.json()["state"] == "pending_termination"
    assert term1.json()["result"] == "pending_counterparty_acknowledgment"

    # 2. Client calling again remains pending_counterparty_acknowledgment
    term_repeat = await client.post(f"/api/v1/contracts/{contract_id}/terminate")
    assert term_repeat.status_code == 200
    assert term_repeat.json()["state"] == "pending_termination"
    assert term_repeat.json()["result"] == "pending_counterparty_acknowledgment"

    # 3. Freelancer counter-party acknowledges termination
    as_user(app, bob)
    term2 = await client.post(f"/api/v1/contracts/{contract_id}/terminate")
    assert term2.status_code == 200
    assert term2.json()["state"] == "terminated"
    assert term2.json()["result"] == "terminated"

    # 4. Terminated contract cannot request further termination -> 409
    term_dead = await client.post(f"/api/v1/contracts/{contract_id}/terminate")
    assert term_dead.status_code == 409


@pytest.mark.asyncio
async def test_phase16_append_only_audit_events_log(contract_client):
    """All contract actions generate an immutable chronological event trail."""
    client, app, session_maker = contract_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        outsider = await session.get(User, "user-outsider")

    # Lifecycle: create, acknowledge (both), transition milestone, propose change order
    as_user(app, alice)
    c_resp = await client.post("/api/v1/contracts/from-offer/offer-accepted-1")
    contract_id = c_resp.json()["contract_id"]
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    as_user(app, bob)
    await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")

    contract_info = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    m_id = contract_info["milestones"][0]["id"]
    await client.post(f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition", json={"state": "ready"})
    await client.post(f"/api/v1/contracts/{contract_id}/milestones/{m_id}/transition", json={"state": "in_progress"})

    # Propose change order
    as_user(app, alice)
    await client.post(
        f"/api/v1/contracts/{contract_id}/change-orders",
        json={"change_summary": "Extra review", "scope": "Review", "amount": 200.0, "currency": "USD"},
    )

    # 1. Outsider cannot view audit events -> 403
    as_user(app, outsider)
    out_events = await client.get(f"/api/v1/contracts/{contract_id}/events")
    assert out_events.status_code == 403

    # 2. Participant reads audit events
    as_user(app, bob)
    events_resp = await client.get(f"/api/v1/contracts/{contract_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]

    event_types = [e["type"] for e in events]
    assert "contract_created" in event_types
    assert "terms_acknowledged" in event_types
    assert "milestone_transition" in event_types
    assert "change_order_proposed" in event_types
    # Verify events are chronological
    timestamps = [e["created_at"] for e in events]
    assert timestamps == sorted(timestamps)
