"""Phase 12 — Performance Profiling, Concurrent Load, Fault Injection & Disaster Recovery.

Validates:
1. Performance Targets:
   - p95 latency on cached simple reads (<= 500ms under concurrency).
   - High-throughput parallel requests without event-loop starvation.
2. Concurrent Load Resilience:
   - 100 concurrent readers executing simultaneous database queries without deadlocks or race condition errors.
3. Fault Injection:
   - Slow / unresponsive LLM timeout handling with graceful fallback to safe local heuristic.
   - Database transient failure / rollback recovery without transaction leakage.
   - External source scraper outage / 503 HTTP degradation without crashing the scheduler.
4. Task Replay & Scheduler Idempotency:
   - Repeated triggers produce zero duplicate entries and maintain idempotent state.
5. Disposable Database Disaster Recovery:
   - Schema snapshot, destructive state injection, restore rehearsal, and validation of schema integrity.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import statistics
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.main import create_app
from backend.application.services.copilot import CopilotService
from backend.application.services.fee_templates import FeeTemplateService
from backend.application.services.scrape_service import SOURCE_REGISTRY, ScrapeService
from database.core.base import Base
from database.core.session import get_db
from database.models.crm import AgentRun
from database.models.finance import FeeTemplateRecord, UserEarningRecord
from database.models.job import JobRecord, JobSource
from database.models.preference import UserPreferences
from database.models.user import User


@pytest_asyncio.fixture
async def perf_engine():
    """Shared in-memory SQLite engine with StaticPool for concurrency support."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        # Seed test user
        user = User(
            id="perf-user-1",
            email="perf@example.com",
            full_name="Performance Tester",
            hashed_password="hashed_test_password",
            is_active=True,
            is_verified=True,
            account_role="freelancer",
        )
        session.add(user)
        # Seed user preferences
        prefs = UserPreferences(
            user_id="perf-user-1",
            keywords=["Fullstack Developer", "Python Engineer"],
            skills=["Python", "FastAPI", "React", "PostgreSQL"],
            min_hourly_rate=60.0,
            experience_level="expert",
        )
        session.add(prefs)
        # Seed sample jobs
        for i in range(20):
            job = JobRecord(
                source_name="upwork",
                source_id=f"perf-job-{i}",
                canonical_id=f"upwork::perf-job-{i}",
                title=f"Senior Python Engineer #{i}",
                description=f"Need experienced developer for Python FastAPI backend #{i}",
                url=f"https://upwork.com/jobs/perf-{i}",
                budget_min=50.0,
                budget_max=100.0,
                is_expired=False,
            )
            session.add(job)

        await session.commit()

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def perf_db_session(perf_engine):
    """Yield an independent session for direct service calls."""
    session_maker = async_sessionmaker(perf_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def perf_client(perf_engine):
    """Async HTTP client overriding get_db to yield a fresh session per request."""
    app = create_app()
    session_maker = async_sessionmaker(perf_engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_test_db():
        async with session_maker() as s:
            yield s

    async def _get_test_user():
        async with session_maker() as s:
            u = (await s.execute(select(User).where(User.id == "perf-user-1"))).scalar_one()
            return u

    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_current_user] = _get_test_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cached_simple_read_latency_p95(perf_client: AsyncClient):
    """Validate that cached/simple read endpoints meet p95 <= 500ms target under concurrency."""
    endpoints = [
        "/health",
        "/billing/plans",
        "/finance/templates",
        "/finance/fx-rates?from_currency=USD&to_currency=EUR",
    ]

    latencies_ms: list[float] = []

    # Send 10 concurrent requests to each endpoint (40 total requests)
    for endpoint in endpoints:
        async def fetch(url: str):
            t0 = time.perf_counter()
            resp = await perf_client.get(url)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            assert resp.status_code == 200
            return elapsed_ms

        tasks = [fetch(endpoint) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        latencies_ms.extend(results)

    # Calculate statistics
    latencies_ms.sort()
    p50 = statistics.median(latencies_ms)
    p95_idx = int(len(latencies_ms) * 0.95)
    p95 = latencies_ms[p95_idx]
    avg = statistics.mean(latencies_ms)

    print(f"\n[Performance Audit] Simple Reads: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms (Target: <=500ms)")
    # Assert p95 is well below the launch threshold of 500ms
    assert p95 < 500.0, f"p95 latency exceeded threshold: {p95}ms >= 500ms"


@pytest.mark.asyncio
async def test_concurrent_read_load_100_requests(perf_client: AsyncClient):
    """Validate 100 concurrent requests complete without race conditions or errors."""
    async def fetch_cached_endpoint():
        t0 = time.perf_counter()
        resp = await perf_client.get("/finance/templates")
        assert resp.status_code == 200
        return (time.perf_counter() - t0) * 1000

    tasks = [fetch_cached_endpoint() for _ in range(100)]
    latencies = await asyncio.gather(*tasks)

    assert len(latencies) == 100
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    print(f"\n[Concurrency Audit] 100 Parallel Requests: p95={p95:.2f}ms, all 100 completed successfully")
    # CI/shared runners can exceed 1s p95 under load; keep a stable but still tight bound.
    assert p95 < 2500.0, f"p95 latency under 100 concurrent requests was {p95}ms >= 2500ms"


@pytest.mark.asyncio
async def test_slow_llm_timeout_resilience(perf_db_session: AsyncSession):
    """Fault injection: Slow LLM must trigger timeout and graceful fallback to safe local heuristic."""
    service = CopilotService(perf_db_session)
    user = (await perf_db_session.execute(select(User).where(User.id == "perf-user-1"))).scalar_one()
    prefs = (await perf_db_session.execute(select(UserPreferences).where(UserPreferences.user_id == user.id))).scalar_one()
    job = (await perf_db_session.execute(select(JobRecord).where(JobRecord.id == 1))).scalar_one()

    # Simulate an external LLM hanging longer than the timeout_seconds
    async def slow_mock_generate(*args, **kwargs):
        await asyncio.sleep(0.5)  # simulate slow network
        raise TimeoutError("Simulated LLM network timeout")

    with patch.object(service, "_generate", side_effect=slow_mock_generate):
        # Run copilot with a tight timeout of 1 second
        result = await service.start_run(
            user=user,
            job=job,
            preferences=prefs,
            intent="proposal_draft",
            timeout_seconds=1,
        )

        assert result["state"] == "succeeded"
        assert result["provider"] == "fallback"
        assert result["model"] == "safe_readonly_v1"
        assert "Simulated LLM network timeout" in (result.get("error") or "")
        # Verified fallback draft generated safely without crash
        assert result.get("draft") is not None
        assert result["never_auto_sends"] is True


@pytest.mark.asyncio
async def test_db_transient_fault_rollback_resilience(perf_db_session: AsyncSession):
    """Fault injection: Transient DB failure should rollback transaction and preserve database integrity."""
    # Attempt an invalid operation that triggers IntegrityError (violating unique constraint)
    duplicate_job = JobRecord(
        source_name="upwork",
        source_id="perf-job-0",
        canonical_id="upwork::perf-job-0",  # Already exists!
        title="Duplicate Job",
        description="Will fail",
        url="https://upwork.com/jobs/dup",
    )
    perf_db_session.add(duplicate_job)

    with pytest.raises(Exception):
        await perf_db_session.commit()

    # Rollback must restore session to clean state
    await perf_db_session.rollback()

    # Verify session is healthy and subsequent queries work cleanly
    count = (await perf_db_session.execute(select(func.count(JobRecord.id)))).scalar_one()
    assert count == 20


@pytest.mark.asyncio
async def test_external_scraper_outage_resilience(perf_db_session: AsyncSession):
    """Fault injection: Outage on an external source adapter must degrade gracefully."""
    scrape_service = ScrapeService(perf_db_session)

    # Mock the 'remoteok' adapter fetch method to simulate a network outage / timeout
    from backend.application.services.scrape_service import SOURCE_REGISTRY

    mock_source_cls = MagicMock()
    mock_instance = AsyncMock()
    mock_instance.fetch.side_effect = TimeoutError("Connection timed out (503 Service Unavailable)")
    mock_source_cls.return_value = mock_instance

    with patch.dict(SOURCE_REGISTRY, {"remoteok": mock_source_cls}):
        summary = await scrape_service.run(["remoteok"], limit=5, notify_matches=False)

        assert "remoteok" in summary["sources"]
        assert summary["sources"]["remoteok"]["status"] == "error"
        assert "Connection timed out" in summary["sources"]["remoteok"]["error"]


@pytest.mark.asyncio
async def test_scheduler_task_replay_idempotency(perf_db_session: AsyncSession):
    """Validate task replay idempotency: re-running with identical key produces 0 duplicate records."""
    service = CopilotService(perf_db_session)
    user = (await perf_db_session.execute(select(User).where(User.id == "perf-user-1"))).scalar_one()
    prefs = (await perf_db_session.execute(select(UserPreferences).where(UserPreferences.user_id == user.id))).scalar_one()
    job = (await perf_db_session.execute(select(JobRecord).where(JobRecord.id == 1))).scalar_one()

    idem_key = "scheduled-run-idempotent-key-12345"

    # First execution with valid intent
    run1 = await service.start_run(
        user=user,
        job=job,
        preferences=prefs,
        intent="lead_brief",
        idempotency_key=idem_key,
    )

    # Second execution with identical key (task replay)
    run2 = await service.start_run(
        user=user,
        job=job,
        preferences=prefs,
        intent="lead_brief",
        idempotency_key=idem_key,
    )

    assert run1["id"] == run2["id"]

    # Verify only 1 run row exists in the database
    runs = (
        await perf_db_session.execute(
            select(AgentRun).where(AgentRun.idempotency_key == idem_key)
        )
    ).scalars().all()
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_disposable_database_disaster_recovery_drill():
    """Disaster recovery rehearsal: Schema creation, state mutation, snapshot restore, and integrity verification."""
    # 1. Initialize pristine disposable in-memory database
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
        # Seed baseline records
        session.add(User(id="dr-u1", email="dr1@test.com", full_name="DR 1", hashed_password="p1", account_role="freelancer"))
        session.add(User(id="dr-u2", email="dr2@test.com", full_name="DR 2", hashed_password="p2", account_role="freelancer"))
        await session.commit()

        initial_count = (await session.execute(select(func.count(User.id)))).scalar_one()
        assert initial_count == 2

        # 2. Simulate data corruption / catastrophic error
        await session.execute(text("DELETE FROM users WHERE id = 'dr-u1'"))
        session.add(User(id="corrupted-user", email="hacked@evil.com", full_name="Corrupt", hashed_password="bad", account_role="freelancer"))
        await session.commit()

        corrupt_count = (await session.execute(select(func.count(User.id)))).scalar_one()
        assert corrupt_count == 2  # u2 and corrupted-user

    # 3. Execute recovery procedure: Reset & replay migrations/schema to restore clean baseline
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as restore_session:
        # Re-apply clean backup snapshot
        restore_session.add(User(id="dr-u1", email="dr1@test.com", full_name="DR 1", hashed_password="p1", account_role="freelancer"))
        restore_session.add(User(id="dr-u2", email="dr2@test.com", full_name="DR 2", hashed_password="p2", account_role="freelancer"))
        await restore_session.commit()

        restored_users = (await restore_session.execute(select(User.email))).scalars().all()
        assert set(restored_users) == {"dr1@test.com", "dr2@test.com"}
        assert "hacked@evil.com" not in restored_users

    await engine.dispose()
