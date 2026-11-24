"""Worker / beat heartbeats for truthful readiness checks."""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

WORKER_KEY = "signaldesk:heartbeat:worker"
BEAT_KEY = "signaldesk:heartbeat:beat"
# Longer than the 60s heartbeat task interval; short enough to detect a dead beat.
DEFAULT_TTL = 180


def _sync_redis():
    import redis

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    optional = os.getenv("REDIS_OPTIONAL", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1.0)
        client.ping()
        return client
    except Exception as exc:  # noqa: BLE001
        if not optional:
            raise
        logger.debug("Heartbeat Redis unavailable: %s", exc.__class__.__name__)
        return None


def touch_worker(ttl: int = DEFAULT_TTL) -> None:
    client = _sync_redis()
    if client is None:
        return
    client.set(WORKER_KEY, str(int(time.time())), ex=max(ttl, 30))


def touch_beat(ttl: int = DEFAULT_TTL) -> None:
    client = _sync_redis()
    if client is None:
        return
    client.set(BEAT_KEY, str(int(time.time())), ex=max(ttl, 30))


def read_heartbeats() -> dict[str, str]:
    """Return worker/beat status without leaking infra details."""
    client = _sync_redis()
    if client is None:
        return {"worker": "unknown", "beat": "unknown"}
    try:
        worker = client.get(WORKER_KEY)
        beat = client.get(BEAT_KEY)
    except Exception:  # noqa: BLE001
        return {"worker": "unknown", "beat": "unknown"}
    return {
        "worker": "ok" if worker else "stale",
        "beat": "ok" if beat else "stale",
    }
