# Phase 18 — Staging, deployment rehearsal and controlled beta gate

## Decision

**Current recommendation: NO GO for any external beta or deployment.** This is a Marketplace beta assessment after Phases 13–17, with the native marketplace disabled by default and all marketplace payment actions contract-only/off. It is not an authorization to deploy, enable flags, or invite users. A later **conditional GO** may be considered for a private, invitation-only, no-payment pilot after every blocking staging and operator gate below is evidenced and an authorized release owner approves it.

**Release identity:** the checkout reports branch `main`, HEAD `d3142ad6b2e585bc6cd7d61c7c3f183c6786c322`, and a dirty worktree with tracked and untracked changes. That SHA is not a releasable pin for this workspace. Freeze and review a clean release commit/tag after the intended changes are committed; record its CI run and artifact digests. The workspace SHA and dirty state are observations, not a release selection.

**Scope:** Marketplace beta after 13–17. Native marketplace remains `FEATURE_MARKETPLACE_ENABLED=false`, `MARKETPLACE_STATUS=private_preview` until the separately approved staging rehearsal. Provider-backed marketplace payments remain unsupported in Phase 16 contract-only mode. Existing SaaS subscription billing is a separate feature and must also remain unconfigured/disabled for this no-billing beta unless its own billing gate passes.

## Evidence checklist

Statuses mean evidence observed in this repository/workspace only; external infrastructure and human evidence are not inferred.

