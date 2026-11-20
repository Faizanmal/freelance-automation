"""Per-source leases, circuit breakers, quarantine / dead letters."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

# In-memory fallbacks when Redis is unavailable (dev / single-process).
_LOCAL_LEASES: dict[str, float] = {}
_LOCAL_CIRCUITS: dict[str, dict[str, Any]] = {}
_LOCAL_QUARANTINE: list[dict[str, Any]] = []
_LOCAL_SPEND: dict[str, float] = {}

CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 300
LEASE_SECONDS = 120


@dataclass(slots=True)
class SourceRunResult:
    source_name: str
    status: str  # ok | no_results | error | skipped | circuit_open | lease_held
    fetched: int = 0
    ingested: int = 0
    merged: int = 0
    skipped: int = 0
    error: str | None = None
    duration_ms: int | None = None
    quarantine_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "status": self.status,
            "fetched": self.fetched,
            "ingested": self.ingested,
            "merged": self.merged,
            "skipped": self.skipped,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "quarantine_id": self.quarantine_id,
            "details": self.details,
        }


async def acquire_source_lease(
    source_name: str, *, ttl_seconds: int = LEASE_SECONDS
) -> bool:
    """Exclusive per-source lease so many users hunting do not storm providers."""
    key = f"source_lease:{source_name}"
    try:
        redis = await get_redis()
        if redis:
            ok = await redis.set(key, "1", nx=True, ex=ttl_seconds)
            return bool(ok)
    except Exception as exc:  # noqa: BLE001
        logger.debug("lease redis unavailable: %s", exc)
    import time

    now = time.time()
    expires = _LOCAL_LEASES.get(source_name, 0)
    if expires > now:
        return False
    _LOCAL_LEASES[source_name] = now + ttl_seconds
    return True


async def release_source_lease(source_name: str) -> None:
    key = f"source_lease:{source_name}"
    try:
        redis = await get_redis()
        if redis:
            await redis.delete(key)
    except Exception:  # noqa: BLE001
        pass
    _LOCAL_LEASES.pop(source_name, None)


async def circuit_is_open(source_name: str) -> bool:
    key = f"source_circuit:{source_name}"
    try:
        redis = await get_redis()
        if redis:
            raw = await redis.get(key)
            if not raw:
                return False
            data = json.loads(raw)
            return data.get("state") == "open"
    except Exception:  # noqa: BLE001
        pass
    data = _LOCAL_CIRCUITS.get(source_name) or {}
    if data.get("state") != "open":
        return False
    opened = float(data.get("opened_at", 0))
    import time

    return time.time() - opened < CIRCUIT_OPEN_SECONDS


async def record_source_success(source_name: str) -> None:
    key = f"source_circuit:{source_name}"
    try:
        redis = await get_redis()
        if redis:
            await redis.delete(key)
    except Exception:  # noqa: BLE001
        pass
    _LOCAL_CIRCUITS.pop(source_name, None)


async def record_source_failure(source_name: str, *, error: str | None = None) -> bool:
    """Increment failures; open circuit when threshold hit. Returns True if now open."""
    import time

    key = f"source_circuit:{source_name}"
    try:
        redis = await get_redis()
        if redis:
            raw = await redis.get(key)
            data = json.loads(raw) if raw else {"failures": 0}
            data["failures"] = int(data.get("failures", 0)) + 1
            data["last_error"] = error
            if data["failures"] >= CIRCUIT_FAILURE_THRESHOLD:
                data["state"] = "open"
                data["opened_at"] = time.time()
            await redis.set(key, json.dumps(data), ex=CIRCUIT_OPEN_SECONDS * 2)
            return data.get("state") == "open"
    except Exception:  # noqa: BLE001
        pass
    data = _LOCAL_CIRCUITS.get(source_name) or {"failures": 0}
    data["failures"] = int(data.get("failures", 0)) + 1
    data["last_error"] = error
    if data["failures"] >= CIRCUIT_FAILURE_THRESHOLD:
        data["state"] = "open"
        data["opened_at"] = time.time()
    _LOCAL_CIRCUITS[source_name] = data
    return data.get("state") == "open"


async def quarantine_batch(
    *,
    source_name: str,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> str:
    qid = str(uuid4())
    entry = {
        "id": qid,
        "source_name": source_name,
        "reason": reason,
        "payload": payload or {},
        "created_at": datetime.now(UTC).isoformat(),
        "status": "open",
    }
    try:
        redis = await get_redis()
        if redis:
            await redis.lpush("ingestion_quarantine", json.dumps(entry))
            await redis.ltrim("ingestion_quarantine", 0, 499)
            return qid
    except Exception:  # noqa: BLE001
        pass
    _LOCAL_QUARANTINE.insert(0, entry)
    del _LOCAL_QUARANTINE[500:]
    return qid


async def list_quarantine(limit: int = 50) -> list[dict[str, Any]]:
    try:
        redis = await get_redis()
        if redis:
            rows = await redis.lrange("ingestion_quarantine", 0, limit - 1)
            return [json.loads(r) for r in rows]
    except Exception:  # noqa: BLE001
        pass
    return list(_LOCAL_QUARANTINE[:limit])


async def record_spend(source_name: str, amount_usd: float) -> float:
    """Track approximate daily spend; returns new total for source today."""
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"source_spend:{day}:{source_name}"
    try:
        redis = await get_redis()
        if redis:
            total = await redis.incrbyfloat(key, amount_usd)
            await redis.expire(key, 86400 * 2)
            return float(total)
    except Exception:  # noqa: BLE001
        pass
    k = f"{day}:{source_name}"
    _LOCAL_SPEND[k] = _LOCAL_SPEND.get(k, 0.0) + amount_usd
    return _LOCAL_SPEND[k]


async def get_spend_today() -> dict[str, float]:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    out: dict[str, float] = {}
    try:
        redis = await get_redis()
        if redis:
            # Scan is ok for ops console scale.
            async for key in redis.scan_iter(match=f"source_spend:{day}:*"):
                name = key.decode() if isinstance(key, bytes) else str(key)
                source = name.rsplit(":", 1)[-1]
                val = await redis.get(key)
                out[source] = float(val or 0)
            return out
    except Exception:  # noqa: BLE001
        pass
    prefix = f"{day}:"
    for k, v in _LOCAL_SPEND.items():
        if k.startswith(prefix):
            out[k[len(prefix) :]] = v
    return out


async def budget_exceeded(source_name: str, daily_budget_usd: float | None) -> bool:
    if daily_budget_usd is None or daily_budget_usd <= 0:
        return False
    spend = await get_spend_today()
    return spend.get(source_name, 0.0) >= daily_budget_usd
