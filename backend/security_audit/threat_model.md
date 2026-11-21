# Threat Model & Data-Flow Diagram (Phase 12)

**System**: Freelance Automation Platform (AGY Freelance Copilot)  
**Status**: Independent Launch-Blocking Security Audit  
**Date**: November 2026  
**Classification**: Internal Operational Security Document  
**Scope**: Frontend, API Gateway, Application Layer, Database, Task Queues, Source Adapters, LLM Providers, Payment/Billing Providers, Notification Dispatchers.

---

## 1. Executive Summary & Architecture Overview

The Freelance Automation Platform discovers freelance opportunities from distributed public sources, filters and scores them against user preferences, enables safe pipeline management, drafts proposals via an assistive AI copilot, calculates transparent net earnings, and provides user-controlled digest notifications.

Because the system ingests untrusted text from external web listings and interacts with external LLMs and payment gateways, **defense-in-depth and strict server-authoritative trust boundaries** are mandatory.

```
                      +---------------------------------------+
                      |          Client Web Browser           |
                      |   (Next.js 14 / React / Tailwind)     |
                      +---------------------------------------+
                                          |
                              HTTPS / WSS | [TB-1: Client-Ingress Boundary]
                                          v
                      +---------------------------------------+
                      |         FastAPI API Gateway           |
                      |  - Request ID & Structured Logging    |
                      |  - JWT Bearer Authentication          |
                      |  - IP/User Sliding Rate Limiters      |
                      |  - Security Headers (HSTS, CSP, etc.) |
                      |  - CORS Whitelisting                  |
                      +---------------------------------------+
                                          |
                       Internal In-Memory | [TB-2: Gateway-Service Boundary]
                                          v
                      +---------------------------------------+
                      |     Application / Service Layer       |
                      |  - Tenant Isolation Enforcement       |
                      |  - Server-Authoritative RBAC (Roles)  |
                      |  - Entitlement & Quota Reservation    |
                      |  - Neutrality Safeguards (Pro != Rank)|
                      +---------------------------------------+
                        /            |             \           \
                       /             |              \           \
      [TB-3: DB Boundary]    [TB-5: Queue]    [TB-7: LLM]  [TB-8: SaaS Webhooks]
                     /               |                \           \
                    v                v                 v           v
          +------------------+  +-----------+  +------------+  +-----------------+
          | PostgreSQL / DB  |  | Celery &  |  | OpenAI /   |  | Stripe / Resend |
          | Parameterized SQL|  | Redis     |  | Gemini API |  | HMAC Validation |
          | Tenant-scoped IDX|  | Outbox    |  | Sandboxed  |  | PII Redaction   |
          +------------------+  +-----------+  +------------+  +-----------------+
                                      |
                             [TB-6: Scraper]
                                      |
                                      v
                             +------------------+
                             | Untrusted Feeds  |
                             | Upwork, HN, etc. |
                             | SSRF-safe client |
                             +------------------+
```

---

## 2. Trust Boundaries & Data Flow Diagram (DFD)

### Trust Boundary 1: Client Web Browser $\to$ FastAPI Ingress
* **Data Flow**: User registration, login credentials, search queries, preference configurations, lead notes, financial inputs.
* **Threats**: Man-in-the-Middle (MitM), Cross-Site Scripting (XSS), Cross-Site Request Forgery (CSRF), credential stuffing, brute force.
* **Controls & Defenses**:
  - TLS 1.3 enforced with `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
  - HTTP-only, SameSite=Lax/Strict session cookies where applicable; standard Bearer JWT tokens in Authorization headers.
  - Strict Content-Security-Policy (CSP): `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; font-src 'self' data: https:; connect-src 'self'`.
  - Header hardening: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`.
  - Sliding-window Redis/in-memory rate limiter per IP and per user account to mitigate brute force.

### Trust Boundary 2: FastAPI Gateway $\to$ Service / Business Logic
* **Data Flow**: Deserialized Pydantic schemas, validated user contexts.
* **Threats**: Insecure Direct Object References (IDOR), privilege escalation, broken object level authorization (BOLA).
* **Controls & Defenses**:
  - Every protected route injects `user: Annotated[User, Depends(get_current_user)]`.
  - Service methods take explicit `user_id` parameter and explicitly query `WHERE user_id == current_user.id`.
  - User cannot pass an arbitrary `user_id` in path or body to access or mutate other users' entities (preferences, earnings, leads, copilot drafts, notification preferences).
  - Admin/moderator routes explicitly inject `Depends(get_current_active_superuser)`.