| Gate | Status | Evidence / owner / severity | Next step |
|---|---|---|---|
| Release ref, clean tree, artifact digest | **Fail** | `main`, HEAD `d3142ad…`, dirty worktree. Release owner · Critical | Commit/review intended scope; pin clean SHA/tag and image digest. |
| CI on pinned release | **Blocked** | No CI run/status attached or accessible from this checkout. Local lint passes with 73 warnings; local build is incomplete. Release owner · Critical | Run required GitHub CI on exact release SHA and attach URL/status. |
| Dependency/security review | **Blocked** | No current Dependabot/security review evidence or SBOM attached. Security owner · High | Review dependency alerts and lockfile audit for the pinned SHA; record dispositions. |
| Documented topology | **Pass (docs only)** | `docs/deploy.md`, `compose.yml`, `frontend/vercel.json`, and `cloudbuild.yaml` describe Vercel frontend + single GCP VM with Compose API/worker/beat/Postgres/Redis/Caddy. Cloud Build/Cloud Run is labeled optional. Infra owner · High | Compare against actual cloud/Vercel resources, DNS, TLS, ports, and active revisions; record verified topology. |
| Actual staging parity, isolation, origins, callbacks, TLS | **Blocked** | No staging URL, cloud inventory, DNS/TLS check, callback allowlist, or separate keys/queues/storage evidence in workspace. Docker Desktop engine is unavailable from this session, so no local service inventory could be read. Infra owner · Critical | Identify isolated staging VM/project and Vercel preview origin; verify resources and no shared production data/secrets. |
| Required env presence (values not collected) | **Blocked** | `.env.production.example` lists expected names. Explicit production Compose validation fails closed without `POSTGRES_PASSWORD` and `PUBLIC_API_URL`; actual secret manager/Vercel settings are unavailable here. Infra owner · Critical | Use an approved presence-only checklist (never paste values); verify exact API and frontend origins, callback URLs, DB/Redis, auth, SMTP sandbox, source/LLM, and monitoring settings. |
| Marketplace/payment flags | **Pass (code defaults only)** | `config/settings.py` defaults marketplace off/private preview; Phase 16 capabilities are hard-coded contract-only. `compose.yml` now explicitly passes `FEATURE_MARKETPLACE_ENABLED=false` and `MARKETPLACE_STATUS=private_preview` defaults. Runtime values are unverified. Release operator · Critical | Confirm effective staging values and API capability response; do not enable live payments. |
| Billing boundary | **Blocked** | SaaS Stripe subscription code exists separately; production Compose can pass Stripe credentials. No staging billing decision, account config, cancellation/refund evidence, or live-key presence review. Billing owner · High | Keep SaaS Stripe keys/price unset for this beta unless separately approved and sandbox cancellation/refund tests pass. |
| Migration rehearsal / backup / restore | **Blocked** | One Alembic head is present in checkout (`20261130_marketplace_operations_phase17`); no disposable database migration, backup, restore, or migration-rollback evidence. DB owner · Critical | Restore a sanitized staging clone, run upgrade and app smoke, prove restore, retain revision and backup evidence. Never rehearse on production data without approved protections. |
| Backend API and worker health | **Blocked** | No staging `/health/live` or `/health/ready` response, worker/beat heartbeat, queue lag, or DB/Redis observation attached. SRE owner · Critical | Run staging health probes and inspect API, worker, beat, DB and Redis after deploy. `degraded` is not a clean beta pass. |
| Frontend checks | **Partial** | `npm run test`: 22 files / 61 tests passed. `npm run lint`: exit 0, 0 errors and 73 warnings. TypeScript `tsc --noEmit` passed. Two production build attempts stalled without output and were interrupted. Frontend owner · Critical | Disposition the warnings, complete the production build on Node 22/Linux CI, and attach CI evidence for the pinned SHA. |
| Backend tests | **Blocked / partial** | Phase 17 privacy unit tests: 2 passed in prior validation; broader backend pytest is running at time of writing. Async integration test previously stalled before its body on this Windows Python runtime's asyncio socket-pair setup. Backend owner · Critical | Get Linux/Python 3.12 CI green, including Phase 16–17 tests and worker tests; attach full output. |
| Real browser and mobile/accessibility journey | **Blocked** | No staging browser run, mobile/keyboard/a11y capture, email-verification/recovery journey, or auth-negative test evidence. QA owner · Critical | Exercise the checklist below in a real staging browser with synthetic authorized accounts; capture request IDs and sanitized evidence. |
| Real authorized inventory sample (target 200) | **Blocked** | No permitted live inventory sample, freshness/link/duplicate/budget/evidence-accuracy measurement. Data owner · High | Sample only permitted sources, document date, sampling method and limitations; do not use fixtures as live data. |
| Marketplace operations and demand | **Blocked** | Phase 17 contains plans and thresholds, not completed interviews, real projects, opted-in cohort, support rota, or exercised escalation. Ops owner · Critical | Record real client/freelancer validation and demand milestone, named operator coverage, appeals/support drills, and consented cohort. |
| Provider/legal payments | **Not applicable to contract-only beta** | No provider selected, no provider approval, no sandbox payment adapter, no payment ledger/reconciliation. Live marketplace funding/payout/refund remain disabled. Legal/compliance owner · Critical for any paid marketplace | Do not claim escrow/protection or collect marketplace payments; treat all payment E2E as blocked until a separate payment gate passes. |
| Monitoring/SLO, spend caps, log redaction, incident response | **Blocked** | Repository has a fail-closed uptime workflow for `UPTIME_URL` and incident/deployment runbooks; no configured alert evidence for source failures, worker lag, DB health, API error rate, duplicate digest, provider spend, or verified redaction. SRE/security · High | Configure and fire-test named alerts, budgets, redaction, incident disable and communication paths in staging. |
| Terms, privacy, deletion, support contact, status page | **Blocked** | Product pages exist; current legal review, data-request exercise, support mailbox ownership, status page, and retention schedule are not verified. Privacy/support owner · High | Review production-facing copy and test a deletion/data request and support report before any cohort. |

## Local checks recorded for this assessment

Commands run from the repository's `frontend` directory:

```powershell
npm run lint
npm run test
npm run build
& .\node_modules\.bin\tsc.cmd --noEmit
```

Commands for backend CI are defined in `.github/workflows/ci.yml` and run from `fastapi`:

```powershell
..\.venv\Scripts\python.exe -m compileall -q app
..\.venv\Scripts\python.exe -m pytest tests -q
```

The workflow additionally checks Alembic has exactly one head, runs worker tests if present, and checks the uptime script fails closed when `UPTIME_URL` is missing. The frontend workflow uses `npm ci`, `npm run lint`, `npm run test`, and `npm run build` on Node 22/Linux; run those exact commands on CI for the release ref. A local Windows result is useful debugging evidence, not a substitute for the configured Linux CI.

