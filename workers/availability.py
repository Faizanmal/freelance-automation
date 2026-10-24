"""Helpers to decide whether Celery can run background work."""

from __future__ import annotations


def celery_workers_online(timeout: float = 0.75) -> bool:
    """Return True when at least one Celery worker answers ping."""
    try:
        from workers.app import celery_app

        inspector = celery_app.control.inspect(timeout=timeout)
        if inspector is None:
            return False
        ping = inspector.ping()
        return bool(ping)
    except Exception:
        # Fail closed for any broker/inspect failure (timeouts, connection errors, etc.).
        return False
