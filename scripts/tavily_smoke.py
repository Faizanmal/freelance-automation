#!/usr/bin/env python3
"""Smoke-check discovery lead quality: Tavily first, SerpAPI fallback.

Usage (from repo root, with fastapi/.env loaded via Settings):

  set PYTHONPATH=.
  python scripts/tavily_smoke.py
  python scripts/tavily_smoke.py --mode freelance --limit 5

Does not require the API server. Needs TAVILY_API_KEY and/or SERPAPI_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FASTAPI = ROOT / "fastapi"
if str(FASTAPI) not in sys.path:
    sys.path.insert(0, str(FASTAPI))


async def run_mode(mode: str, limit: int) -> list[dict]:
    from app.integrations.serpapi_discovery import (
        discovery_provider_status,
        search_discovery,
    )

    status = discovery_provider_status()
    print(f"\n=== mode={mode} providers={status} ===")
    rows = await search_discovery(mode=mode, limit=limit)  # type: ignore[arg-type]
    if not rows:
        print("  (no rows)")
        return []
    for index, row in enumerate(rows, start=1):
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        provider = meta.get("provider") or meta.get("engine") or "?"
        title = (row.get("title") or "")[:80]
        url = row.get("url") or ""
        print(f"  {index}. [{provider}] {title}")
        print(f"     {url}")
    return rows


async def main() -> int:
    parser = argparse.ArgumentParser(description="Tavily→SerpAPI lead quality smoke")
    parser.add_argument(
        "--mode",
        choices=("freelance", "jobs", "companies", "all"),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    from app.integrations.serpapi_discovery import discovery_provider_status

    status = discovery_provider_status()
    if not status.get("ready"):
        print(
            "No discovery provider ready. Set TAVILY_API_KEY and/or SERPAPI_API_KEY "
            "in fastapi/.env"
        )
        return 1

    print(f"Discovery ready: primary={status.get('primary')} fallback={status.get('fallback')}")

    modes = (
        ("freelance", "jobs", "companies")
        if args.mode == "all"
        else (args.mode,)
    )
    total = 0
    for mode in modes:
        rows = await run_mode(mode, args.limit)
        total += len(rows)

    print(f"\nDone. {total} sample lead(s) across {len(modes)} mode(s).")
    if total == 0:
        print("Fail: zero leads — check keys, queries, or provider quotas.")
        return 2
    print("Pass: at least one discovery row returned.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