Observed for this assessment: frontend tests passed (22 files, 61 tests); TypeScript `tsc --noEmit` passed. `npm run lint` exits successfully with 0 errors and 73 warnings, primarily unused variables/imports and hook dependency warnings. The local frontend runtime is Node 26.13.1 while CI specifies Node 22; two production build attempts produced no further output for over 90 seconds and were interrupted. The full backend suite and a focused run of the new Phase 16–17 tests likewise produced no output within the available runtime and were interrupted; the local virtualenv is Python 3.14.10 while CI specifies Python 3.12, and the Windows Python launcher reports no managed interpreter installations. These build/full-suite results are **incomplete**, not passes or confirmed code failures. Alembic heads reported one head, `20261130_marketplace_operations_phase17`. Backend compile, OpenAPI schema generation, and Phase 17 metrics privacy tests passed in prior validation. `docker compose config --quiet` passed for the shell's default development Compose selection, but that selection is not evidence about production. Explicit `docker compose -f compose.yml config` failed closed without required environment values; with non-secret placeholder values it rendered marketplace defaults `false` / `private_preview`. Docker Desktop engine access is denied, so no local container health or inventory was available. No staging, deploy, migration application, provider charge/payout, or invite was performed.

**Credential handling incident:** an initial diagnostic ran without `-f compose.yml`; the shell's `COMPOSE_FILE` selected `compose.dev.yml`, and Compose rendered local environment values to tool output. Credential-shaped values were present. Treat any real credentials from that local configuration as exposed and rotate them (including provider/OAuth/API credentials, JWT signing secret, and database credentials as applicable); do not paste replacements into chat or this gate. This incident is separate from production and does not prove those credentials are live.

## Scope-specific staging browser checklist

Use a dedicated staging deployment and synthetic test users only. Never expose synthetic fixtures as live marketplace inventory.

1. Visit the actual Vercel preview and API staging origin; verify TLS, correct API base, exact CORS allowlist, and that callbacks return to staging. Confirm there is no production data or key reuse.
2. Register, verify email through a mail sandbox, sign in/out, recover access, complete onboarding, inspect profile/data controls, and confirm unauthenticated and cross-account requests are denied.
3. With marketplace flag off, verify native directory/projects/matching/contract routes show their disabled/private-preview behavior and cannot create offers or contracts. Verify contract capability response says `contract_only`, every payment capability false, and no client-facing escrow/protection promise appears.
4. In an isolated staging-only exercise after approval to enable the private-preview flag, test employer and freelancer onboarding, genuine project approval/expiry, mutual matching, free interest submissions/no paid rank, offer negotiation, both-party contract acknowledgment, milestone delivery/approval/change request, support report, appeal, and operator audit. Return the flag to off and verify new writes are blocked.
5. Exercise waitlist consent and opt-out, support access control, moderator/support/source-role separation, reason-required privileged changes, audit access logging, duplicate/spam report, source disable/re-enable, verification expiry, and emergency disable. Use synthetic accounts and capture request IDs.
6. Test source, LLM, mail/notification, billing, Redis and DB degradation independently in staging. Verify bounded retries, useful degraded UI, no infinite loading, no secret/PII leakage, no unbounded AI/provider spend, and clean recovery. Keep billing keys and marketplace payment provider credentials absent for a no-billing contract-only beta.
7. Check keyboard-only navigation, mobile viewport, focus/errors, labels/contrast, and core page accessibility. Capture screenshots and failed request IDs with personal data redacted.
8. For discovery surfaces included in the chosen cohort, also exercise hunt rules, shared inventory, rank/explanation, lead detail, Save/Skip, proposal/CRM, sandbox digest, financial calculator, and email/data controls. Keep this distinct from verified native marketplace hiring outcomes.

## Inventory and cohort evidence

For an authorized inventory sample, record source and permission, collection timestamp, sample selection method, sample size (target 200 where allowed), working-link rate, stale-date rate, duplicate rate, unknown-budget rate, attribution/source coverage, and evidence accuracy. Include failed links and abstentions in denominators. Do not report an unrun target as a measurement or substitute synthetic fixture precision for live-feed usefulness.

