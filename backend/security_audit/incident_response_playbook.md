# Security Incident Response Playbook & Operational Runbook (Phase 12)

**Classification**: Confidential / Operations  
**Platform**: AGY Freelance Automation  
**Effective Date**: November 2026  
**Review Cadence**: Semi-annual or post-incident  

---

## 1. Incident Severity Classification & Escalation Matrix

| Severity Level | Definition | Target First Response | Target Remediation | Examples |
| :--- | :--- | :--- | :--- | :--- |
| **P1 — Critical** | Active system compromise, user data exfiltration, remote code execution (RCE), billing breach, or complete service outage. | **15 minutes** | **< 4 hours** | Stolen database credentials, SSRF accessing cloud metadata, unauthenticated IDOR leaking financial data, forged webhook bypassing payments. |
| **P2 — High** | Partial service degradation, authentication bypass under specific conditions, broken rate limiter allowing abuse, unvalidated prompt injection leading to biased drafts. | **1 hour** | **< 12 hours** | Scraping queue lockup, slow LLM cascading failure, non-admin able to read moderation queue, email delivery failure. |
| **P3 — Medium** | Isolated functional defect, non-exploitable disclosure of low-risk metadata, transient webhook signature verification error, minor UI regression. | **4 hours** | **< 48 hours** | Inaccurate fee calculation on obscure currency, missing CSP header on static error page, transient Redis connection error. |
| **P4 — Low** | Cosmetic flaw, minor performance deviation under heavy synthetic load, documentation discrepancy, non-blocking warning. | **24 hours** | **Next release cycle** | Minor rounding discrepancy on historical FX conversion, log formatting noise. |

---

## 2. Emergency Response Protocols

### Playbook A: Compromised Secret / API Key Leak
1. **Identify & Isolate**:
   - Determine which secret was exposed (e.g. `JWT_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `OPENAI_API_KEY`, `DATABASE_URL`).
   - If `JWT_SECRET_KEY` is compromised, immediately trigger token revocation by incrementing `TOKEN_VERSION` or flushing active token blocks, requiring re-authentication.
2. **Rotate Credentials**:
   - Generate fresh cryptographically secure 256-bit secret: `openssl rand -hex 32`.
   - Update production environment secrets store (AWS Secrets Manager, GCP Secret Manager, or environment vault).
   - Invalidate the compromised API key in the provider console (OpenAI, Stripe, Resend).
3. **Audit Access Logs**:
   - Query `fastapi` structured access logs filtering by `X-Request-Id` and `request_id` to inspect operations performed using the compromised secret.
   - Validate whether unauthorized data modifications or export events occurred.
4. **Post-Incident Review**:
   - File incident post-mortem with root cause analysis (RCA) and preventive safeguards (e.g. pre-commit git secret scanners).

---

### Playbook B: Prompt Injection / Rogue Agent Attempt
1. **Quarantine Listing & User Context**:
   - Flag the offending job listing in the database: `UPDATE jobs SET is_expired = TRUE, expired_reason = 'security_quarantine' WHERE id = :job_id`.
   - The platform architecture strictly disallows dynamic LLM tool execution; copilot tools are limited to hardcoded read-only queries (`read_job`, `read_profile`, `read_lead`).
2. **Review Extracted Patterns**:
   - Check the listing text against `_INJECTION_PATTERNS` in `backend/application/services/copilot.py`.
   - If an evasive injection pattern was observed, add the new signature to regex patterns:
     ```python
     re.compile(r"new_adversarial_pattern_here", re.IGNORECASE)
     ```
3. **Verify Draft Isolation**:
   - Verify that no proposals were dispatched externally (`CopilotDraft` never auto-sends; proposals remain strictly preview drafts in the user's private workspace).

---

### Playbook C: Webhook Replay / Forgery Attack
1. **Signature Verification Audit**:
   - Inbound Stripe webhooks must pass `stripe.Webhook.construct_event` with HMAC-SHA256 signature and 300-second timestamp tolerance window.
   - Forged or expired requests are immediately rejected with HTTP 400.
2. **Idempotency Guard**:
   - If an attacker repeatedly sends a previously recorded legitimate webhook, the system queries `billing_webhook_events`. If `event_id` exists, it logs the duplicate and returns HTTP 200 without reprocessing or incrementing quotas.
3. **Attacker Mitigation**:
   - Rate limit offending IP addresses at reverse proxy / Cloudflare edge.

---

### Playbook D: Database Corruption, Migration Failure & Rollback Runbook
1. **Stop Mutation Traffic**:
   - Switch application to read-only mode or temporary maintenance page.
2. **Assess Database Health**:
   - Check point-in-time recovery (PITR) availability and recent automated snapshots.
3. **Rehearse & Execute Restore**:
   - In test/staging (or temporary replica), test restoring snapshot:
     ```bash
     pg_restore -h localhost -U postgres -d freelance_restore_test backup.dump
     ```
   - Verify table row counts on critical tables (`users`, `user_preferences`, `user_earnings`, `quota_reservations`).
4. **Migration Rollback**:
   - If an Alembic migration introduced a breaking change:
     ```bash
     alembic downgrade -1
     ```
   - Inspect `database/core/schema_patch.py` to ensure backward-compatible column addition without destructive drops.
5. **Resume Traffic & Monitor**:
   - Verify system health via `/health` and `/health/ready` endpoints.
   - Monitor error rates and p95 latency for 30 minutes following restoration.

---

## 3. Data Breach Notification & Regulatory Protocol (GDPR / CCPA)

1. **Breach Determination**:
   - If an incident involves confirmed unauthorized access to personal identifiable information (PII) or user earnings:
2. **Containment within 1 Hour**:
   - Terminate affected user sessions, revoke compromised tokens, and block exploited attack vector.
3. **Regulatory Notification (Within 72 Hours)**:
   - In accordance with GDPR Article 33 and relevant data protection authorities, submit formal breach notification detailing the nature of the breach, affected user categories, and mitigation steps taken.
4. **User Communication**:
   - Transparently notify affected freelancers without undue delay, advising on password resets and presenting data audit logs.

---

## 4. Service Identities & Principle of Least Privilege

- **FastAPI Application Process**:
  - Runs under unprivileged system user (`appuser`).
  - No write access to operating system binary paths.
- **Database User**:
  - Has `SELECT`, `INSERT`, `UPDATE`, `DELETE` on platform tables.
  - No `SUPERUSER` privileges; cannot alter database cluster configuration or access foreign data wrappers.
- **Background Worker**:
  - Read-write access to Redis task queue and PostgreSQL application database.
  - No external administrative capabilities.
- **LLM Integrations**:
  - API keys scoped strictly to text generation endpoints; no access to organizational settings or fine-tuning datasets.
