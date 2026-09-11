#!/usr/bin/env python3
"""Periodic scrape worker. Prefer API SCRAPE_INTERVAL_MINUTES for in-process scheduling."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import httpx


async def cycle(api: str, sources: list[str], limit: int, notify: bool, token: str | None) -> dict:
    payload = {"sources": sources, "limit": limit, "notify_matches": notify}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{api.rstrip('/')}/jobs/scrape", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run scrape once or on an interval")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["remoteok", "arbeitnow", "himalayas", "jobicy"],
    )
    parser.add_argument("--interval-minutes", type=int, default=0, help="0 = run once")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument(
        "--token",
        default=os.getenv("SIGNAL_DESK_TOKEN"),
        help="JWT access token (or set SIGNAL_DESK_TOKEN)",
    )
    args = parser.parse_args()

    if not args.token:
        parser.error("--token or SIGNAL_DESK_TOKEN is required")

    while True:
        result = await cycle(args.api, args.sources, args.limit, args.notify, args.token)
        print(json.dumps(result, indent=2))
        if args.interval_minutes <= 0:
            return 0
        await asyncio.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except httpx.HTTPError as exc:
        print(f"Worker failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
