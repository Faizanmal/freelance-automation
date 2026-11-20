# Phase 06 — Evidence-based opportunity intelligence and scam-risk assistance

## Intent

Help people decide whether a lead deserves their time. **Never declare a person or company fraudulent from an LLM inference.** Keep relevance, freshness, hiring intent, and risk as **separate** channels.

## What shipped

| Area | Location |
|------|----------|
| Structured extraction | `backend/application/services/trust/project_extraction.py` |
| Evidence registry | `backend/application/services/trust/evidence.py` |
| Risk indicators | `backend/application/services/trust/risk_indicators.py` |
| SSRF-safe fetch | `backend/application/services/trust/safe_fetch.py` |
| Employer panel | `backend/application/services/trust/employer_research.py` |
| Due-diligence checklist | `backend/application/services/trust/due_diligence.py` |
| Compose service | `backend/application/services/trust/service.py` |
| Reports / mod queue | `listing_reports.py` + `database/models/listing_report.py` |
| API | `fastapi/app/api/v1/trust.py` |
| Findings attach | `lead_findings._trust_summary` |
| Desk UI | Leads aside due-diligence + Flag concern |
| Ops UI | Admin moderation queue |

### Extraction
- Deliverables, skills, work type, deadlines, budget structure, constraints, must-haves, location, apply procedure, fee, ambiguous/missing.
- Field evidence pointers; explicit unknowns.
- LLM path schema-validated; **fraud/scam fields rejected**; deterministic fallback on outage.
- Stores provider / model / prompt / extraction version / cost (no extra PII).

### Evidence
- Opportunity/company scope; signal type; factual observation; URL; excerpt; timestamp; confidence; expiry; visibility; reviewer status.
- Semantics: **verified / observed / reported / unknown**.
- No universal reputation number.

### Risk
- Transparent indicators: payment-before-work, sensitive data, unpaid tests, spam/exposure language, domain mismatch (soft), unclear budget, unknown employer (**abstain**, not scam).
- Never infer from protected traits / nationality / geography alone.
- `verdict: null`, `automatic_exclusion: false`; high → human review queue.

### Employer research
- Public identity/domain/hiring page/timestamps from listing + allowlisted fetch.
- No private contacts; no mass personal enrichment.
- SSRF: scheme, allowlist, DNS/IP public check, redirect re-validation, size/time limits, sanitized text.

### Reporting
- User report → open queue → moderator outcome + correction request.
- External platform report path when known.
- PII redaction; duplicate/reason uniqueness; rate limit; dismiss_abuse outcome.

## Evaluation

| Item | Value |
|------|-------|
| Corpus | `fastapi/tests/fixtures/trust_eval/` — **43** labeled examples |
| Splits | train 28 / holdout 15 |
| Labels | legitimate, ambiguous, suspicious, adversarial, missing_field |
| Holdout high-risk precision | ≥ 0.75 (asserted) |
| Holdout high-risk recall | ≥ 0.75 (asserted) |
| Legitimate high-risk FP | 0 (asserted) |
| Work-type accuracy (deterministic) | ≥ 0.70 (asserted) |

**Dataset limits:** synthetic human-authored fixtures — **not** production scam statistics. Do **not** claim scam-prevention efficacy from this set alone.

**Known failure cases:** domain-mismatch soft FP on third-party boards; non-English budget may stay unknown; LLM outage → deterministic only; unknown company ≠ scam (by design); no private company registry verification.

## Gate

| Gate | Status |
|------|--------|
| Every displayed factual claim has provenance or explicit unknown | Pass |
| No automatic exclusion solely from a model | Pass |
| High-risk native listings → human review | Pass (queue + `requires_human_review`) |
| No sensitive data exposed in reports | Pass (sanitize) |
| Users can report/correct | Pass |
| Quality metrics published with limits | Pass (this doc) |

## Tests

```bash
cd fastapi && .venv/Scripts/python -m unittest tests.test_trust_intelligence -v
```

## Non-claims

This phase assists due diligence. It does **not** assert that Signal Desk prevents scams, verifies employers, or detects all fraud.
