# Per-source cost and retention

Estimates for shared discovery inventory. Ranking/digest are out of band.

| Source | Permission | Typical unit cost | Daily budget default (USD) | Rate/hr | Raw retention (days) | Listing TTL (days) | Notes |
|--------|------------|-------------------|----------------------------|---------|----------------------|--------------------|-------|
| serpapi_freelance | conditional | ~$0.01–0.05 / search | 5.0 | 30 | 14 | 30 | Tavily primary; SerpAPI fallback; shared Redis cache |
| serpapi_jobs | conditional | ~$0.01–0.05 / search | 5.0 | 30 | 14 | 30 | Same |
| serpapi_companies | conditional | ~$0.01–0.05 / search | 5.0 | 30 | 14 | 30 | Allowlisted career hosts only |
| serpapi_maps | conditional (Pro) | SerpAPI maps | 5.0 | 30 | 14 | 30 | Opt-in |
| remoteok | authorized | $0 (public API) | 0 | 40 | 14 | 30 | Honor published API terms |
| arbeitnow | authorized | $0 | 0 | 40 | 14 | 45* | |
| himalayas | authorized | $0 | 0 | 40 | 14 | 45* | |
| jobicy | authorized | $0 | 0 | 40 | 14 | 45* | |
| greenhouse / lever / ashby / ats_direct | authorized | $0 | 0 | 60 | 14 | 45* | Official ATS feeds |
| reddit_hiring | conditional | $0–Reddit API | 0 | 12 | 14 | 14 | Prefer public JSON / OAuth |
| hn_hiring | conditional | $0 | 0 | 12 | 14 | 45* | Public HN |
| github_bounties | conditional | $0 | 0 | 12 | 14 | 45* | Public API |
| upwork / freelancer | conditional (Pro) | API quota | 0 | 20 | 14 | 21 | Credentials required |
| peopleperhour / guru | restricted | n/a | — | — | 0 | — | Default-off until licensed |
| remotive / weworkremotely | restricted | n/a | — | — | 0 | — | Demo registry only |
| linkedin_browser / upwork_browser | experimental | n/a | — | — | 0 | — | Default-off; no CAPTCHA bypass |

\* Default TTL 45 when not listed in `SOURCE_TTL_DAYS`.

## Retention rules

- Preserve raw evidence only when `retention_days_raw > 0` and permission is not restricted.
- Expired/removed listings stay marked; revalidation under source TTL + quotas; **never auto-republish** removed jobs.
- Quarantine/dead-letter payloads: ops review; trim to last 500 entries (Redis/local).
- User-facing payloads use excerpts + attribution; full raw HTML is not required for desk UX.

## Spend tracking

`source_spend:{YYYY-MM-DD}:{source}` in Redis (or in-memory fallback). Scrape runner refuses further fetches when `daily_budget_usd` is exceeded.
