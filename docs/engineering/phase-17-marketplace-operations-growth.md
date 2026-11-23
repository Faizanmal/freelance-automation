# Phase 17 — Marketplace operations, quality and sustainable launch growth

## Current state and truthful reporting

The repository has separate external-listing and native-project flows, listing reports, project moderation/appeals, verification claims, audit events, contract disputes, and an administrative dashboard. Phase 17 adds scoped operator roles, a consent-based support queue and waitlist, durable/audited source controls, a role-specific operations view, reason-required moderation and restriction controls, and an operations queue read model. Queue payloads omit reporter identities and dispute evidence. Payment exceptions report unavailable because Phase 16 is contract-only.

No real prospective customers, freelancers, organizations, interviews, project demand, acquisition costs, transaction volume, or readiness are evidenced by this code change. Do not expose generated/synthetic data as marketplace activity. `is_sample` projects remain excluded from pilot counts and outcomes.

## Operator roles and workflows

Roles are assigned by a superuser through the protected operations role endpoint and can be revoked. The three scoped roles are `marketplace_moderator`, `support_agent`, and `source_operator`; superusers retain access. Marketplace moderation and appeal queues are distinct from support/disputes and source takedown. Private evidence and contact fields are not in queue summaries. User restriction/verification changes and moderation/source actions require a written reason and create audit events. Source kill-switch records persist in the audit table and are restored on service startup; enable/disable remains reversible.

Workflow ownership:

- **Marketplace moderator:** native project moderation/appeals, listing reports including duplicate/spam reports, verification claims/expiry, and audit review.
- **Support agent:** support cases and contract dispute triage. Human review only; no automated legal/financial outcomes. Contract report text is PII-scrubbed and detail access is audited. Evidence attachments are rejected because secure object storage, malware scanning, and retention controls are not configured; that remains a pilot blocker if evidence submission is required.
- **Source operator:** source health and reversible source disable/enable with reason. Takedown decisions should follow source terms/legal review and the runbook.
- **Payment exceptions:** absent/disabled until provider integration exists. Never create fake exception rows.

Support submissions are authenticated, PII-scrubbed, capped at five open cases per user, and their status is visible only to the requester and scoped operators. Waitlist entry requires explicit waitlist consent; optional concierge contact consent is separate. Users can opt out. New entries are capped at two per account per month; duplicate joins are idempotent, and rejoining after opt-out requires support. No incentive, referral-credit, or paid-ranking mechanism is shipped.

The existing organization/project invitation workflow is the invite path. Referral attribution is intentionally not enabled until identity, self-referral, collusion, and reversal controls are implemented. No outreach emails are sent by the waitlist endpoints.

## Emergency disable and operating coverage

For immediate native marketplace shutdown, set `FEATURE_MARKETPLACE_ENABLED=false` and `MARKETPLACE_STATUS=disabled` in the deployment environment, stop new invitation/offer writes at the edge if needed, and page the named incident owner. For a single source, the source operator disables it from `/ops`; the reason is persisted to audit and restored on restart. To recover, the incident owner documents impact and remediation, re-enables the source/feature explicitly, and watches the audit/access logs. Follow the existing incident playbook for severity, credential compromise, data exposure, and post-incident review.

The service has no staffed support rota verified by this phase. Before a pilot, name primary and backup moderators, support agent, source operator, incident commander, and escalation contact; publish coverage hours and response targets. Do not promise response SLAs until people accept and exercise that schedule. Payment dispute staffing remains blocked with payment integration.

## Outcome metrics and instrumentation contract

Metrics must be computed from server-side controlled events or persisted workflow records. Each report must include its observation window, numerator, denominator, sample size, cohort, and whether records are verified or estimated. Exclude samples/test users and sample projects from production reporting. Suppress small cohorts (minimum ten distinct people or organizations) in aggregate views. External apply clicks and confirmed applications are separate outcomes.

