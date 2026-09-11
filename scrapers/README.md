# Scrapers

Source adapters for the Freelance Intelligence platform.

## Public HTTP sources

| Source | Module | Auth |
|--------|--------|------|
| RemoteOK | `sources/remoteok.py` | None |
| Remotive | `sources/remotive.py` | None |
| Arbeitnow | `sources/arbeitnow.py` | None |
| Himalayas | `sources/himalayas.py` | None |
| Jobicy | `sources/jobicy.py` | None |

## Freelance marketplaces (official APIs)

| Source | Module | Auth |
|--------|--------|------|
| Upwork | `sources/upwork.py` | OAuth 2.0 Bearer token |
| Freelancer.com | `sources/freelancer.py` | `Freelancer-OAuth-V1` token |

Product ingestion lives in `fastapi/app/ingestion/sources.py` and calls `fastapi/app/integrations/*` for marketplace auth.

## Playwright framework

`core/` provides browser pool, stealth, rate limits, retries, and selector recovery for future authenticated UI flows. Prefer official APIs for Upwork/Freelancer.

`sources/dummy_scraper.py` remains a framework smoke-test fixture.
