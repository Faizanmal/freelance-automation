"""Normalize DATABASE_URL for asyncpg (Supabase / Neon SSL query params)."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SSL_TRUE = frozenset({"1", "true", "require", "verify-ca", "verify-full"})


def prepare_async_database_url(database_url: str) -> tuple[str, dict]:
    """Return (cleaned_url, connect_args) for create_async_engine.

    asyncpg does not understand libpq ``ssl=require`` / ``sslmode`` query
    params. Strip them and set ``connect_args["ssl"]=True`` instead.
    """
    if database_url.startswith("sqlite"):
        return database_url, {"check_same_thread": False}

    parsed = urlparse(database_url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    kept: list[tuple[str, str]] = []
    want_ssl = False
    for key, value in query_pairs:
        lower = key.lower()
        if lower in {"ssl", "sslmode"}:
            if value.lower() in _SSL_TRUE:
                want_ssl = True
            continue
        kept.append((key, value))

    cleaned = urlunparse(parsed._replace(query=urlencode(kept)))
    connect_args: dict = {}
    if want_ssl:
        connect_args["ssl"] = True
    return cleaned, connect_args