### Trust Boundary 3: Service Layer $\to$ Database (PostgreSQL / SQLite)
* **Data Flow**: SQL queries via SQLAlchemy async ORM.
* **Threats**: SQL Injection (SQLi), query denial of service (unindexed table scans), cross-tenant data leaks.
* **Controls & Defenses**:
  - 100% parameterized queries via SQLAlchemy 2.0 ORM; raw string concatenation forbidden.
  - Foreign key constraints with explicit cascaded or restricted deletes.
  - Compound indexes on multi-tenant tables: `(user_id, status)`, `(user_id, is_active)`, `(canonical_id)`, `(source_name, source_id)`.
  - Bounded pagination limits (`limit <= 100`, `Query(..., ge=1, le=100)`).

### Trust Boundary 4: Database Storage $\to$ Data at Rest & Encryption
* **Data Flow**: User passwords, API tokens, user earnings, notes.
* **Threats**: Credential leakage from database dumps, unencrypted sensitive PII.
* **Controls & Defenses**:
  - Password hashing using `Argon2id` / `bcrypt` with unique salt and high work factor.
  - **Zero Cardholder Data Policy**: Credit card numbers, CVVs, and raw payment methods are NEVER stored, processed, or logged; Stripe Checkout & Customer Portal handle all cardholder interactions.
  - Bank credentials and live banking credentials are strictly rejected (users enter high-level manual statement figures for fee calculations without storing bank account numbers).

### Trust Boundary 5: Service Layer $\to$ Asynchronous Queues (Celery / Redis)
* **Data Flow**: Background tasks, scheduled scrapers, digest notifications, email dispatch.
* **Threats**: Queue poisoning, task tampering, retry storms, duplicate processing.
* **Controls & Defenses**:
  - Redis connection authenticated with TLS and password.
  - Transactional outbox pattern: notification delivery records created with `pending` status before dispatch.
  - Idempotent task execution: jobs have unique deduplication keys `(event_type, recipient, channel, date)`.
  - Exponential backoff with bounded retries (max 3-5 retries); persistent failures routed to dead-letter queue (DLQ).

### Trust Boundary 6: Ingestion Engine $\to$ External Scrapers & Source Feeds
* **Data Flow**: HTTP responses from Upwork, Freelancer, RemoteOK, Hacker News, Reddit, ATS boards.
* **Threats**: Server-Side Request Forgery (SSRF), malicious payloads in RSS/HTML feeds, XML External Entity (XXE), oversized payload denial-of-service.
* **Controls & Defenses**:
  - Strict URL allowlisting for external fetching.
  - Private IP blocking: IP addresses resolving to `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254` (cloud metadata endpoints), or IPv6 loopbacks are blocked immediately prior to socket connection.
  - Response payload size ceiling: hard cutoff at 5MB per listing to prevent memory exhaustion.
  - Feed parsing using defused/standard parsers preventing entity expansion.

### Trust Boundary 7: Service Layer $\to$ AI Copilot & LLM Providers
* **Data Flow**: User profile prompts, job listing descriptions, AI generation requests.
* **Threats**: Indirect prompt injection, jailbreaks, tool manipulation / unauthorized tool action, data exfiltration, hallucinated claims.
* **Controls & Defenses**:
  - **Untrusted Listing Sanitization**: All external listing text passes through regex-based instruction sanitization (`_sanitize_listing_text`) neutralizing patterns like `ignore all previous instructions`, `system prompt`, `you are now`, `tool: exec`.
  - **Server-Authoritative Tool Permissions**: LLM CANNOT invoke arbitrary tools or write to the database. The system executes a predefined, fixed list of read-only context gatherers (`read_profile`, `read_job`, `read_lead`, `read_portfolio_summary`).
  - **Drafts Never Auto-Send**: Copilot generates previews only (`save_draft_preview`). Any outward action requires explicit, interactive user consent.
  - **Unverified Claims Scanner**: Generated proposals are scanned against known hallucination markers (`_FABRICATION_MARKERS`), warning the freelancer before submission.

