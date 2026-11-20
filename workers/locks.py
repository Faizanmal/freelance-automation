"""Distributed overlap locks for Celery beat/worker scheduled tasks."""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

LOCK_PREFIX = "signaldesk:lock:"


def _sync_redis():
    """Return a sync Redis client or None when Redis is unavailable/optional."""
    import os

    import redis

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    optional = os.getenv("REDIS_OPTIONAL", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1.5)
        client.ping()
        return client
    except Exception as exc:  # noqa: BLE001 — broker may be down locally
        if not optional:
            raise
        logger.warning("Overlap lock unavailable (Redis): %s", exc.__class__.__name__)
        return None


@contextmanager
def overlap_lock(name: str, ttl_seconds: int = 600) -> Iterator[bool]:
    """
    Acquire a short-lived Redis lock.

    Yields True when the caller owns the lock (or Redis is optional/unavailable
    and we allow local single-process execution). Yields False when another
    worker already holds the lock — caller should skip work.
    """
    token = str(uuid.uuid4())
    key = f"{LOCK_PREFIX}{name}"
    client = _sync_redis()
    if client is None:
        yield True
        return

    acquired = bool(client.set(key, token, nx=True, ex=max(ttl_seconds, 1)))
    try:
        yield acquired
    finally:
        if acquired:
            # Release only if we still own the token (avoid deleting a renewed lock).
            try:
                current = client.get(key)
                if current == token:
                    client.delete(key)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to release lock %s", name)
