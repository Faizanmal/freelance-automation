# Phase 16 — Contracts, milestones, transparent payments and dispute support

## Shipped foundation: contract-only mode

`/api/v1/contracts/capabilities` reports `mode=contract_only` and every payment capability as unsupported. Funding, checkout, account onboarding, holds, release, payout, refund, webhook verification, and reconciliation are disabled. The contract API never represents a provider redirect as payment confirmation and never handles or stores card or identity documents.

An authenticated participant can create one contract from an accepted Phase 15 offer. The captured snapshot records the offer version, parties, project, scope, contract type, currency, amount, and milestone terms. The snapshot is separate from the offer and is not rewritten by negotiation. Both the client organization and freelancer must acknowledge it before the contract becomes active. Legal template suitability and enforceability have not been reviewed.

Milestone workflow supports draft, ready, in progress, submitted, changes requested, approved, canceled, and disputed. Payment states are rejected because no provider capability is configured. Delivery review is role-limited: only the freelancer submits and only a client organization member approves or requests changes. Either party may file a report. Reports are queued as requiring human review; the API does not decide legal or financial outcomes.

Milestone transitions are `draft → ready → in_progress → submitted → (changes_requested → submitted)* → approved`. Cancellation is allowed before approval; a report can move an active or submitted milestone to disputed. Provider-dependent states `funding_pending`, `provider_confirmed_funded`, `payout_pending`, and `paid` are not reachable in contract-only mode.

Change orders retain a separate terms snapshot and require acknowledgment by both parties. They do not mutate the original contract snapshot. Either party may request termination; the other party must acknowledge before the contract becomes terminated. Contract, acknowledgment, milestone, change-order, and dispute events are append-only through the API. Dispute corrections are appended as separate immutable addenda. Evidence attachments are rejected until access-controlled object storage, malware scanning, retention, and audited reviewer access are configured; report text is PII-scrubbed.

Amounts in new change orders are exact decimal strings with explicit matching currency. The inherited offer schema stores amounts as floating point; migration to exact minor-unit or decimal offer values is still required before production financial use. `/api/v1/contracts/quote` returns an illustrative 3% client platform fee hypothesis and a 0% freelancer fee target; processor, FX, and tax amounts are marked unavailable. The quote expires after ten minutes, is not a payment authorization, and makes no promise of a protected payment, guaranteed exchange rate, or escrow.

## Provider adapter and financial state

No provider has been selected or verified. There is no provider adapter implementation, transaction ledger, webhook endpoint, reconciliation job, or operator exception queue. When provider research is authorized, an adapter must explicitly report supported/unsupported capabilities for hosted checkout, connected account onboarding, authorized hold/funding where the marketplace product and account qualify, release/transfer/payout, refund, signed webhook verification, and reconciliation. An absent capability must remain disabled; no simulated provider may be represented as production.

The future provider transaction lifecycle must be independent of contract/milestone state: `created → checkout_pending → provider_pending → provider_confirmed` or `failed`; confirmed movements may then enter `refund_pending → partially_refunded/refunded`, `payout_pending → paid/returned`, or `chargeback_open → chargeback_won/chargeback_lost`. Reconciliation is separate: `unmatched → matched`, or `exception_open → under_review → resolved`; unresolved mismatches remain in an operator queue. This lifecycle is design-only and is not implemented without a verified provider.

If an adapter is later approved, retain separate business contract/milestone state and provider transaction state. Record only provider-confirmed movements in a balanced internal accounting journal; do not custody customer funds. Webhook processing must verify signatures, persist an append-only event log, deduplicate/replay-protect by provider event ID and idempotency key, handle out-of-order delivery, retry safely, dead-letter failures, reconcile provider statements, and route mismatches to human operators. Client-supplied amount or recipient is never authoritative. A frontend success redirect alone must never mark a transaction paid.

## Required reviews before live payment development or launch

The following are **not verified** and block live activation:

- Actual legal business entity, operating locations, and target jurisdictions.
- Current provider marketplace eligibility for that entity, including Indian account restrictions, cross-border settlement, supported currencies, and connected-account requirements; written provider approval and current provider documentation.
- Qualified legal/accounting review of contract templates, tax collection/reporting, invoicing, platform fee treatment, refunds, disputes, sanctions-screening responsibilities, KYC/KYB obligations, and privacy/data-retention duties.
- Provider allocation of KYC/KYB, sanctions screening, chargeback, refund, and dispute responsibilities; hosted identity/payment flows preferred, with no raw card or ID storage.
- Support staffing, escalation coverage, evidence access controls, response deadlines, retention/deletion policy, and documented operational runbooks.
- Fee disclosure design showing gross contract value, any client platform fee hypothesis separately, freelancer platform fee target (0%), processor/FX/tax estimates and payer, confirmed amount/rate where available, and quote expiration. Never add hidden spread or imply a guaranteed rate.

## Failure and acceptance scenarios still required for a provider sandbox

Before enabling sandbox provider actions, build and demonstrate accepted offer → contract → test funding confirmation → delivery → approval → test payout → reconciliation, plus separate refund and dispute flows. Cover duplicate webhook, replay, out-of-order events, partial refund, failed and returned payout, currency mismatch, chargeback, zero/negative amount, client amount/recipient tampering, and reconciliation mismatch. No production charge or payout is authorized by this phase.

## Launch gate

Live payment feature flags must default off. Launch remains blocked until qualified reviews, provider approval and eligibility, sandbox end-to-end acceptance, failure tests, operational runbooks, audit/retention controls, and explicit product approval are recorded. Contract-only mode is the only supported mode in this release.
