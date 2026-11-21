# Phase 08 — Freelancer OS: lead pipeline, copilot, collaboration

## Intent

Turn Signal Desk from a feed into a workspace that helps freelancers get paid. The agent assists; the user controls outward actions. No bulk application or unsolicited contact automation.

## What shipped

| Area | Location |
|------|----------|
| Explicit pipeline stages + history | `database/models/crm.py`, `UserLeadAction.pipeline_stage`, `LeadStageEvent` |
| Safe migration from Save/Skip/pitched/won | Alembic `20261122_copilot_crm_workflow` + `STATUS_TO_STAGE` |
| Notes, tasks, reminders (deduped), tags, contacts | `LeadNote`, `LeadTask`, `LeadReminder`, CRM fields on lead action |
| Apply-click ≠ confirmed application | `apply_clicked_at` vs `applied_confirmed_at`; apply flow marks confirmed |
| Board / list / search / filters / bulk internal / undo / export | `PipelineService` + `/api/v1/pipeline/*` + `/pipeline` UI |
| Typed AI copilot intents | `CopilotService` + `/api/v1/copilot/*` |
| Evidence grounding + unverified claims | Draft `evidence` / `unverified_claims`; fabrication pattern scan |
| Adversarial listing isolation | `_sanitize_listing_text`; allowlisted tools only |
| Durable agent runs | `AgentRun` + `AgentToolCall` (redacted); cancel / retry / idempotency |
| Safe readonly fallback when AI unavailable | `safe_readonly_v1` template drafts; never auto-send |
| Workspace dashboard (real vs sample) | `GET /pipeline/dashboard?demo=` |
| Productivity entitlements | `productivity_entitlements()` — does **not** limit native apply or organic rank |
| Draft/note retention policy (per plan) | Entitlement days; soft-delete fields on drafts/notes |

### Locked decisions

- Single-user first (no team workspace tables). Role boundaries remain user-scoped.
- Legacy `status` (`save|skip|pitched|won`) preserved for ranking / Leads UI; `pipeline_stage` is canonical CRM stage.
- `pitched` ↔ `applied` (applied/contacted).
- Copilot **cannot** dispatch outward messages/applications even with `confirm_side_effect`.
- Bulk stage changes allowed for internal CRM only; bulk → `applied` forbidden.
- External applications continue to link to the original listing URL.

### Retention & permissions

| Data | Free | Pro |
|------|------|-----|
| Copilot runs / day | 10 | 100 |
| Token budget / run | 4k | 12k |
| Draft retention (policy) | 30 days | 365 days |
| Note retention (policy) | 90 days | 730 days |

Granular access: all CRM/copilot rows filtered by `user_id`. Cross-tenant run lookup returns 404/`run_not_found`.

## Acceptance flow (manual / browser)

1. Save lead on `/leads` → appears in Pipeline `saved`
2. Copilot **Research brief** → editable grounded draft (or safe fallback)
3. Edit draft → versioned save
4. Mark **applied** (confirmed) — distinct from apply-click
5. Schedule follow-up / reminder
6. Negotiation notes → won/lost
7. Export CSV / ICS

Also verify: false-claim highlighting, adversarial listing text cannot override tools, cancel/retry runs, duplicate reminders collapse, demo dashboard separate from real data, offline/AI-down fallback, no outward send by default.

## Tests

```bash
cd fastapi
set PYTHONPATH=..;.
.venv\Scripts\python -m unittest tests.test_phase08_crm_copilot -v
```

```bash
cd frontend
npm test -- tests/app/pipeline-page.test.tsx
```

## Gate

| Gate | Status |
|------|--------|
| Stages + migration from Save/Skip | Pass |
| Apply-click ≠ confirmed applied | Pass |
| Copilot never auto-sends | Pass |
| Allowlisted tools / listing sanitize | Pass |
| Durable run cancel/retry/idempotency | Pass (unit) |
| Cross-tenant isolation | Pass (unit) |
| Demo vs real dashboard | Pass |
| Entitlements do not gate organic rank / native apply | Pass |
| Playwright full browser acceptance | Deferred (carry-forward) |

## Rollout

1. Apply Alembic `20261122_copilot_crm_workflow` (or rely on `create_all` + `schema_patch` in local).
2. Ship `/pipeline` nav + APIs.
3. Monitor copilot quota 429s and fallback rate.

## Non-claims

- Not a multi-seat team CRM yet.
- Not automated apply / cold outreach.
- Not a substitute for source terms of service on external boards.
