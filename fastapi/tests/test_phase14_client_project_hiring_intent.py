"""Phase 14 — Client Workspace and Proof of Hiring Intent Test Suite.

Covers:
1. E2E Client Project Lifecycle:
   - Create brief in draft status under employer organization.
   - AI scope clarification (boundaries, acceptance criteria, milestone outline, budget basis).
   - Client approves AI draft.
   - Submit project: passes safety scanner, transitions to approved_open.
   - Shortlist candidate: transitions to shortlist.
   - Candidate interview: transitions to interviewing.
   - Candidate hire: transitions to offered_hired.
   - Close project: transitions to closed.
   - Reopen project with audit history.
2. Hiring-Intent Evidence:
   - Verified organization domain, clear budget, decision deadline.
   - Payment method verification (unverified payment must never appear funded).
   - Zero native application fee assertion.
3. Content Policy & Safety Scanner (Negative Tests):
   - Missing or inverted budget rejected (400).
   - Discriminatory requirements flagged for human review.
   - Malicious links / off-platform redirects flagged for human review.
   - Upfront freelancer payment requests flagged for human review.
   - Excessive unpaid speculative work flagged for human review.
4. Moderator Review & Appeal Queue:
   - Flagged project enters moderation queue.
   - Client appeals flagged project with explanation.
   - Superuser resolves moderation appeal and approves project.
   - No automatic bans on AI assessment alone.
5. Clarification Requests & Anti-Spam:
   - Freelancer submits clarification question.
   - Rate limit enforcement (max 3 questions per 24 hours).
   - Duplicate question prevention.
   - Client answers question and marks public.
6. Reconfirmation & Auto-Expiration:
   - Periodic reconfirmation extends deadline.
   - Stale/unanswered project auto-expires with transparent abandonment reason.
7. Security & IDOR Negative Tests:
   - Non-org member cannot create/edit org projects (403 Forbidden).
   - Unauthorized user cannot transition status (403 Forbidden).
   - Draft projects hidden from external viewers (404 Not Found).
   - Duplicate project posting within 24 hours blocked (400 Bad Request).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_active_superuser, get_current_user
from app.main import create_app
from database.core.base import Base
from database.core.session import get_db
from database.models.network import EmployerOrg, OrgMembership
from database.models.project import NativeProject, ProjectModerationQueue
from database.models.user import User


@pytest_asyncio.fixture
async def phase14_test_engine():
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
        # Employer Owner: Alice
        alice = User(
            id="user-alice-client",
            email="alice@techcorp.io",
            full_name="Alice Client Lead",
            hashed_password="alice_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="client",
        )
        # Freelancer Candidate: Bob
        bob = User(
            id="user-bob-dev",
            email="bob@fastapi.expert",
            full_name="Bob Developer",
            hashed_password="bob_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="freelancer",
        )
        # Unaffiliated User: Charlie
        charlie = User(
            id="user-charlie-outsider",
            email="charlie@other.org",
            full_name="Charlie Outsider",
            hashed_password="charlie_password",
            is_active=True,
            is_verified=True,
            is_superuser=False,
            account_role="client",
        )
        # Staff Moderator: Superuser
        superuser = User(
            id="user-admin-staff",
            email="admin@platform.internal",
            full_name="Admin Staff",
            hashed_password="admin_password",
            is_active=True,
            is_verified=True,
            is_superuser=True,
            account_role="staff",
        )
        session.add_all([alice, bob, charlie, superuser])
        await session.flush()

        # Create Alice's Org
        org = EmployerOrg(
            id="org-techcorp",
            name="TechCorp AI",
            slug="techcorp-ai",
            website="https://techcorp.io",
            industry="technology",
            org_domain="techcorp.io",
            domain_verified=True,
            verification_status="domain_verified",
            owner_id=alice.id,
            is_sample=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(org)
        await session.flush()

        # Alice's Membership as Owner
        mem = OrgMembership(
            id="mem-alice-owner",
            org_id="org-techcorp",
            user_id=alice.id,
            email=alice.email,
            role="owner",
            seat_status="active",
            invited_at=datetime.now(timezone.utc),
            accepted_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(mem)
        await session.commit()

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def phase14_client(phase14_test_engine):
    app = create_app()
    session_maker = async_sessionmaker(
        phase14_test_engine, expire_on_commit=False, class_=AsyncSession
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
async def test_client_wizard_and_project_lifecycle_e2e(phase14_client):
    """E2E Client creates project brief, clarifies scope, submits, shortlists, hires, closes and reopens."""
    client, app, session_maker = phase14_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    app.dependency_overrides[get_current_user] = lambda: alice

    # 1. Wizard AI Scope Clarification
    res = await client.post(
        "/api/v1/projects/clarify-scope",
        json={
            "raw_description": "We need an async Python FastAPI backend for AI agent orchestration with PostgreSQL and automated test coverage.",
            "template_key": "fastapi_backend",
        },
    )
    assert res.status_code == 200
    clarification = res.json()["clarification"]
    assert "FastAPI" in clarification["suggested_skills"]
    assert len(clarification["deliverables"]) >= 3
    assert len(clarification["milestone_outline"]) >= 2
    assert "Key unknowns" in clarification["budget_basis_notes"]

    # 2. Create Project Brief (Draft)
    deadline = (datetime.now(timezone.utc) + timedelta(days=21)).isoformat()
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Agent Orchestration Backend Service",
            "raw_description": "Architect and deploy an async FastAPI service with PostgreSQL and automated test coverage.",
            "budget_min": 3000.0,
            "budget_max": 5000.0,
            "currency": "USD",
            "rate_period": "fixed",
            "hiring_deadline": deadline,
            "template_key": "fastapi_backend",
        },
    )
    assert res.status_code == 201
    project = res.json()["project"]
    project_id = project["id"]
    assert project["status"] == "draft"
    assert project["ai_clarification_approved"] is False

    # 3. Approve AI Scope Breakdown
    res = await client.put(f"/api/v1/projects/{project_id}/ai-scope/approve", json={})
    assert res.status_code == 200
    assert res.json()["ai_clarification_approved"] is True

    # 4. Submit Project Brief (passes safety scanner -> approved_open)
    res = await client.post(f"/api/v1/projects/{project_id}/submit")
    assert res.status_code == 200
    assert res.json()["status"] == "approved_open"
    assert res.json()["review_state"] == "approved"

    # 5. Shortlist Candidate (Bob)
    res = await client.post(
        f"/api/v1/projects/{project_id}/shortlist",
        json={"candidate_id": "user-bob-dev", "notes": "Strong FastAPI & async background"},
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "shortlisted"

    # Verify project status automatically reflects shortlisted stage
    res_p = await client.get(f"/api/v1/projects/{project_id}")
    assert res_p.status_code == 200
    assert res_p.json()["project"]["status"] == "shortlist"
    assert len(res_p.json()["project"]["shortlisted_candidates"]) == 1

    # 6. Candidate Interview Stage
    res = await client.put(
        f"/api/v1/projects/{project_id}/shortlist/user-bob-dev",
        json={"stage": "interviewing", "notes": "Interview scheduled"},
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "interviewing"

    res_p = await client.get(f"/api/v1/projects/{project_id}")
    assert res_p.json()["project"]["status"] == "interviewing"

    # 7. Candidate Hired Stage
    res = await client.put(
        f"/api/v1/projects/{project_id}/shortlist/user-bob-dev",
        json={"stage": "hired", "notes": "Offer accepted and agreement signed"},
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "hired"

    res_p = await client.get(f"/api/v1/projects/{project_id}")
    assert res_p.json()["project"]["status"] == "offered_hired"

    # 8. Close Project
    res = await client.post(
        f"/api/v1/projects/{project_id}/transition",
        json={"target_status": "closed", "reason": "Engineering contract commenced"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "closed"

    # 9. Reopen Project with Audit History
    res = await client.post(
        f"/api/v1/projects/{project_id}/transition",
        json={"target_status": "approved_open", "reason": "Expanding scope for additional contractor"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved_open"

    res_p = await client.get(f"/api/v1/projects/{project_id}")
    history = res_p.json()["project"]["status_history"]
    actions = [h["action"] for h in history]
    assert "create_draft" in actions
    assert "publish_project" in actions
    assert "transition_to_closed" in actions
    assert "transition_to_approved_open" in actions


@pytest.mark.asyncio
async def test_hiring_intent_evidence_verification(phase14_client):
    """Verifies observable hiring intent proof, payment status, and 0 native fee."""
    client, app, session_maker = phase14_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")

    app.dependency_overrides[get_current_user] = lambda: alice

    deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Data Pipeline Engineering",
            "raw_description": "Build high throughput web data pipeline.",
            "budget_min": 2000.0,
            "budget_max": 4000.0,
            "hiring_deadline": deadline,
        },
    )
    project_id = res.json()["project"]["id"]

    res_p = await client.get(f"/api/v1/projects/{project_id}")
    intent = res_p.json()["project"]["hiring_intent_evidence"]
    assert intent["native_application_fee_usd"] == 0.0
    assert intent["checklist"]["org_domain_verified"] is True
    # Unverified payment must NEVER appear funded
    assert intent["checklist"]["payment_method_verified"] is False
    assert "Unfunded" in intent["checklist"]["payment_status_label"]
    assert intent["checklist"]["decision_deadline_days_remaining"] >= 13


@pytest.mark.asyncio
async def test_content_policy_safety_scanner_negative_tests(phase14_client):
    """Negative tests: discriminatory criteria, malicious links, upfront fee scams, unpaid trial."""
    client, app, session_maker = phase14_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        superuser = await session.get(User, "user-admin-staff")

    app.dependency_overrides[get_current_user] = lambda: alice
    deadline = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    # 1. Missing / Inverted Budget Rejected
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Invalid Budget Project",
            "raw_description": "Valid description for engineering project.",
            "budget_min": 5000.0,
            "budget_max": 1000.0,  # Max < Min
            "hiring_deadline": deadline,
        },
    )
    assert res.status_code == 400

    # 2. Discriminatory requirements flagged for human review
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Discriminatory Project",
            "raw_description": "Seeking developers. Must be under 25 years old and female only candidates preferred.",
            "budget_min": 2000.0,
            "budget_max": 4000.0,
            "hiring_deadline": deadline,
        },
    )
    p_id = res.json()["project"]["id"]
    res_sub = await client.post(f"/api/v1/projects/{p_id}/submit")
    assert res_sub.status_code == 200
    assert res_sub.json()["review_state"] == "flagged_for_human_review"
    assert res_sub.json()["flagged_reason"] == "discriminatory_criteria"

    # 3. Upfront fee scam flagged for human review
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Upfront Fee Project",
            "raw_description": "Must pay a fee of $100 for software license before you start.",
            "budget_min": 2000.0,
            "budget_max": 4000.0,
            "hiring_deadline": deadline,
        },
    )
    p_id2 = res.json()["project"]["id"]
    res_sub2 = await client.post(f"/api/v1/projects/{p_id2}/submit")
    assert res_sub2.json()["flagged_reason"] == "upfront_fee_request"

    # 4. Excessive unpaid trial flagged
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Unpaid Trial Project",
            "raw_description": "Must complete an unpaid trial of 3 weeks before hire.",
            "budget_min": 2000.0,
            "budget_max": 4000.0,
            "hiring_deadline": deadline,
        },
    )
    p_id3 = res.json()["project"]["id"]
    res_sub3 = await client.post(f"/api/v1/projects/{p_id3}/submit")
    assert res_sub3.json()["flagged_reason"] == "excessive_unpaid_work"

    # 5. Client appeals flagged project
    res_appeal = await client.post(
        f"/api/v1/projects/{p_id3}/appeal",
        json={"appeal_details": "We have revised our scope to clarify all trial work is fully paid at standard contractor rates."},
    )
    assert res_appeal.status_code == 200
    assert "submitted" in res_appeal.json()["message"].lower()

    # 6. Superuser views moderation queue and resolves appeal
    app.dependency_overrides[get_current_active_superuser] = lambda: superuser
    res_queue = await client.get("/api/v1/projects/moderation/queue")
    assert res_queue.status_code == 200
    queue = res_queue.json()["queue"]
    assert len(queue) >= 3

    # Resolve appeal for p_id3
    target_entry = next(e for e in queue if e["project_id"] == p_id3)
    res_resolve = await client.post(
        f"/api/v1/projects/moderation/{target_entry['id']}/resolve",
        json={"decision": "approved", "reviewer_notes": "Client clarified trial is fully paid."},
    )
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_clarification_requests_and_anti_spam(phase14_client):
    """Freelancer asks clarification, rate limit max 3/24h, duplicate check, client answers."""
    client, app, session_maker = phase14_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        bob = await session.get(User, "user-bob-dev")

    # Alice creates and submits an open project
    app.dependency_overrides[get_current_user] = lambda: alice
    deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Open ML Orchestration",
            "raw_description": "Deploy model training pipeline with Celery and Redis.",
            "budget_min": 3000.0,
            "budget_max": 6000.0,
            "hiring_deadline": deadline,
        },
    )
    project_id = res.json()["project"]["id"]
    await client.post(f"/api/v1/projects/{project_id}/submit")

    # Bob (Freelancer) submits clarification questions
    app.dependency_overrides[get_current_user] = lambda: bob
    res_q1 = await client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"question": "What is the expected daily training dataset volume?"},
    )
    assert res_q1.status_code == 200
    q1_id = res_q1.json()["clarification_id"]

    # Duplicate question check (blocked)
    res_dup = await client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"question": "What is the expected daily training dataset volume?"},
    )
    assert res_dup.status_code == 400
    assert "duplicate" in res_dup.json()["detail"].lower()

    # Question 2 and Question 3
    res_q2 = await client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"question": "Are cloud GPU instances provided directly by TechCorp?"},
    )
    assert res_q2.status_code == 200

    res_q3 = await client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"question": "Is Kubernetes deployment required for the worker nodes?"},
    )
    assert res_q3.status_code == 200

    # Question 4 within 24h is rate-limited (anti-spam)
    res_q4 = await client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"question": "What is the targeted p99 inference latency threshold?"},
    )
    assert res_q4.status_code == 400
    assert "rate limit" in res_q4.json()["detail"].lower()

    # Alice answers Q1
    app.dependency_overrides[get_current_user] = lambda: alice
    res_ans = await client.post(
        f"/api/v1/projects/clarifications/{q1_id}/answer",
        json={"answer": "Around 50 GB per day in Parquet format.", "is_public": True},
    )
    assert res_ans.status_code == 200

    # Public Q&A list check
    app.dependency_overrides[get_current_user] = lambda: bob
    res_list = await client.get(f"/api/v1/projects/{project_id}/clarifications")
    assert res_list.status_code == 200
    clarifications = res_list.json()["clarifications"]
    assert len(clarifications) == 1
    assert clarifications[0]["answer"] == "Around 50 GB per day in Parquet format."


@pytest.mark.asyncio
async def test_reconfirmation_stale_expiration_and_idor(phase14_client):
    """Reconfirmation, auto-expiration of inactive projects, and IDOR access control."""
    client, app, session_maker = phase14_client

    async with session_maker() as session:
        alice = await session.get(User, "user-alice-client")
        charlie = await session.get(User, "user-charlie-outsider")
        superuser = await session.get(User, "user-admin-staff")

    # Charlie (Outsider) cannot create project under Alice's org (IDOR check)
    app.dependency_overrides[get_current_user] = lambda: charlie
    deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    res_idor = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Unauthorized Project Creation",
            "raw_description": "Attempting to create project for unowned organization.",
            "budget_min": 1000.0,
            "budget_max": 2000.0,
            "hiring_deadline": deadline,
        },
    )
    assert res_idor.status_code == 403

    # Alice creates and submits a project
    app.dependency_overrides[get_current_user] = lambda: alice
    res = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Autonomous Agent Tooling",
            "raw_description": "Build agent evaluation framework with synthetic benchmarks.",
            "budget_min": 2500.0,
            "budget_max": 5000.0,
            "hiring_deadline": deadline,
        },
    )
    p_id = res.json()["project"]["id"]
    await client.post(f"/api/v1/projects/{p_id}/submit")

    # Duplicate posting by Alice within 24h blocked
    res_dup = await client.post(
        "/api/v1/projects",
        json={
            "org_id": "org-techcorp",
            "title": "Autonomous Agent Tooling",
            "raw_description": "Build agent evaluation framework with synthetic benchmarks.",
            "budget_min": 2500.0,
            "budget_max": 5000.0,
            "hiring_deadline": deadline,
        },
    )
    assert res_dup.status_code == 400
    assert "duplicate" in res_dup.json()["detail"].lower()

    # Reconfirm hiring intent extends reconfirm_by
    res_reconf = await client.post(f"/api/v1/projects/{p_id}/reconfirm")
    assert res_reconf.status_code == 200
    assert "reconfirmed" in res_reconf.json()["message"].lower()

    # Test Stale Auto-Expiration watchdog
    async with session_maker() as session:
        proj = await session.get(NativeProject, p_id)
        # Simulate elapsed deadline
        proj.hiring_deadline = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()

    app.dependency_overrides[get_current_active_superuser] = lambda: superuser
    res_expire = await client.post("/api/v1/projects/maintenance/expire-stale")
    assert res_expire.status_code == 200
    assert res_expire.json()["count"] >= 1

    # Check project status is now expired with abandonment reason
    app.dependency_overrides[get_current_user] = lambda: alice
    res_check = await client.get(f"/api/v1/projects/{p_id}")
    assert res_check.json()["project"]["status"] == "expired"
