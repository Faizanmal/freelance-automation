# Phase 15 — Fair Two-Sided Marketplace & Mutual-Interest Hiring

## Executive Summary

Phase 15 implements a fair, meritocratic two-sided marketplace foundation that eliminates pay-to-apply barriers, bidding wars, and artificial scarcity. It introduces an organic two-sided matching engine safeguarded by an **architectural firewall**, bilateral structured negotiation, concurrency-guarded offer finalization, authenticated participant messaging with contact masking, and privacy-safe evaluation metrics.

In compliance with the Phase 15 gate requirements:
1. **Private Preview Feature Flag**: Enforced via `FEATURE_MARKETPLACE_ENABLED=False` and `MARKETPLACE_STATUS="private_preview"` until Gate 18.
2. **Zero Pay-to-Apply**: Applications and expressions of interest carry a fixed $0.00 platform fee.
3. **No Market Liquidity Claims**: All test benchmarks and synthetic evaluations are labeled `mode="simulated"` and explicitly disclaim live production market liquidity.

---

## 1. Architectural Firewall & Organic Match Ranking

### Strict Entitlement Isolation
To prevent the emergence of pay-to-win dynamics, entitlement, subscription, pro status, or ad credit fields are strictly quarantined from the organic ranking vector.

```python
FORBIDDEN_FIREWALL_FIELDS = {
    "entitlement",
    "subscription",
    "tier",
    "plan",
    "credits",
    "boost_credits",
    "is_paid",
    "paid_tier",
    "ad_spend",
    "sponsored",
}
```

The `TalentFeatureVector` enforces this at the model level via a validator. If any prohibited attribute is detected, it raises a `ValueError` immediately.

### Matching Vector & Weights
Organic candidate ranking calculates match quality using five observable dimensions:
$$\text{Score} = 0.45 \times \text{Skill} + 0.25 \times \text{Budget} + 0.15 \times \text{Availability} + 0.15 \times \text{WorkPref} + \text{NewcomerBoost}$$

1. **Skill Evidence Match ($45\%$)**: Based on verified skill claims and portfolio artifacts matching the project's required skills.
2. **Budget / Rate Compatibility ($25\%$)**: Evaluates rate overlap between freelancer minimum/maximum and project budget range without punishing lower rates.
3. **Availability & Capacity ($15\%$)**: Evaluates weekly hours required vs freelancer available capacity, confirming availability freshness.
4. **Work Preference Compatibility ($15\%$)**: Aligns remote vs hybrid/onsite preferences.
5. **Equitable Newcomer Rotation Boost ($+6\%$)**: High-potential candidates with $\le 3$ years experience receive an equitable rotation boost to ensure fair exposure without uncalibrated score inflation.

### Configurable Small Shortlist
- The system returns a focused shortlist (default 3–5 candidates).
- If fewer qualified candidates exist, only genuine matches are returned; the shortlist is never padded with false filler.
- Clients can request an expanded shortlist by providing a reason code, which is recorded in the audit trail.

---

## 2. Mutual Interest & Freelancer Safeguards

1. **Zero Connect / Pay-to-Apply Fees**:
   - Platform fee is hardcoded to \$0.00.
   - Eliminates speculative financial barriers for job seekers.
2. **Anti-Spam & Rate Controls**:
   - Active application limit: Max 5 active applications concurrently per freelancer.
   - Rolling rate limit: Max 3 applications per rolling 24-hour period.
   - Transparent error messages without monetary penalization.
3. **No Unpaid Speculative Deliverables**:
   - Expressions of interest require a structured pitch and links to existing portfolio artifacts.
   - Clients cannot demand custom unpaid work or test deliverables prior to a funded contract.
4. **Graceful Withdrawal & Decline**:
   - Freelancers can decline invitations or withdraw pending applications at any time.
   - Declining or withdrawing incurs zero negative reputation decay.

---

## 3. Concurrency-Guarded Bilateral Negotiation & Offers

### Offer Lifecycle
```
draft → pending_review → counter_proposed → accepted / declined / expired / superseded
```

### Bilateral Terms & Negotiation Assistant
- `NegotiationAssistant.draft_milestones`: Generates structured milestone proposals, delivery schedules, and scope boundaries based on agreed rates.
- Offers maintain full versioning (`version`, `revision_id`, `created_at`, `audit_trail`).

### Concurrency Guard Architecture
To prevent double-hiring, race conditions, or conflicting acceptances:
1. When an offer is accepted via `/api/v1/matching/offers/{offer_id}/accept`:
   - An atomic status verification checks `project.status != "offered_hired"`.
   - If the position is already filled, a `ConflictError` (`409 Conflict`) is immediately raised.
   - The accepted offer transitions to `accepted`, and the parent project transitions to `offered_hired`.
   - All other pending offers associated with this project are automatically transitioned to `superseded`.
2. Any subsequent acceptance attempt on a superseded offer immediately returns `409 Conflict`.

---

## 4. Authenticated Participant Messaging & Privacy

1. **Participant Authorization**:
   - Only verified client org members and the targeted candidate can read or post messages.
   - Strangers or unauthenticated users receive `403 Forbidden`.
2. **Contact Details Masking**:
   - Pre-offer messages are scanned with regex for raw telephone numbers and email addresses.
   - Detected contact information is masked (e.g. `[contact info masked until offer accepted]`) to prevent off-platform bypass scams and preserve dispute recourse.
3. **Attachment Safety**:
   - Maximum file size: $10\text{ MB}$.
   - Permitted extensions: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.zip`, `.txt`, `.md`, `.json`, `.csv`.
   - SHA-256 integrity hash computed and stored for every attachment.
4. **Abuse Reporting & Participant Blocking**:
   - Either party can report harassment, off-platform steering, or non-compliant demands.
   - Optional counterpart blocking prevents further messages while flagging the conversation for staff review.

---

## 5. Privacy-Safe Evaluation Metrics & Benchmarks

The `/api/v1/matching/metrics` endpoint provides auditable operational metrics partitioned by execution mode:
- `time_spent_by_each_side_sec`: Median drafting and review time.
- `relevant_candidate_rate`: Proportion of shortlisted candidates advancing to interview or offer ($\ge 0.60$).
- `response_latency_hours`: Time from client invitation to freelancer response.
- `offer_acceptance_rate`: Proportion of finalized offers accepted without dispute.
- `newcomer_inclusion_rate`: Proportion of shortlists featuring qualified newcomer rotation.

### Synthetic Data Liquidity Disclaimer
Every metric payload returned in simulated testing mode carries the mandatory legal notice:
> **"SIMULATED / TEST MODE: Metrics derived from synthetic test scenarios do not guarantee market liquidity or response rates in live production environments."**
