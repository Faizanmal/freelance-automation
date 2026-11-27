"""HTTP middleware: request IDs and structured access logging."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging.logger import get_logger

logger = get_logger(__name__)
REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER) or request.headers.get(
            "X-Correlation-Id"
        )
        request_id = (incoming or "").strip() or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        # Lead/Desk reads must never be served from CDN/browser caches — user
        # Save/Skip state changes every click and stale GETs snap the UI back.
        path = request.url.path or ""
        if any(
            marker in path
            for marker in (
                "/preferences/findings",
                "/preferences/demo-findings",
                "/preferences/pipeline-stats",
                "/preferences/leads/",
                "/preferences/match-feedback",
                "/pipeline",
                "/jobs",
                "/notifications/inbox",
            )
        ):
            response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Vary"] = "Authorization, Cookie"
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
