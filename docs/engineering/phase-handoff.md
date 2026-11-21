# Phase handoff

**Current phase completed:** 08 (freelancer OS — pipeline CRM + copilot) after 01–07  
**Do not deploy** without explicit approval. Ensure Alembic `20261122_copilot_crm_workflow` (or `schema_patch` / `create_all` for new CRM tables + `user_lead_actions` CRM columns) is applied.

## Phase 08 summary

- Explicit pipeline stages with history; Save/Skip/`pitched`/`won` migrated safely
- Notes, tasks, deduped reminders, tags, employer/contact fields
- Apply-click distinguished from confirmed application
- Board/list UI, search, bulk internal stage moves + undo, CSV/ICS export
- Typed AI copilot (brief, gaps, portfolio, proposal, interview, scope, negotiation)
- Durable agent runs (id, state, tool history redacted, budgets, cancel/retry/idempotency)
- Grounded drafts + unverified-claim highlights; adversarial listing text sanitized
- Workspace dashboard (real data vs separate sample/demo)
- Per-plan productivity entitlements without limiting native apply or organic rank

Docs: `phase-08.md`

## Verification evidence

- `tests.test_phase08_crm_copilot`: stage mapping, sanitization, entitlements, bulk guard, reminder dedupe, copilot fallback/isolation/tools, demo dashboard
- Frontend: `tests/app/pipeline-page.test.tsx`

## Carry-forward

- Playwright + axe CI for full acceptance browser flow
- Orphan Celery beat / stale sweep wiring
- Scheduled draft/note retention purge job (policy values shipped; sweeper optional)
- Multi-user team workspaces (explicitly out of single-user-first scope)
- Persistent Redis quarantine DB table (optional)
- Larger matching holdout before promoting `hybrid_v1`

## Next prompt recommendations

1. Playwright acceptance: save → brief → draft → applied → follow-up → won/lost → export
2. Retention sweeper for drafts/notes past plan TTL
3. Wire orphan Celery beat schedules