For the beta cohort, record opt-in and eligibility criteria, number of genuine independent hiring organizations and freelancers, demand milestone, project approval owner, response coverage, support escalation path, and acceptable failure thresholds. Phase 17's 10 client/20 freelancer interview targets and later goals of 20 organizations/100 opted-in freelancers are targets, not current counts. Example internal thresholds (90% working links, zero critical auth/data leak, no stuck loading) must be evaluated on a documented sample before acceptance.

## Cost and provider matrix

| Service / cost area | Current evidence | Beta treatment |
|---|---|---|
| Marketplace payment processor / FX / payout / refunds | No selected or approved provider; no provider transaction capability | Off; no marketplace charges, custody, payout, or escrow claim |
| SaaS subscription billing | Stripe integration and optional credentials exist; runtime account and cancellation/refund setup unknown | Keep credentials/price unset unless separately approved; test sandbox checkout, cancellation and refund before enabling |
| Search/source providers | SerpAPI, Tavily and other integrations are configurable; active credentials, quotas, terms and current cost are unverified | Enable only permitted sources; set and alert on provider spend caps; show source attribution and stale status |
| LLM providers | Multiple provider keys are configurable; live models, rates, budgets and timeout behavior are unverified | Keep optional; configure hard spending cap, bounded retries, usage telemetry and degraded fallback |
| Hosting/data/monitoring | Docs give an old rough VM estimate only; actual cloud, Vercel, storage, backup and monitoring invoices are unavailable | Collect current quotes/invoices and owner-approved monthly cap; don't present estimates as measured unit economics |
| Human support / verification / disputes | Staffing and loaded support cost not evidenced | Name coverage and price support time before expanding beyond a tightly capped pilot |

## Release and rollback rehearsal (not run)

These are the repository-supported commands to rehearse on a dedicated staging VM after actual topology is confirmed. They are **instructions, not executed actions**. Do not run against production as written without the release owner's explicit approval. `compose.yml` is the production Compose file: it exposes 80/443 for Caddy, binds API to loopback port 8002 by default, stores Postgres/Redis in named volumes, and runs `alembic upgrade head` automatically when the API starts. It is a single-VM topology, not rolling/blue-green; expect a brief API restart and rehearse downtime. Keep the existing services and port bindings intact.

```bash
# On the isolated staging VM, repo root; RELEASE_SHA must be a reviewed commit/tag.
git fetch --tags
git checkout --detach "$RELEASE_SHA"
git rev-parse HEAD
git status --short
docker compose config --quiet
docker compose build api worker beat

# Verify backup and restore on the isolated staging DB/clone before app rollout.
docker compose exec -T db pg_dump -U freelance -d freelance -Fc > "staging-pre-${RELEASE_SHA}.dump"
docker compose exec -T db pg_restore --list < "staging-pre-${RELEASE_SHA}.dump"

# On disposable clone only: API startup applies the Alembic head automatically.
docker compose up -d --no-deps api worker beat
docker compose ps
curl --fail --show-error https://STAGING_API_HOST/api/v1/health/live
curl --fail --show-error https://STAGING_API_HOST/api/v1/health/ready
docker compose logs --since=10m api worker beat

# Roll back application images/code only if migration remains backward compatible:
git checkout --detach "$PREVIOUS_RELEASE_SHA"
docker compose build api worker beat
docker compose up -d --no-deps api worker beat
curl --fail --show-error https://STAGING_API_HOST/api/v1/health/live
curl --fail --show-error https://STAGING_API_HOST/api/v1/health/ready
```

The dump listing command only validates archive readability; it does **not** prove restore. Restore that dump into a separate empty disposable database, compare expected table/row counts, and run the smoke journey before calling backup recovery passed. Do not use production dumps without approved sanitization/access controls. The rollback runbook prefers a forward fix; after a non-backward-compatible migration, restore only from a tested backup under separately approved incident procedures. Never downgrade/drop data by default.

