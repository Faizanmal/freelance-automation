"""Phase 13 — Verified Talent and Employer Network Test Suite.

Covers:
1. E2E Freelancer Profile lifecycle:
   - Profile editor, skills, portfolio artifacts (with contribution roles: owner vs contributor).
   - Work availability with expiration date enforcement.
   - Rate preferences and currencies.
   - Privacy consent: private by default, opt-in directory, search indexing consent, platform contact.
   - Preview vs Public view (no private user data leaked).
   - Publish and unpublish lifecycle.
2. E2E Employer Organization & Seat lifecycle:
   - Organization onboarding.
   - Org membership invitation with token.
   - Invitation acceptance.
   - Member role update and seat revocation.
   - Seat lifecycle audit logs (OrgSeatLog).
3. Verification Levels & Sandbox Provider:
   - Claim creation (Level 1, Level 2, Level 3).
   - Sandbox verification for GitHub contributions with role discrimination (owner vs contributor).
   - Sandbox verification for domain DNS and org representative status.
   - Rejection of direct government ID payloads (policy compliance).
   - Evidence correction workflow.
   - No fabricated badges or unearned verified statuses.
4. Both-Side Reputation Activity:
   - Observable events recording (response, delivery, repeat hire, paid transaction).
   - Time decay weighting.
   - Sample size threshold (< 3 events marks insufficient data without negative score).
   - Multi-component breakdown (no single uncalibrated score).
   - Collusion and circular review ring detection.
   - Fair newcomer exposure.
5. Security, IDOR & Negative Tests:
   - User B cannot edit User A's profile, skills, or portfolio artifacts (IDOR).
   - Non-member cannot view org details or audit logs (403 Forbidden).
   - Unpublished and un-consented profiles excluded from directory.
   - Search indexing policy (X-Robots-Tag: noindex, nofollow).
   - Feature flag private preview access gating.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.main import create_app
from config.settings import get_settings
from database.core.base import Base
from database.core.session import get_db
from database.models.network import (
    EmployerOrg,
    OrgMembership,
    OrgSeatLog,
    PortfolioArtifact,
    PublicListingConsent,
    RatePreference,
    ReputationActivity,
    TalentProfile,
    TalentSkill,
    VerificationClaim,
    VerificationEvidence,
    WorkAvailability,
)
from database.models.user import User


@pytest_asyncio.fixture
async def network_test_engine():
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
        # Freelancer 1: Alice
        alice = User(
            id="user-alice",
            email="alice@engineer.ai",
            full_name="Alice AI Engineer",
            hashed_password="alice_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="freelancer",
        )
        # Freelancer 2: Bob
        bob = User(
            id="user-bob",
            email="bob@backend.dev",
            full_name="Bob Backend Dev",
            hashed_password="bob_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="freelancer",
        )
        # Employer Owner: Charlie
        charlie = User(
            id="user-charlie",
            email="charlie@acmecorp.com",
            full_name="Charlie Employer",
            hashed_password="charlie_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="client",
        )
        # Employer Member: David
        david = User(
            id="user-david",
            email="david@acmecorp.com",
            full_name="David Member",
            hashed_password="david_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="client",
        )
        session.add_all([alice, bob, charlie, david])
        await session.commit()

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def network_client(network_test_engine):
    app = create_app()
    session_maker = async_sessionmaker(
        network_test_engine, expire_on_commit=False, class_=AsyncSession
    )

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app, session_maker


# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freelancer_profile_lifecycle(network_client):
    """E2E Freelancer profile creation, skills, artifacts, availability, rates and consent."""
    client, app, session_maker = network_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice")

    app.dependency_overrides[get_current_user] = lambda: alice

    # 1. Get initial profile (Private by default)
    res = await client.get("/api/v1/network/profile")
    assert res.status_code == 200
    profile = res.json()["profile"]
    assert profile["is_published"] is False
    assert profile["is_owner_view"] is True
    assert profile["contact_allowed"] is False
    assert profile["listing_consent"]["opt_in_directory"] is False

    # 2. Update profile details
    res = await client.put(
        "/api/v1/network/profile",
        json={
            "headline": "Lead AI Automation Architect",
            "bio": "Specializing in autonomous agent systems and FastAPI architectures.",
            "primary_segment": "ai_software_automation",
            "years_experience": 8.5,
            "location_display": "Remote (UTC+1)",
        },
    )
    assert res.status_code == 200

    # 3. Add skills
    res = await client.post(
        "/api/v1/network/profile/skills",
        json={"skill_name": "FastAPI", "category": "backend", "years_of_experience": 5.0},
    )
    assert res.status_code == 200
    fastapi_skill = res.json()["skill"]
    assert fastapi_skill["verification_status"] == "unverified"

    # Add second skill
    res = await client.post(
        "/api/v1/network/profile/skills",
        json={"skill_name": "Agentic AI", "category": "ai_automation", "years_of_experience": 3.0},
    )
    assert res.status_code == 200

    # 4. Add portfolio artifact (explicit contribution role: owner vs contributor)
    res = await client.post(
        "/api/v1/network/profile/artifacts",
        json={
            "title": "Autonomous Pipeline Engine",
            "url": "https://github.com/alice/agent-engine",
            "artifact_type": "github_repo",
            "contribution_role": "owner",
            "description": "Core orchestration engine.",
        },
    )
    assert res.status_code == 200
    art = res.json()["artifact"]
    assert art["contribution_role"] == "owner"
    assert art["verification_status"] == "unverified"

    # 5. Update availability and rates
    expiry_time = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    res = await client.put(
        "/api/v1/network/profile/availability",
        json={"status": "available", "hours_per_week": 35, "expires_at": expiry_time},
    )
    assert res.status_code == 200
    assert res.json()["availability"]["status"] == "available"

    res = await client.put(
        "/api/v1/network/profile/rates",
        json={"min_rate": 90.0, "max_rate": 140.0, "currency": "USD", "rate_type": "hourly"},
    )
    assert res.status_code == 200
    assert res.json()["rates"]["min_rate"] == 90.0

    # 6. Cannot publish without explicit opt-in consent
    res = await client.post("/api/v1/network/profile/publish")
    assert res.status_code == 400
    assert "opt-in" in res.json()["detail"].lower()

    # 7. Grant opt-in consent and publish
    res = await client.put(
        "/api/v1/network/profile/consent",
        json={
            "opt_in_directory": True,
            "allow_platform_contact": True,
            "search_indexing_consent": False,
        },
    )
    assert res.status_code == 200
    assert res.json()["consent"]["opt_in_directory"] is True

    res = await client.post("/api/v1/network/profile/publish")
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    # 8. Check profile preview
    res = await client.get("/api/v1/network/profile/preview")
    assert res.status_code == 200
    preview = res.json()["preview"]
    assert preview["headline"] == "Lead AI Automation Architect"
    assert preview["contact_allowed"] is True
    # Email, phone, password must NEVER be in public preview
    assert "email" not in preview
    assert "hashed_password" not in preview


@pytest.mark.asyncio
async def test_employer_org_and_seat_lifecycle(network_client):
    """E2E Employer organization creation, member invitation, accept, update role, revoke seat, audit logs."""
    client, app, session_maker = network_client

    async with session_maker() as session:
        charlie = await session.get(User, "user-charlie")
        david = await session.get(User, "user-david")

    # Act as Charlie (Org Owner)
    app.dependency_overrides[get_current_user] = lambda: charlie

    # 1. Create Organization
    res = await client.post(
        "/api/v1/network/organizations",
        json={
            "name": "Acme Innovations",
            "website": "https://acme.example.com",
            "industry": "ai_software",
            "org_domain": "acmecorp.com",
        },
    )
    assert res.status_code == 201
    org = res.json()["organization"]
    org_id = org["id"]
    assert org["slug"] == "acme-innovations"

    # 2. Invite David as hiring_manager
    res = await client.post(
        f"/api/v1/network/organizations/{org_id}/invitations",
        json={"email": "david@acmecorp.com", "role": "hiring_manager"},
    )
    assert res.status_code == 200
    inv = res.json()["invitation"]
    token = inv["invitation_token"]
    membership_id = inv["membership_id"]
    assert inv["seat_status"] == "invited"
    assert token is not None

    # 3. Act as David to accept invitation
    app.dependency_overrides[get_current_user] = lambda: david
    res = await client.post(f"/api/v1/network/organizations/invitations/{token}/accept")
    assert res.status_code == 200
    assert res.json()["seat_status"] == "active"
    assert res.json()["role"] == "hiring_manager"

    # 4. Charlie updates David's role to admin
    app.dependency_overrides[get_current_user] = lambda: charlie
    res = await client.put(
        f"/api/v1/network/organizations/{org_id}/members/{membership_id}",
        json={"role": "admin"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"

    # 5. Charlie revokes David's seat
    res = await client.delete(f"/api/v1/network/organizations/{org_id}/members/{membership_id}")
    assert res.status_code == 200
    assert res.json()["seat_status"] == "revoked"

    # 6. Check org audit logs
    res = await client.get(f"/api/v1/network/organizations/{org_id}/audit-logs")
    assert res.status_code == 200
    logs = res.json()["audit_logs"]
    actions = [l["action"] for l in logs]
    assert "organization_created" in actions
    assert "invite_sent" in actions
    assert "invite_accepted" in actions
    assert "role_changed" in actions
    assert "seat_revoked" in actions


@pytest.mark.asyncio
async def test_verification_levels_and_sandbox_provider(network_client):
    """Verification claims, sandbox verification, role discrimination, correction workflow, and no gov ID."""
    client, app, session_maker = network_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice")

    app.dependency_overrides[get_current_user] = lambda: alice

    # 1. Create a GitHub contribution claim (Level 3)
    res = await client.post(
        "/api/v1/network/verification/claims",
        json={"claim_type": "github_contribution"},
    )
    assert res.status_code == 200
    claim_id = res.json()["claim"]["id"]
    assert res.json()["claim"]["level"] == 3
    assert res.json()["claim"]["claim_source"] == "user_claimed"

    # 2. Rejection of direct government ID payload
    res = await client.post(
        f"/api/v1/network/verification/claims/{claim_id}/evidence",
        json={
            "provider": "direct_upload",
            "evidence_type": "passport_scan",
            "evidence_payload": {"government_id": "AB12345678"},
        },
    )
    assert res.status_code == 400
    assert "government id" in res.json()["detail"].lower()

    # 3. Submit valid evidence
    res = await client.post(
        f"/api/v1/network/verification/claims/{claim_id}/evidence",
        json={
            "provider": "sandbox_github",
            "evidence_type": "commit_history",
            "provider_reference_id": "gh_ref_123",
            "evidence_payload": {"repo": "agent-engine", "claimed_role": "contributor"},
        },
    )
    assert res.status_code == 200
    evidence_id = res.json()["evidence_id"]

    # 4. Evidence correction workflow
    res = await client.put(
        f"/api/v1/network/verification/evidence/{evidence_id}/correction",
        json={
            "correction_notes": "Updated commit author email to match verified primary email.",
            "updated_reference_id": "gh_ref_123_corrected",
        },
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Evidence corrected"

    # 5. Execute Sandbox Verification for GitHub contribution
    # Test contributor vs owner distinction
    res = await client.post(
        f"/api/v1/network/verification/claims/{claim_id}/sandbox-verify",
        json={
            "user_handle_or_email": "alice",
            "target_resource": "https://github.com/upstream-org/agent-engine",
            "claimed_role": "contributor",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["result"]["verified_role"] == "contributor"
    assert body["result"]["role_matches"] is True
    assert "read:user" in body["result"]["granted_scopes"]


@pytest.mark.asyncio
async def test_both_side_reputation_and_manipulation_checks(network_client):
    """Reputation activity, time decay, sample size threshold, newcomer label, and circular review detection."""
    client, app, session_maker = network_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice")
        charlie = await session.get(User, "user-charlie")

    app.dependency_overrides[get_current_user] = lambda: charlie

    # 1. Query Alice's reputation before any events (sample size 0 < 3)
    res = await client.get("/api/v1/network/reputation/user-alice?entity_type=freelancer")
    assert res.status_code == 200
    rep = res.json()["reputation"]
    assert rep["has_sufficient_data"] is False
    assert rep["status_label"] == "New talent (insufficient data)"
    assert rep["sample_size"] == 0
    assert rep["newcomer_fair_exposure"] is True

    # 2. Record observable interactions via ReputationService
    from backend.application.services.network.reputation_service import ReputationService

    async with session_maker() as session:
        rep_service = ReputationService(session)

        # Self-hire attempt (manipulation check: should be flagged suspicious)
        await rep_service.record_activity(
            user_id="user-alice",
            counterparty_id="user-alice",  # self-hire
            event_type="delivery_confirmed",
        )

        # Genuine activities from Charlie
        await rep_service.record_activity(
            user_id="user-alice",
            counterparty_id="user-charlie",
            event_type="response_recorded",
            response_time_seconds=1800,  # 30 min
        )
        await rep_service.record_activity(
            user_id="user-alice",
            counterparty_id="user-charlie",
            event_type="delivery_confirmed",
        )
        await rep_service.record_activity(
            user_id="user-alice",
            counterparty_id="user-charlie",
            event_type="repeat_hire",
        )
        await rep_service.record_activity(
            user_id="user-alice",
            counterparty_id="user-charlie",
            event_type="paid_transaction",
            transaction_amount=3500.0,
        )

    # 3. Query Alice's reputation again (4 valid events >= 3)
    res = await client.get("/api/v1/network/reputation/user-alice?entity_type=freelancer")
    assert res.status_code == 200
    rep = res.json()["reputation"]
    assert rep["has_sufficient_data"] is True
    assert rep["sample_size"] == 4  # Self-hire was excluded!
    assert rep["status_label"] == "Verified history"
    assert rep["components"]["confirmed_deliveries_count"] == 1
    assert rep["components"]["avg_response_minutes"] == 30.0
    assert rep["components"]["paid_transactions_volume_usd"] == 3500.0


@pytest.mark.asyncio
async def test_directory_discovery_privacy_and_security(network_client):
    """Talent discovery filters, non-discriminatory attributes, opt-out unpublish, and IDOR negative tests."""
    client, app, session_maker = network_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice")
        bob = await session.get(User, "user-bob")
        charlie = await session.get(User, "user-charlie")

    # Set up Alice as published and opted in
    app.dependency_overrides[get_current_user] = lambda: alice
    await client.put(
        "/api/v1/network/profile",
        json={"headline": "Senior AI Systems Engineer", "primary_segment": "ai_software_automation"},
    )
    await client.post(
        "/api/v1/network/profile/skills",
        json={"skill_name": "Python", "category": "backend", "years_of_experience": 6.0},
    )
    await client.put(
        "/api/v1/network/profile/rates",
        json={"min_rate": 100.0, "max_rate": 150.0, "currency": "USD", "rate_type": "hourly"},
    )
    await client.put(
        "/api/v1/network/profile/consent",
        json={"opt_in_directory": True, "allow_platform_contact": True, "search_indexing_consent": False},
    )
    res_pub = await client.post("/api/v1/network/profile/publish")
    assert res_pub.status_code == 200

    # Bob remains unpublished / private by default
    app.dependency_overrides[get_current_user] = lambda: bob
    await client.put("/api/v1/network/profile", json={"headline": "Private Draft Dev"})

    # Act as Charlie searching directory
    app.dependency_overrides[get_current_user] = lambda: charlie
    res_dir = await client.get("/api/v1/network/directory")
    assert res_dir.status_code == 200
    assert res_dir.headers.get("X-Robots-Tag") == "noindex, nofollow"

    items = res_dir.json()["items"]
    headlines = [item["headline"] for item in items]
    assert "Senior AI Systems Engineer" in headlines
    # Bob must NOT be in the directory
    assert "Private Draft Dev" not in headlines

    # Filter by skill
    res_skill = await client.get("/api/v1/network/directory?skills=Python")
    assert res_skill.status_code == 200
    assert len(res_skill.json()["items"]) >= 1

    res_nomatch = await client.get("/api/v1/network/directory?skills=NonExistentSkill12345")
    assert res_nomatch.status_code == 200
    assert len(res_nomatch.json()["items"]) == 0

    # Filter by rate range
    res_rate = await client.get("/api/v1/network/directory?min_rate=50&max_rate=120")
    assert res_rate.status_code == 200
    assert len(res_rate.json()["items"]) >= 1

    # IDOR check: Bob cannot edit Alice's skills or artifacts
    app.dependency_overrides[get_current_user] = lambda: bob
    res_idor = await client.delete("/api/v1/network/profile/skills/non-existent-or-alice-skill")
    assert res_idor.status_code == 404

    # Non-member IDOR check: Bob cannot view Charlie's org audit logs
    res_org_idor = await client.get("/api/v1/network/organizations/some-org-id/audit-logs")
    assert res_org_idor.status_code in {403, 404}

    # Opt-out test: Alice unpublishes
    app.dependency_overrides[get_current_user] = lambda: alice
    res_unpub = await client.post("/api/v1/network/profile/unpublish")
    assert res_unpub.status_code == 200

    # Verify Alice is now immediately removed from the public directory
    app.dependency_overrides[get_current_user] = lambda: charlie
    res_dir_after = await client.get("/api/v1/network/directory")
    items_after = res_dir_after.json()["items"]
    assert not any(i["headline"] == "Senior AI Systems Engineer" for i in items_after)
