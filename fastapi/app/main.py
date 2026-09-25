from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import auth, billing, health, integrations, jobs, notifications, preferences, users
from config.settings import get_settings
from app.core.exceptions import AppException
from app.core.logging.logger import get_logger
from database.core.base import Base
from database.core.schema_patch import ensure_sqlite_columns
from database.core.session import get_engine, get_session
from database.models import (  # noqa: F401
    JobApplication,
    JobRecord,
    JobSource,
    NotificationDelivery,
    NotificationRecord,
    User,
    UserPreferences,
)
from backend.application.services.scrape_service import ScrapeService

logger = get_logger(__name__)
settings = get_settings()


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
        logger.exception("Scrape cycle failed (%s)", reason)


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    interval = max(settings.scrape_interval_minutes, 1) * 60
    logger.info("Scrape scheduler enabled every %s minutes", settings.scrape_interval_minutes)
    while not stop_event.is_set():
        await _run_scrape_cycle("scheduler")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_sqlite_columns(engine)
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(integrations.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(preferences.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")

    app.include_router(auth.router)
    app.include_router(billing.router)
    app.include_router(health.router)
    app.include_router(integrations.router)
    app.include_router(jobs.router)
    app.include_router(notifications.router)
    app.include_router(preferences.router)
    app.include_router(users.router)

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/health/live",
            "jobs": "/jobs",
            "scrape": "POST /jobs/scrape",
            "sources": settings.scrape_source_list,
            "scheduler_minutes": settings.scrape_interval_minutes,
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc):
        logger.warning("HTTP exception: %s", exc.detail)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        logger.warning("Validation error: %s", exc.errors())
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc):
        logger.error("App exception: %s", exc.message)
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        logger.exception("Unhandled exception")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    return app


app = create_app()