The moderator-only `/api/v1/ops/metrics` endpoint is intentionally a partial persisted-record snapshot (`mode=persisted_records_only`), not a launch dashboard. It reports the available project abandonment, first-shortlist timing, offer hiring, repeat hiring, external-application confirmation, confirmed listing complaint, and contract dispute metrics; it marks all other definitions as `not_instrumented`. Ratios with fewer than ten distinct cohort members are suppressed. Values are not independently verified transactions, and the endpoint does not yet provide controlled QA-event exclusion for every underlying record type; review cohort semantics and test-data filtering before using it for a launch decision.

| Metric | Definition | Current data readiness |
|---|---|---|
| Time to first qualified lead | Median project submit → first hard-filter-passing candidate surfaced to the client; denominator is submitted, non-sample projects with a recorded candidate event | Match scores and project lifecycle exist; client-view exposure timestamp needs instrumentation |
| Time to shortlist | Median project submit → first shortlist record; n is eligible non-sample projects | Derivable from project creation/status histories and shortlist rows; verify timestamp consistency before reporting |
| Client review minutes | Active review minutes / projects reviewed, excluding idle gaps | Not instrumented; must not be inferred from wall-clock elapsed time |
| Freelancer time per qualified application/contract | Reported active minutes / qualified submitted applications or activated contracts; show both denominators | Not instrumented for native marketplace; add opt-in timer/event source before use |
| Response rate | Invitations with response / delivered invitations; n is delivered invitations | Invitation workflow records response status; delivery confirmation is not yet a reliable denominator |
| Hiring rate | Accepted offers / offers finalized as accepted, declined, superseded, or expired; report counts and the superseded/expired treatment separately | Offer records exist; finalized denominator semantics need review before publishing |
| Abandoned-job rate | Submitted non-sample projects expired/closed without a hire / all submitted non-sample projects reaching an outcome | Project lifecycle exists; define cancellation/reopen cohort handling before activation |
| Verified listing coverage | Active external listings with independently checked source/authenticity evidence / active external listings with source metadata | Listing trust evidence exists; controlled verification denominator is incomplete |
| Authenticity complaints | Confirmed authenticity complaints / distinct active listings; also show complaint count and reviewed count | Listing reports and human outcomes exist; map outcomes and deduplicate listing subjects |
| Dispute rate | Contracts with a filed dispute / bilaterally acknowledged active contracts; always show n | Contract and dispute records exist; no payment dispute is implied |
| Repeat hiring | Organizations with 2+ accepted offers / organizations with at least 1 accepted offer | Accepted-offer data exists; exclude sample organizations/projects |
| Newcomer organic visibility | Qualified newcomer shortlist impressions / all qualified organic shortlist impressions; sponsored/paid inputs are excluded | Ranking has a newcomer component; impression logging/consent is incomplete |
| User acquisition cost | Attributable cash spend + valued founder acquisition hours / new verified, opted-in users by persona | No complete acquisition-cost ledger; report unavailable until tracked |
| Gross margin | Marketplace revenue − provider, verification, support, refund, dispute, fraud, and infrastructure variable cost, divided by revenue | No native marketplace revenue; unavailable |
| Effective payment cost | Processor + FX + payout + refund/dispute loss + KYC + variable support cost / gross provider-confirmed transaction value | No provider transactions; unavailable |

No charts should render an unavailable metric as zero. Discovery SaaS activity is not native marketplace liquidity. Instrument controlled QA records with an explicit test marker, verify event transitions and denominators against them, then exclude them from production queries.

## Consent-based acquisition and pilot plan

**Initial niche:** AI/software/automation projects. Use founder-led interviews, opt-in communities, inbound pages, and consented partnerships. Do not scrape private contact details, automate unsolicited outreach, or offer rewards for listings or ranking. Reuse native client project creation/invitations, public talent-directory opt-in, and the new consented waitlist. Concierge follow-up is permitted only where the user separately opted in; preserve unsubscribe/opt-out immediately.

**Discovery interview target (not completed):** at least 10 prospective independent hiring clients and 20 freelancers. Continue interviews until both groups have repeated evidence around current workflow, spend, trust concerns, time-to-hire, platform expectations, and support needs. Do not pitch hypothetical payment protection as existing.

**Client script (20–30 minutes):**

