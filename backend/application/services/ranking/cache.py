"""Stable recommendation cache keys keyed by user/preferences/version."""

from __future__ import annotations

import time
from hashlib import sha1
from typing import Any


def recommendation_cache_key(
    *,
    user_id: str,
    prefs_updated_at: str | None,
    score_version: str,
    retrieval_mode: str,
    limit: int,
    offset: int = 0,
    freelance_focus: bool = False,
    include_skipped: bool = False,
) -> str:
    raw = "|".join(
        [
            str(user_id),
            str(prefs_updated_at or ""),
            score_version,
            retrieval_mode,
            str(int(limit)),
            str(int(offset)),
            "1" if freelance_focus else "0",
            "1" if include_skipped else "0",
        ]
    )
    digest = sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f"rec:{digest}"


class MemoryRecommendationCache:
    """Process-local TTL cache for ranked pages."""

    def __init__(self, ttl_seconds: float = 45.0) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._user_keys: dict[str, set[str]] = {}
        self._user_gen: dict[str, int] = {}
        self.ttl_seconds = ttl_seconds

    def user_gen(self, user_id: str) -> int:
        return int(self._user_gen.get(str(user_id), 0))

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(
        self,
        key: str,
        value: Any,
        *,
        user_id: str | None = None,
        user_gen: int | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        # Drop stale builders that finished after a Save/Skip/Restore invalidated.
        if user_id is not None and user_gen is not None:
            if int(user_gen) != self.user_gen(str(user_id)):
                return
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        self._store[key] = (time.monotonic() + ttl, value)
        if user_id:
            self._user_keys.setdefault(str(user_id), set()).add(key)

    def invalidate_user(self, user_id: str) -> int:
        uid = str(user_id)
        self._user_gen[uid] = self.user_gen(uid) + 1
        keys = list(self._user_keys.pop(uid, set()))
        for key in keys:
            self._store.pop(key, None)
        return len(keys)

    def invalidate_prefix(self, prefix: str = "rec:") -> None:
        drop = [k for k in self._store if k.startswith(prefix)]
        for key in drop:
            del self._store[key]
        if prefix == "rec:":
            self._user_keys.clear()


_CACHE = MemoryRecommendationCache(ttl_seconds=45.0)


def get_recommendation_cache() -> MemoryRecommendationCache:
    return _CACHE