### Trust Boundary 8: External SaaS $\to$ Inbound Webhooks & Dispatchers
* **Data Flow**: Stripe billing events, Resend email status callbacks.
* **Threats**: Webhook forgery, replay attacks, timestamp manipulation, PII leakage in notification metadata.
* **Controls & Defenses**:
  - Cryptographic HMAC-SHA256 signature verification on raw request payload prior to deserialization (`Stripe-Signature`).
  - Strict 300-second replay tolerance window (`abs(now - timestamp) <= 300`).
  - Database event deduplication: duplicate `event_id` is recorded and acknowledged idempotently with HTTP 200 without executing side effects.
  - Out-of-order state defense: older event timestamps cannot downgrade or overwrite newer subscription states.
  - Notification logs redact email addresses, phone numbers, and webhook tokens (`args_redacted`, `recipient_redacted`).

---

## 3. STRIDE Threat Analysis Matrix

| Element | Threat (STRIDE) | Specific Attack Vector | Mitigating Architecture & Implementation |
| :--- | :--- | :--- | :--- |
| **Authentication** | Spoofing | Forged JWT access token or stolen refresh token | High-entropy secret key, short-lived access tokens (15m), token blocklisting on logout, password hash verification with Argon2id. |
| **Pipeline & CRM** | Tampering | User A modifies notes, stages, or earnings of User B | Tenant isolation: SQL queries strictly parameterized with `where user_id = current_user.id`. IDOR negative tests verify 403/404. |
| **Billing Webhooks** | Repudiation | Attacker submits fake subscription renewal to gain Pro tier | HMAC-SHA256 signature validation with webhook secret, replay protection window (300s), duplicate event ID check. |
| **Financial Ledger** | Information Disclosure | Viewing another freelancer's hourly rate or earnings | Ledger records isolated by `user_id`; no aggregate public endpoints expose individual earnings. |
| **Search / Ingestion** | Denial of Service | Scraper flood or concurrent heavy matching queries | Per-user query rate limits, cached read endpoints (TTL cache on plans/templates), concurrency-safe DB pools. |
| **AI Copilot** | Elevation of Privilege | Untrusted job description directs LLM to execute shell/database command | Server-side execution only; LLM outputs text/JSON; tool list is hardcoded read-only; no shell or dynamic execution tools exist. |

---

## 4. User Consent, Data Retention & GDPR Deletion

1. **Consent Tracking**:
   - `UserConsent` model tracks explicit user agreement to Terms of Service, Privacy Policy, and Scraping/Digest preferences with timestamp, IP hash, and version.
2. **Report & Appeal Workflow**:
   - `ListingReport` system enables users to flag misleading, scam, or abusive listings.
   - Moderator queue (`/trust/moderation/queue`) requires active superuser status.
   - Freelancers can request corrections or appeal reports with audit logging.
3. **Data Retention & Right to be Forgotten (GDPR / CCPA)**:
   - Account deletion endpoint (`DELETE /users/me`) initiates a hard cascade of personal data:
     * User profile, credentials, and sessions revoked immediately.
     * User preferences, earnings entries, lead actions, notes, reminders, copilot drafts, and notification subscriptions permanently deleted.
     * Scraped public job listings are preserved (since they are public data), but disassociated from user interactions.
   - Data Export (`GET /users/me/export`): Freelancers can export all their personal data in a structured, machine-readable JSON format.

---

## 5. Security & Verification Audit Gate Checklist

- [x] **No Unresolved Critical/High Security Defects**: Architecture enforces strict least privilege, zero shell tools in LLM, and 100% tenant-scoped queries.
- [x] **No Real Production Charges or PII Leaks**: Sandbox mode enforced for all payment and notification providers.
- [x] **Server-Authoritative Validation**: Client-side validation is replicated and enforced strictly in FastAPI Pydantic models.
- [x] **SSRF Protection**: Private IP ranges blocked on all outbound fetching endpoints.
- [x] **Replay & Forgery Defense**: Cryptographic HMAC verification and 300s timestamp window for external webhooks.
