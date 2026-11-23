# Phase 19 — Product learning, outcomes and continuous improvement

## Current evidence and decision

No controlled beta production analytics, opted-in user interviews, source cost ledger, or measured customer outcomes were present in the workspace when this phase was implemented. This document and the new event path prepare staging instrumentation; they do **not** claim users, conversions, market demand, or launch readiness. Marketplace and payments remain gated under Phase 18.

## Event dictionary and capture contract

`fastapi/app/product_events.py` is the allowlist. Authenticated event ingestion is `POST /api/v1/telemetry/product-events`; it requires the user's latest `analytics` consent to be granted. Up to 25 events may be sent per request. Unknown fields/event names and timestamps without timezone or outside the 90-day late-arrival window are rejected. Each event has a client UUID idempotency key scoped to its user. Server assigns `production`, `staging`, `test`, or `development`; clients cannot label data as production/test. The API accepts only a bounded surface enum, no free-form metadata. User deletion cascades to their event rows. There is no anonymous fingerprinting.

| Event | Meaning / truth level |
|---|---|
| `acquisition_landing_viewed` | Landing page view; only consented authenticated events currently supported |
| `activation_onboarding_completed` | Onboarding completion |
| `hunt_completed` | A user completed a discovery hunt |
| `first_qualified_lead` | First hard-filter-qualified lead surfaced |
| `lead_saved`, `lead_skipped` | Save/skip action; wired in the leads UI |
| `external_apply_clicked` | External application link opened; wired in the leads UI and never counted as an application |
| `application_confirmed`, `application_reply_recorded`, `interview_reported` | User-reported external outcomes, not independently verified |
| `contract_acknowledged`, `cash_received_self_reported` | User-reported outcome; no amount or payment details collected |
| `alert_opted_out`, `report_submitted` | User action; no private content collected |
| `subscription_started`, `subscription_canceled` | Subscription lifecycle action; billing source of truth remains provider records |
| `native_project_shortlisted`, `native_project_response_recorded`, `native_contract_completed`, `native_dispute_filed` | Native marketplace workflow; must stay separate from discovery SaaS and require real persisted outcomes |

No prompts, message contents, contact details, job/project identifiers, financial amounts, or raw provider payloads are permitted in product analytics. Event schemas reject extra payload keys. The ingestion event log is append-only through this endpoint; duplicate event keys return a duplicate count. Revoking consent stops new ingestion; existing data remains subject to deletion requests and the retention policy after legal/privacy review. Retention automation is not yet implemented; agree and implement a reviewed retention period before collecting production events.

The API currently wires only lead save, skip, and external apply-click UI actions. The remaining dictionary entries are definitions for future instrumentation, not observed events. Acquisition events from anonymous visits are intentionally not captured by this authenticated event endpoint. Existing operational persisted-record metrics remain separate at `/api/v1/ops/metrics`.

## Dashboard and interpretation

Moderators can read `/api/v1/ops/product-learning`. It returns aggregated event counts by server-assigned environment and event name, never event/user IDs. Counts are suppressed below ten distinct people; empty cells explicitly say `no_observations`, and test/staging/development stay separate from production. Self-reported application/interview/cash events do not establish verified ground truth. The endpoint does not yet compute cohort funnels, time-to-value, acquisition cost, retention, or provider spend. Existing operations dashboard continues to label its own records-only metrics and uninstrumented outcomes.

Before using this data for decisions, add reviewed cohort definitions, denominators, missingness, observation windows, late-arrival handling and source provenance. Reconcile controlled staging scenarios against raw test records and aggregate counts. Never merge test events into production. For source/LLM cost, reconcile provider billing/usage records with application usage counters; do not infer spend from event counts.

## Feedback and research loop

- Use the existing in-product support case, listing correction/report, and cancellation feedback pathways. Support summaries are user submitted; redact private data before exporting or quoting. Conduct interviews only with explicit participation consent and record a de-identified finding, not raw private conversation, in the decision log.
- Review feedback and operational incidents weekly during a pilot; review source policy/provider changes, dependency/security updates, restore evidence, staffing and unit economics monthly. Assign a named human owner before beta. These cadences are proposals; staffing is not evidenced.
- Prioritize each item with severity, frequency, outcome impact, evidence confidence and effort. Mark observations, hypotheses and decisions separately. Use `docs/engineering/decision-log.md` for decisions; publish a user-facing changelog for shipped changes.
- Candidate next release: complete consent-aware event instrumentation for onboarding, first qualified lead, completed hunt, application self-report, alerts and native project milestones; build one privacy-suppressed cohort view with time-to-first-value and reported application rate. Success criteria: each controlled staging journey produces exactly one event per action key, duplicates are ignored, revoked consent rejects events, event counts reconcile, cohorts under ten are suppressed, and production remains empty until real beta activity exists.

## Experiment and rollout guardrails

Ranking/trust/AI changes require versioned data/config, a documented hypothesis, offline holdout/regression checks and a staged feature-flag rollout. Keep deterministic ranking when it performs as well or better at lower cost. Never experiment with paid ranking or discriminatory variables. Track error rate, provider spend, false positives, fairness, latency and user overrides/appeals; define rollback thresholds before exposure. Roll back by disabling the feature flag and preserve the previous configuration. No autopilot production changes.

## Gate checklist

| Gate | Status | Evidence / next step |
|---|---|---|
| Event schema bounded and allowlisted | **Pass (unit checks)** | Phase 19 + Phase 17 focused suite: 6 passed. Pydantic rejects unknown event names and extra fields. Run again on supported Python 3.12/Linux CI. |
| Consent gate and deletion behavior | **Implemented, integration not verified** | Requires analytics consent; user foreign key cascades. Reconcile consent revocation/deletion in DB-backed tests. |
| Idempotency and late events | **Implemented, integration not verified** | Per-user event UUID unique key; accepted timestamp window 90 days. Exercise duplicate database insertion and late batches in CI. |
| Environment separation and privacy suppression | **Unit checks pass; DB integration not verified** | Server-derived environment and ten-person suppression in moderator aggregate API. Verify against controlled seeded records. |
| Workflow coverage and cost reconciliation | Partial / blocked | Only save, skip, and external click UI events wired. Add remaining events and provider-usage reconciliation. |
| Real beta analytics and feedback findings | Not available | No beta cohort or verified production analytics supplied; recruit opt-in users after Phase 18 gate. |
| Research, staffing, public changelog, review cadence | Planned / blocked | Name owners, complete interviews, publish findings and establish review cadence before widening the pilot. |
| Deployment or live feature changes | Not authorized | No production changes or user invitations performed. |

## Verification performed

- `fastapi/.venv` Python compile of the app passed; the focused Phase 19 + Phase 17 privacy tests passed: **6 passed**. Imports and Pydantic event validation were manually exercised. This Windows/Python 3.14 result does not replace CI on the project’s supported Python 3.12/Linux runtime.
- Frontend `npm run test`: **22 files / 61 tests passed**. `npx tsc --noEmit` passed. `npm run lint` exited successfully with **0 errors / 73 existing warnings**.
- `alembic -c database/alembic.ini heads` reports one head: `20261201_product_learning_events_phase19`.
- `git diff --check` passed (repository line-ending notices only).
- No database migration was applied, no staging journey was run, and no production analytics were inspected or created.

**Decision:** instrumentation preparation only. No production analytics claims and no expansion of marketplace scope. Next step is CI verification, then a controlled staging event-reconciliation exercise; a subsequent beta proposal must use observed evidence and require explicit release approval.
