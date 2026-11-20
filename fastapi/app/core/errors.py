"""Normalized API error envelope helpers (compat: keep ``detail``)."""

from __future__ import annotations

from typing import Any


def error_envelope(
    *,
    detail: Any,
    code: str,
    request_id: str | None = None,
    errors: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Build a stable error body.

    Compatibility: ``detail`` remains the primary field (FastAPI/clients).
    New fields: ``code``, ``request_id``, optional ``errors``.
    """
    body: dict[str, Any] = {
        "detail": detail,
        "code": code,
    }
    if request_id:
        body["request_id"] = request_id
    if errors is not None:
        body["errors"] = errors
    return body