1. Tell me about the last software/automation contractor you hired. What triggered the search?
2. Where did you find them? What did it cost in money and staff time?
3. How did you verify fit, scope, rate, and availability? What failed or caused delay?
4. How were deliverables, changes, acceptance, invoice, tax, and payment handled?
5. What would make you trust a manually curated shortlist? What evidence would disqualify it?
6. What support response and escalation would you expect if work or communication went wrong?
7. Would you opt in to a small concierge pilot? What project could you share, and what must remain private?

**Freelancer script (20–30 minutes):**

1. How did your last three paid software/automation contracts arrive?
2. How much unpaid proposal, screening, or negotiation time did each require?
3. What evidence would you share to demonstrate fit, and what should stay private?
4. What scope, revision, acceptance, cancellation, currency, invoice, tax, and payment terms do you need before starting?
5. What dispute support would be useful, and what should the platform never decide for you?
6. What profile visibility and outreach consent would you choose?
7. Would you opt in to a small pilot or waitlist? What would make you leave?

Record consent, role, date, anonymized notes, and permission for follow-up separately. Avoid collecting unnecessary personal/sensitive data. Findings are qualitative until coded with sample sizes and contradictory cases included.

**Pilot sequence:** first validate demand through interviews and concierge briefs. Proposed first supply-invite gate: at least five qualified, budgeted, client-approved briefs from at least three independent organizations, with clear scope, hiring owner, and decision deadline. These are go/no-go thresholds, not current counts. Then manually invite only qualified, explicitly opted-in freelancers for each brief; never pad a shortlist. Later recruitment goals are 20 genuine hiring organizations and 100 qualified opted-in freelancers, explicitly goals rather than claims. Keep discovery SaaS useful even when native project count is zero.

## Unit economics model

Model client success fee options at 3%, 5%, and 8% of completed gross contract value; keep the freelancer platform fee at 0% in the base case. These are alternatives for scenario analysis, not approved pricing. Compare each party’s total effective price, including processor fees, FX, tax/invoice handling, payout costs, verification, support, refunds, disputes, fraud loss, and time cost. Do not shift costs into a hidden freelancer spread.

For scenario `s`:

`contribution_s = completed_GMV × client_fee_rate − processor_and_FX − verification − refunds_and_dispute_loss − support_minutes × loaded_support_rate − variable_infrastructure − acquisition_cost`

`break_even_completed_contracts = fixed_monthly_cost / contribution_per_completed_contract` when contribution is positive; otherwise break-even is not achieved.

Stress-test low volume with high support minutes and high dispute/refund loss; also model zero completed contracts and 100% failed/abandoned pilot projects. Costs with no vendor quote or observed time study must be input as named assumptions, not presented as measured. Payment costs remain unavailable until provider selection/approval. Acquisition cost must include founder hours with an explicit shadow hourly rate. Keep native applications free in every scenario.

## Go/no-go rubric

Proceed only when all are true:

- Interview targets are complete and evidence indicates repeated, specific client demand and freelancer willingness, without extrapolating beyond the sample.
- Proposed first demand milestone is met with real, independently verified organizations and eligible projects; no samples count.
- Moderator/support/source roles are assigned narrowly, synthetic-user exercises pass 403/allowed-action checks, and every privileged change has a reason plus audit record.
- Duplicate/spam review, project appeal, account restriction reversal, verification expiry, source disable/re-enable, support escalation, and incident disable procedures have been exercised.
- Privacy-safe metrics are reconciled against controlled server-side events with denominators/sample sizes; unavailable fields remain unavailable.
- Unit economics remain positive under documented low-volume/high-dispute assumptions, or the team explicitly chooses an iteration plan with a capped budget.
- Support staffing, response coverage, retention, safety escalation, and emergency owner are named and scheduled.

External blockers, not software defects: qualified legal/compliance and tax advice, actual entity/jurisdictions, provider eligibility/approval and payment support, local privacy/retention interpretation, and human recruiting/interview execution. Phase 16 still blocks payment integration and all live charge/payout flows. No customer counts or launch-readiness claim is authorized by this plan.