For emergency marketplace disable in Compose, set `FEATURE_MARKETPLACE_ENABLED=false` and `MARKETPLACE_STATUS=disabled` in the approved environment and recreate only the API/worker/beat services after confirming the correct project and env file: `docker compose up -d --no-deps api worker beat`. This flag change is a control, not a substitute for support/incident response. The staging operator must prove that existing sessions cannot perform new native marketplace writes after shutdown. Payment functions remain code-disabled irrespective of this marketplace flag.

Frontend staging promotion is a separate Vercel preview-to-production action. Confirm the Vercel project root is `frontend`, `NEXT_PUBLIC_API_URL` points to staging for preview and the approved API for production, and Next build configuration is immutable for the release. No Vercel promotion or GCP VM command was run for this gate.

## Monitoring, owner handoff, and go/no-go rubric

Before a private pilot, name primary/backup release operator, incident commander, moderator, support agent, source operator, privacy contact, and escalation hours. Add tested alerts for API error/latency, DB and Redis readiness, worker/beat lag and queue age, failed source runs and freshness, duplicate digests, auth/security events, provider spend/budget (source/LLM), backup completion, and uptime. Define thresholds and a kill-switch owner. The repo's current uptime workflow checks live and readiness only; it does not establish these SLOs or spending caps.

### Scope release notes and known limitations

- Marketplace onboarding, projects, mutual matching, free interest submissions, offers, contract snapshots/milestones, operator queues, support reports, appeals, and consented waitlist are available in code behind existing role/feature controls.
- Production Compose now passes explicit marketplace-off/private-preview defaults; the Vercel install command now uses the lockfile with `npm ci`.
- Marketplace funding, protected/escrow claims, provider payouts/refunds, payment webhooks, reconciliation, and provider exception handling are unavailable. Contracts are not legally reviewed; contract evidence attachments are disabled pending secure storage and retention controls.
- Operations metrics are partial persisted-record snapshots; small cohorts are suppressed, some metrics are not instrumented, and not every event source has a test marker. Do not use them as verified customer/transaction or launch-readiness claims.
- No current staging deployment, opt-in pilot demand, support rota, current source-cost quote, provider approval, privacy/legal review, or beta feedback is evidenced.

### Pilot feedback and stop plan

For any later authorized private pilot, assign an owner to contact each consenting client and freelancer after a project decision and at the pilot midpoint/end. Ask the same short questions about relevance, time spent, trust, clarity of scope/acceptance, response time, and whether they would use the workflow again; capture consent, role, date, sample size, and anonymized notes. Offer an opt-out and deletion path. Review issues weekly with support/moderation and document the decision and owner. Pause intake immediately for any critical auth/privacy incident, unapproved payment claim/charge, no available support coverage, repeated false/duplicate listing, or uncontrolled provider spend; resume only after the incident owner records remediation and re-approval. These are proposed controls, not an active staffed process.

**GO** only for the exact verified scope/SHA after all Critical rows pass, CI/security review passes, staging rehearsal and backup restore pass, browser/security/accessibility and controlled cohort checks pass, and an authorized human explicitly approves. **CONDITIONAL GO** may cover an internal staging or tightly capped private no-payment pilot only when remaining risks are named, accepted by the release owner, flags and billing scope are explicit, and no Critical or legal/privacy/provider blocker applies. **NO GO** applies now: release identity is dirty/unpinned, CI isn't evidenced and lint fails, staging and restore are unverified, real-browser and demand evidence are absent, and operations/monitoring staffing is not established. Do not deploy, promote, or invite users from this document alone.

### Release record to complete

| Field | Value |
|---|---|
| Scope / cohort | Marketplace beta, contract-only, payments off |
| Release SHA/tag and image digest | Pending clean reviewed release |
| CI run / security review | Pending |
| Staging frontend/API origins and project IDs | Pending verification; record values in controlled release system, not this document if sensitive |
| Migration head / clone restore evidence | Head known locally; rehearsal pending |
| Browser evidence / request IDs | Pending |
| Inventory sample method and results | Pending authorized collection |
| Named owners / coverage / accepted thresholds | Pending human assignment |
| Decision and approving person/date | NO GO on current evidence; approval pending |
