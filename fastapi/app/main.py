from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    admin,
    auth,
    billing,
    copilot,
    contracts,
    feedback,
    finance,
    health,
    integrations,
    jobs,
    matching,
    network,
    notifications,
    ops,
    pipeline,
    preferences,
    projects,
    roadmap,
    telemetry,
    trust,
    users,
)
from app.core.errors import error_envelope
from app.core.exceptions import AppException
from app.core.logging.logger import get_logger
from app.core.middleware import RequestIdMiddleware, get_request_id
from backend.application.services.scrape_service import ScrapeService
from config.settings import get_settings
from database.core.base import Base
from database.core.schema_patch import ensure_missing_columns
from database.core.session import get_engine, get_session
from database.models import (  # noqa: F401
    AgentRun,
    AgentToolCall,
    AuditEvent,
    CancellationFeedback,
    CopilotDraft,
    JobApplication,
    JobRecord,
    JobSource,
    LeadNote,
    LeadReminder,
    LeadStageEvent,
    LeadTask,
    NotificationDelivery,
    NotificationRecord,
    PipelineUndoEvent,
    RoadmapVote,
    User,
    UserConsent,
    UserLeadAction,
    UserPreferences,
)
from database.models.listing_report import (  # noqa: F401
    ListingReport,
    ListingReportCorrection,
)
from database.models.audit import AuditEvent
from fastapi import FastAPI

logger = get_logger(__name__)
settings = get_settings()

# Fail fast on clearly unsafe production config (values never logged).
if settings.is_production:
    logger.info(
        "Starting in production; optional integrations disabled when credentials absent"
    )

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=1.0 if not settings.is_production else 0.1,
    )


async def _run_scrape_cycle(reason: str) -> None:
    try:
        async with get_session() as session:
            summary = await ScrapeService(session).run(
                settings.scrape_source_list,
                limit=settings.scrape_limit,
                notify_matches=settings.scrape_notify_matches,
            )
            logger.info("Scrape (%s): %s", reason, summary)
    except Exception:
        # Keep the scheduler alive even if a cycle raises unexpectedly.
        logger.exception("Scrape cycle failed (%s)", reason)


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    interval = max(settings.scrape_interval_minutes, 1) * 60
    logger.info(
        "Scrape scheduler enabled every %s minutes", settings.scrape_interval_minutes
    )
    while not stop_event.is_set():
        await _run_scrape_cycle("scheduler")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scrape scheduler wait failed; continuing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_missing_columns(engine)
    # Restore reversible source kill switches from durable operator audit records.
    async with get_session() as session:
        controls = await session.execute(
            select(AuditEvent).where(AuditEvent.action.in_([
                "source_operator_disabled", "source_operator_enabled"
            ])).order_by(AuditEvent.created_at.desc())
        )
        seen_sources: set[str] = set()
        from app.ingestion.governance import set_operator_disabled
        for control in controls.scalars().all():
            source_key = (control.meta or {}).get("source_key")
            if source_key and source_key not in seen_sources:
                set_operator_disabled(source_key, control.action == "source_operator_disabled")
                seen_sources.add(source_key)
    logger.info("Database schema ready (%s)", settings.database_url.split("://")[0])

    stop_event = asyncio.Event()
    scheduler_task: asyncio.Task | None = None

    if settings.scrape_on_startup:
        asyncio.create_task(_run_scrape_cycle("startup"))

    if settings.scrape_interval_minutes > 0:
        scheduler_task = asyncio.create_task(_scheduler_loop(stop_event))

    yield

    stop_event.set()
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"
    openapi_url = None if settings.is_production else "/openapi.json"

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    origins = settings.cors_origin_list
    if not origins:
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

    def _cors_headers(request) -> dict[str, str]:
        """Ensure error responses still carry CORS when middleware is bypassed."""
        origin = request.headers.get("origin")
        if not origin:
            return {}
        if origin not in origins and "*" not in origins:
            return {}
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
        return headers

    def _json_error(request, content: dict, status_code: int) -> JSONResponse:
        return JSONResponse(
            content, status_code=status_code, headers=_cors_headers(request)
        )

    # Security headers first (inner); CORS added last so it wraps all responses
    # including exception-handler JSON and BaseHTTPMiddleware edge cases.
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; font-src 'self' data: https:; connect-src 'self'"
        )
        return response

    app.add_middleware(RequestIdMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(integrations.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(preferences.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(copilot.router, prefix="/api/v1")
    app.include_router(contracts.router, prefix="/api/v1")
    app.include_router(ops.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(roadmap.router, prefix="/api/v1")
    app.include_router(feedback.router, prefix="/api/v1")
    app.include_router(telemetry.router, prefix="/api/v1")
    app.include_router(trust.router, prefix="/api/v1")
    app.include_router(finance.router, prefix="/api/v1")
    app.include_router(network.router, prefix="/api/v1")
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(matching.router, prefix="/api/v1")

    app.include_router(auth.router)
    app.include_router(billing.router)
    app.include_router(health.router)
    app.include_router(integrations.router)
    app.include_router(jobs.router)
    app.include_router(notifications.router)
    app.include_router(preferences.router)
    app.include_router(pipeline.router)
    app.include_router(copilot.router)
    app.include_router(contracts.router)
    app.include_router(ops.router)
    app.include_router(users.router)
    app.include_router(admin.router)
    app.include_router(roadmap.router)
    app.include_router(feedback.router)
    app.include_router(telemetry.router)
    app.include_router(trust.router)
    app.include_router(finance.router)
    app.include_router(matching.router)

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/health",
            "jobs": "/jobs",
            "scrape": "POST /jobs/scrape",
            "sources": settings.scrape_source_list,
            "scheduler_minutes": settings.scrape_interval_minutes,
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc):
        rid = get_request_id(request)
        logger.warning("HTTP exception: %s request_id=%s", exc.detail, rid)
        return _json_error(
            request,
            error_envelope(
                detail=exc.detail,
                code=f"http_{exc.status_code}",
                request_id=rid,
            ),
            exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        rid = get_request_id(request)
        errs = jsonable_encoder(exc.errors())
        logger.warning("Validation error: %s request_id=%s", errs, rid)
        return _json_error(
            request,
            error_envelope(
                detail=errs,
                code="validation_error",
                request_id=rid,
                errors=errs,
            ),
            422,
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc):
        rid = get_request_id(request)
        logger.error("App exception: %s request_id=%s", exc.message, rid)
        return _json_error(
            request,
            error_envelope(
                detail=exc.message,
                code="app_error",
                request_id=rid,
            ),
            exc.status_code,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        rid = get_request_id(request)
        logger.exception("Unhandled exception request_id=%s", rid)
        return _json_error(
            request,
            error_envelope(
                detail="Internal server error",
                code="internal_error",
                request_id=rid,
            ),
            500,
        )

    return app


app = create_app()
