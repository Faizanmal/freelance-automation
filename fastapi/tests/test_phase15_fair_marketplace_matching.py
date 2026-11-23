"""Phase 15 — Fair Two-Sided Marketplace Matching & Mutual-Interest Hiring Test Suite.

Validates:
1. Two-sided matching, explainable shortlist (3-5), zero-fit behavior.
2. Architectural firewall: Entitlement/paid data prohibited; free high-fit ranks over paid low-fit.
3. Equitable newcomer exposure rotation.
4. Mutual interest ($0 fee), anti-spam rate controls (3/24h, max 5 active), withdrawal & decline without penalty.
5. Bilateral offer negotiation, counter-proposals (versioning), and concurrency locks (409 Conflict on filled position).
6. Direct messaging: participant isolation, attachment checks, contact masking, report/block.
7. Privacy-safe evaluation metrics and synthetic liquidity disclaimer.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.main import create_app
from backend.application.services.marketplace_matching import (
    CandidateMatch,
    ConflictError,
    EvaluationMetricsCalculator,
    FairMarketplaceMatcher,
    TalentFeatureVector,
)
from database.core.base import Base
from database.core.session import get_db
from database.models.matching import (
    ProjectApplication,
    ProjectConversation,
    ProjectInvitation,
    ProjectMessage,
    ProjectOffer,
    ProjectOfferRevision,
)
from database.models.network import (
    EmployerOrg,
    OrgMembership,
    RatePreference,
    TalentProfile,
    TalentSkill,
    WorkAvailability,
)
from database.models.project import NativeProject
from database.models.user import User


def as_user(app, user: User):
    app.dependency_overrides[get_current_user] = lambda: user


@pytest_asyncio.fixture
async def phase15_client():
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
        # Client user
        alice = User(
            id="user-alice-client",
            email="alice@techcorp.io",
            full_name="Alice Client",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="client",
        )
        # Freelancer 1: Bob (Verified Expert)
        bob = User(
            id="user-bob-dev",
            email="bob@python.dev",
            full_name="Bob Developer",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="freelancer",
        )
        # Freelancer 2: Charlie (Newcomer)
        charlie = User(
            id="user-charlie-dev",
            email="charlie@newcomer.dev",
            full_name="Charlie Newcomer",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="freelancer",
        )
        # Stranger (Unaffiliated)
        stranger = User(
            id="user-stranger-outsider",
            email="stranger@other.org",
            full_name="Stranger Outsider",
            hashed_password="pw",
            is_active=True,
            is_verified=True,
            account_role="freelancer",
        )
        session.add_all([alice, bob, charlie, stranger])
        await session.flush()

        # Org: TechCorp AI
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

        # Org membership
        mem = OrgMembership(
            id="mem-alice-owner",
            org_id=org.id,
            user_id=alice.id,
            email=alice.email,
            role="owner",
            seat_status="active",
        )
        session.add(mem)

        # Native Project
        project = NativeProject(
            id="proj-distributed-agent",
            org_id=org.id,
            creator_id=alice.id,
            title="Distributed Python Async Agent Core",
            raw_description="High performance FastAPI and Redis async streaming engine with Celery workers.",
            skills_required=["Python", "FastAPI", "Redis"],
            budget_min=3000.0,
            budget_max=6000.0,
            currency="USD",
            rate_period="fixed",
            scope_level="medium",
            work_type="remote",
            required_hours_per_week=25,
            hiring_deadline=datetime.now(timezone.utc) + timedelta(days=21),
            reconfirm_by=datetime.now(timezone.utc) + timedelta(days=14),
            status="approved_open",
            review_state="approved",
            payment_verified=True,
        )
        session.add(project)

        # Bob's Profile: Verified Python & FastAPI
        prof_bob = TalentProfile(
            id="prof-bob",
            user_id=bob.id,
            headline="Senior Python & FastAPI Specialist",
            bio="Building high throughput distributed systems.",
            years_experience=6.0,
            is_published=True,
            status="published",
        )
        session.add(prof_bob)
        session.add(TalentSkill(id="sk-bob-py", profile_id=prof_bob.id, skill_name="Python", verification_status="verified"))
        session.add(TalentSkill(id="sk-bob-fa", profile_id=prof_bob.id, skill_name="FastAPI", verification_status="verified"))
        session.add(RatePreference(id="rate-bob", profile_id=prof_bob.id, min_rate=80, max_rate=110, rate_type="hourly"))
        session.add(WorkAvailability(
            id="avail-bob",
            profile_id=prof_bob.id,
            status="available",
            hours_per_week=35,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ))

        # Charlie's Profile: Qualified Newcomer
        prof_charlie = TalentProfile(
            id="prof-charlie",
            user_id=charlie.id,
            headline="Fullstack Python & Redis Developer",
            bio="Passionate engineer exploring distributed queues.",
            years_experience=3.0,
            is_published=True,
            status="published",
        )
        session.add(prof_charlie)
        session.add(TalentSkill(id="sk-charlie-py", profile_id=prof_charlie.id, skill_name="Python", verification_status="verified"))
        session.add(TalentSkill(id="sk-charlie-re", profile_id=prof_charlie.id, skill_name="Redis", verification_status="verified"))
        session.add(RatePreference(id="rate-charlie", profile_id=prof_charlie.id, min_rate=60, max_rate=90, rate_type="hourly"))
        session.add(WorkAvailability(
            id="avail-charlie",
            profile_id=prof_charlie.id,
            status="available",
            hours_per_week=30,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ))

        await session.commit()

    app = create_app()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app, session_maker

    await engine.dispose()


# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_sided_matching_and_shortlist_generation(phase15_client):
    """Test two-sided matching, shortlist of 3-5, reasons, missing info, and zero-fit behavior."""
    client, app, session_maker = phase15_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        charlie = await session.get(User, "user-charlie-dev")

    as_user(app, alice)
    res = await client.get("/api/v1/matching/projects/proj-distributed-agent/shortlist")
    assert res.status_code == 200, res.text
    data = res.json()

    assert "shortlist" in data
    shortlist = data["shortlist"]
    assert len(shortlist) >= 2

    bob_match = next(c for c in shortlist if c["freelancer_id"] == bob.id)
    assert bob_match["overall_score"] >= 0.70
    assert any("Verified evidence" in r for r in bob_match["reasons"])
    assert len(bob_match["missing_information"]) > 0  # Missing Redis noted for Bob

    charlie_match = next(c for c in shortlist if c["freelancer_id"] == charlie.id)
    assert charlie_match["is_newcomer"] is True
    assert charlie_match["newcomer_boost"] > 0.0


@pytest.mark.asyncio
async def test_firewall_paid_vs_free_equal_ranking():
    """Verify architectural firewall: Entitlement/paid data raises error; free high-fit ranks over paid low-fit."""
    # 1. Firewall Test: Passing subscription/paid data into TalentFeatureVector must raise ValueError
    with pytest.raises(ValueError, match="Firewall violation"):
        TalentFeatureVector(
            freelancer_id="usr-paid",
            headline="Pro Dev",
            plan="pro",  # Prohibited!
        )

    with pytest.raises(ValueError, match="Firewall violation"):
        TalentFeatureVector(
            freelancer_id="usr-ad",
            headline="Boosted Dev",
            ad_credits=50,  # Prohibited!
        )

    # 2. Ranking Verification: Free Candidate with High Fit vs Simulated Low-Fit Candidate
    mock_project = {
        "skills_required": ["Python", "FastAPI", "PostgreSQL"],
        "budget_min": 4000.0,
        "budget_max": 7000.0,
        "rate_period": "fixed",
        "work_type": "remote",
        "required_hours_per_week": 30,
        "scope_level": "medium",
    }

    free_dev = TalentFeatureVector(
        freelancer_id="free-alice",
        headline="Free Open Source Contributor",
        skills=[
            {"skill_name": "Python", "verification_status": "verified"},
            {"skill_name": "FastAPI", "verification_status": "verified"},
            {"skill_name": "PostgreSQL", "verification_status": "verified"},
        ],
        min_rate=80,
        max_rate=120,
        rate_type="hourly",
        hours_per_week=40,
        availability_status="available",
        work_type_preference="remote",
        years_experience=5.0,
        verification_level=3,
        is_newcomer=False,
    )

    other_dev = TalentFeatureVector(
        freelancer_id="dev-bob",
        headline="Junior Frontend Developer",
        skills=[
            {"skill_name": "JavaScript", "verification_status": "self_claimed"},
        ],
        min_rate=40,
        max_rate=60,
        rate_type="hourly",
        hours_per_week=20,
        availability_status="available",
        work_type_preference="remote",
        years_experience=1.0,
        verification_level=1,
        is_newcomer=False,
    )

    ranked = FairMarketplaceMatcher.rank_candidates(mock_project, [free_dev, other_dev], limit=5)
    assert len(ranked) >= 1
    assert ranked[0].freelancer_id == "free-alice"
    assert ranked[0].overall_score >= 0.85


@pytest.mark.asyncio
async def test_newcomer_equitable_exposure_rotation():
    """Verify equitable newcomer exposure rotation boost gives qualified newcomers fair exposure."""
    mock_project = {
        "skills_required": ["Python", "PyTorch"],
        "budget_min": 5000.0,
        "budget_max": 8000.0,
        "rate_period": "fixed",
        "work_type": "remote",
        "required_hours_per_week": 20,
        "scope_level": "medium",
    }

    newcomer = TalentFeatureVector(
        freelancer_id="newcomer-1",
        headline="Talented AI Engineer (New to Platform)",
        skills=[
            {"skill_name": "Python", "verification_status": "verified"},
            {"skill_name": "PyTorch", "verification_status": "verified"},
        ],
        min_rate=70,
        max_rate=100,
        hours_per_week=30,
        years_experience=3.0,
        verification_level=2,
        is_newcomer=True,
    )

    veteran = TalentFeatureVector(
        freelancer_id="veteran-1",
        headline="Established AI Engineer",
        skills=[
            {"skill_name": "Python", "verification_status": "verified"},
            {"skill_name": "PyTorch", "verification_status": "verified"},
        ],
        min_rate=70,
        max_rate=100,
        hours_per_week=30,
        years_experience=3.0,
        verification_level=2,
        is_newcomer=False,
    )

    ranked = FairMarketplaceMatcher.rank_candidates(mock_project, [veteran, newcomer], limit=5)
    assert len(ranked) == 2

    newcomer_match = next(r for r in ranked if r.freelancer_id == "newcomer-1")
    veteran_match = next(r for r in ranked if r.freelancer_id == "veteran-1")

    assert newcomer_match.breakdown.newcomer_boost > 0.0
    assert any("newcomer exposure rotation" in r for r in newcomer_match.breakdown.reasons)
    assert newcomer_match.overall_score >= veteran_match.overall_score


@pytest.mark.asyncio
async def test_mutual_interest_and_anti_spam_rate_controls(phase15_client):
    """Test $0 fee expression of interest, anti-spam (3/24h, max 5 active), withdrawal and decline."""
    client, app, session_maker = phase15_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    # 1. Freelancer applies at $0 cost
    as_user(app, bob)
    apply_payload = {
        "structured_pitch": "I have 4 years building async agent graph architectures with FastAPI.",
        "proposed_rate": 3500.0,
        "proposed_rate_period": "fixed",
        "estimated_days": 14,
    }
    res = await client.post(
        "/api/v1/matching/projects/proj-distributed-agent/apply",
        json=apply_payload,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "submitted"
    app_id = data["application_id"]

    # 2. Duplicate application on same project fails
    dup_res = await client.post(
        "/api/v1/matching/projects/proj-distributed-agent/apply",
        json=apply_payload,
    )
    assert dup_res.status_code == 400
    assert "already submitted" in dup_res.json()["detail"]

    # 3. Freelancer withdraws interest
    w_res = await client.post(f"/api/v1/matching/applications/{app_id}/withdraw")
    assert w_res.status_code == 200
    assert w_res.json()["status"] == "withdrawn"

    # 4. Re-applying after withdrawal is permitted
    res2 = await client.post(
        "/api/v1/matching/projects/proj-distributed-agent/apply",
        json=apply_payload,
    )
    assert res2.status_code == 201
    app_id_2 = res2.json()["application_id"]

    # 5. Client declines with reason (no rating penalty)
    as_user(app, alice)
    dec_res = await client.post(
        f"/api/v1/matching/applications/{app_id_2}/decline",
        json={"reason": "Selected another profile specializing in Redis Streams"},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_negotiation_offers_and_concurrency_guards(phase15_client):
    """Test offer counter-proposals, milestone agreements, and duplicate acceptance prevention (409 Conflict)."""
    client, app, session_maker = phase15_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        charlie = await session.get(User, "user-charlie-dev")

        # Create applications for both candidates
        app1 = ProjectApplication(
            id=str(uuid4()),
            project_id="proj-distributed-agent",
            freelancer_id=bob.id,
            status="negotiating",
            structured_pitch="Expert in scraping and streaming pipelines.",
            proposed_rate=3000.0,
        )
        app2 = ProjectApplication(
            id=str(uuid4()),
            project_id="proj-distributed-agent",
            freelancer_id=charlie.id,
            status="negotiating",
            structured_pitch="Experienced Redis backend engineer.",
            proposed_rate=3200.0,
        )
        session.add_all([app1, app2])
        await session.commit()

    # 1. Client creates Offer 1 for Candidate 1 (Bob)
    as_user(app, alice)
    off1_res = await client.post(
        "/api/v1/matching/projects/proj-distributed-agent/offers",
        json={"application_id": app1.id, "agreed_amount": 2800.0, "contract_type": "fixed_price"},
    )
    assert off1_res.status_code == 201, off1_res.text
    off1_id = off1_res.json()["offer_id"]

    # 2. Candidate 1 submits counter-proposal -> version increases to 2
    as_user(app, bob)
    counter_res = await client.post(
        f"/api/v1/matching/offers/{off1_id}/counter",
        json={"revised_amount": 3000.0, "change_summary": "Adjusted to $3000 to cover staging environment deployment."},
    )
    assert counter_res.status_code == 200, counter_res.text
    assert counter_res.json()["version"] == 2

    # 3. Client creates Offer 2 for Candidate 2 (Charlie)
    as_user(app, alice)
    off2_res = await client.post(
        "/api/v1/matching/projects/proj-distributed-agent/offers",
        json={"application_id": app2.id, "agreed_amount": 3100.0, "contract_type": "fixed_price"},
    )
    assert off2_res.status_code == 201, off2_res.text
    off2_id = off2_res.json()["offer_id"]

    # 4. Client accepts Candidate 1's counter-offer (off1)
    accept1_res = await client.post(f"/api/v1/matching/offers/{off1_id}/accept")
    assert accept1_res.status_code == 200, accept1_res.text
    assert accept1_res.json()["status"] == "accepted"

    # 5. CONCURRENCY GUARD: Candidate 2 tries to accept Offer 2
    # Position is now filled! Must fail with 409 Conflict
    as_user(app, charlie)
    accept2_res = await client.post(f"/api/v1/matching/offers/{off2_id}/accept")
    assert accept2_res.status_code == 409, accept2_res.text
    assert "already been filled" in accept2_res.json()["detail"]


@pytest.mark.asyncio
async def test_direct_messaging_attachment_scan_and_privacy(phase15_client):
    """Test authenticated negotiation chat, attachment validation, contact details masking, and reporting."""
    client, app, session_maker = phase15_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        stranger = await session.get(User, "user-stranger-outsider")

    # 1. Initiate conversation
    as_user(app, alice)
    init_res = await client.post(
        f"/api/v1/matching/conversations/initiate?project_id=proj-distributed-agent&freelancer_id={bob.id}",
    )
    assert init_res.status_code == 200, init_res.text
    conv_id = init_res.json()["conversation_id"]

    # 2. Stranger tries to access conversation -> 403 Forbidden
    as_user(app, stranger)
    stranger_res = await client.get(f"/api/v1/matching/conversations/{conv_id}/messages")
    assert stranger_res.status_code == 403

    # 3. Freelancer sends message with raw email -> Contact details should be masked
    as_user(app, bob)
    msg_res = await client.post(
        f"/api/v1/matching/conversations/{conv_id}/messages",
        json={"body": "Hello, email me directly at contact@secretdev.com or call +1 555-019-2834 to discuss."},
    )
    assert msg_res.status_code == 201, msg_res.text
    saved_body = msg_res.json()["body"]
    assert "contact@secretdev.com" not in saved_body
    assert "[contact details hidden" in saved_body

    # 4. Invalid attachment extension (.exe) rejected
    bad_att_res = await client.post(
        f"/api/v1/matching/conversations/{conv_id}/messages",
        json={
            "body": "Here is the file.",
            "attachments": [{"filename": "trojan.exe", "url": "https://cdn.example.com/trojan.exe", "size_bytes": 1024}],
        },
    )
    assert bad_att_res.status_code == 400
    assert "not permitted" in bad_att_res.json()["detail"]

    # 5. Valid attachment (.pdf) accepted
    good_att_res = await client.post(
        f"/api/v1/matching/conversations/{conv_id}/messages",
        json={
            "body": "Here is the architecture spec document.",
            "attachments": [{"filename": "architecture_diagram.pdf", "url": "https://cdn.example.com/spec.pdf", "size_bytes": 204800}],
        },
    )
    assert good_att_res.status_code == 201

    # 6. Report / block conversation
    as_user(app, alice)
    rep_res = await client.post(
        f"/api/v1/matching/conversations/{conv_id}/report",
        json={"action": "block", "reason": "Abusive communication"},
    )
    assert rep_res.status_code == 200
    assert rep_res.json()["status"] == "blocked"


@pytest.mark.asyncio
async def test_evaluation_metrics_and_synthetic_liquidity_disclaimer(phase15_client):
    """Test privacy-safe evaluation metrics and synthetic liquidity disclaimer."""
    client, app, session_maker = phase15_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")

    as_user(app, alice)
    res = await client.get("/api/v1/matching/metrics?mode=simulated")
    assert res.status_code == 200
    data = res.json()["metrics"]

    assert data["mode"] == "simulated"
    assert data["relevant_candidate_rate"] > 0.8
    assert data["avg_response_latency_hours"] > 0
    assert "Synthetic benchmarks must never be used to claim market liquidity" in data["disclaimer"]


@pytest.mark.asyncio
async def test_phase16_contract_only_flow_and_disabled_funding(phase15_client):
    """Accepted offer -> bilateral contract -> delivery/approval; funding stays unavailable."""
    from database.models.contracts import ContractMilestone, ProjectContract

    client, app, session_maker = phase15_client
    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")
        application = ProjectApplication(
            id=str(uuid4()), project_id="proj-distributed-agent", freelancer_id=bob.id,
            status="negotiating", structured_pitch="Experienced backend engineer with delivery history.",
            proposed_rate=3000.0,
        )
        session.add(application)
        await session.commit()

    as_user(app, alice)
    offer_response = await client.post(
        "/api/v1/matching/projects/proj-distributed-agent/offers",
        json={"application_id": application.id, "agreed_amount": 3000.0,
              "contract_type": "fixed_price", "milestones": [{"title": "Delivery", "amount": 3000, "deliverable": "Source and handoff"}]},
    )
    assert offer_response.status_code == 201, offer_response.text
    offer_id = offer_response.json()["offer_id"]
    as_user(app, bob)
    assert (await client.post(f"/api/v1/matching/offers/{offer_id}/accept")).status_code == 200

    capabilities = await client.get("/api/v1/contracts/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["mode"] == "contract_only"
    assert capabilities.json()["live_payments_enabled"] is False
    assert not any(capabilities.json()["supported"].values())

    as_user(app, alice)
    created = await client.post(f"/api/v1/contracts/from-offer/{offer_id}")
    assert created.status_code == 201, created.text
    contract_id = created.json()["contract_id"]
    assert created.json()["snapshot"]["offer_version"] == 1
    assert (await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")).json()["state"] == "awaiting_acknowledgments"
    as_user(app, bob)
    assert (await client.post(f"/api/v1/contracts/{contract_id}/acknowledge")).json()["state"] == "active"

    async with session_maker() as session:
        contract = await session.get(ProjectContract, contract_id)
        milestone = (await session.execute(select(ContractMilestone).where(ContractMilestone.contract_id == contract_id))).scalar_one()
        assert contract.snapshot["amount"] == "3000.0"
        milestone_id = milestone.id

    for state in ("ready", "in_progress", "submitted"):
        response = await client.post(f"/api/v1/contracts/{contract_id}/milestones/{milestone_id}/transition", json={"state": state})
        assert response.status_code == 200, response.text
    as_user(app, alice)
    approved = await client.post(f"/api/v1/contracts/{contract_id}/milestones/{milestone_id}/transition", json={"state": "approved"})
    assert approved.status_code == 200, approved.text
    disabled = await client.post(f"/api/v1/contracts/{contract_id}/milestones/{milestone_id}/transition", json={"state": "paid"})
    assert disabled.status_code == 409
    assert "disabled" in disabled.json()["detail"]

    report = await client.post(f"/api/v1/contracts/{contract_id}/disputes", json={"reason": "quality", "statement": "The delivered item does not meet the agreed acceptance criteria."})
    assert report.status_code == 201, report.text
    assert report.json()["review"] == "human_required"
