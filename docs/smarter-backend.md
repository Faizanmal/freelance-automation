# Smarter Backend — Phased Plan

**Goal:** Keep the **shared job pool**. Make ranking and hunting smarter from skills, enrichment, and Save/Skip — not per-user scrapers.

```text
Phase 1  Enrich on ingest (skills, seniority band, engagement, quality)
Phase 2  Skill-aware system hunt queries (aggregate user skills → Tavily/SerpAPI)
Phase 3  Save/Skip feedback into match scores
Phase 4  (Later) Embeddings blend — out of scope for this sprint
```

## Architecture (unchanged)

```
Hunters → enrich → shared jobs DB
                      ↓
         Hunt Rules + feedback → Leads / digest
```

## Phase 1 — Enrichment quality

- Heuristic enrichment with word-boundary skill hits (fix `go`/`ai` false positives).
- Normalize seniority to `junior|mid|senior|lead`.
- Detect `engagement_type`: freelance / contract / full_time / unknown.
- `quality_flags`: unpaid, course/tutorial, spam-ish patterns → matching downranks.
- Persist via existing `job.enrichment`, `job.seniority`, `job.tags`, `job.analysis_summary`.

## Phase 2 — Skill-aware hunts

- Aggregate top skills across active users’ Hunt Rules.
- Build freelance / jobs query strings when system scrape has no explicit `query`.
- Fall back to `SERPAPI_*_QUERY` env defaults when no user skills yet.
- Manual scrape with a user-supplied query still wins.

## Phase 3 — Feedback loop

- From Save/Skip → skills on those jobs (tags/enrichment).
- Boost skills the user saves; soft-penalize skills they skip often.
- Applied in `MatchingService` without changing the pool.

## Phase 4 — Later

- Embedding similarity blended with keyword score.
- Pro gets fresher slice of the same pool.

## Success checks

- New jobs show enrichment skills/seniority/engagement.
- Scheduled/manual hunts without `query` include popular user skills.
- Save a React lead → more React-like leads rise; Skip WordPress → WordPress drops.
