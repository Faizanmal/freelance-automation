# Phase 09 — Reliable Alerts, Scheduled Digests and User-Controlled Automation

## Architectural Overview

Phase 09 establishes a production-grade, user-controlled notification and automation architecture that strictly preserves the **two independent clocks**:
1. **The Hunt Clock (Source Ingestion)**: Independent background scrapers running on regular schedules (`tasks.scrape_jobs` every 30m) that continuously populate the raw shared inventory (`JobRecord`).
2. **The Show Clock (Delivery Scheduling)**: Evaluates user local preferences on user-configured cadence, days, and local time (`tasks.process_lead_digests` every 15m), querying already-ingested inventory without running expensive per-user polling loops.

```
┌────────────────────────────────────────────────────────┐
│                      HUNT CLOCK                        │
│ Scrapers & Search Workers (SerpAPI, Tavily, HN, ATS)   │
└──────────────────────────┬─────────────────────────────┘
                           │ Continuous async ingest
                           ▼
┌────────────────────────────────────────────────────────┐
│               SHARED RAW INVENTORY                     │
│               Database (JobRecord)                     │
└──────────────────────────┬─────────────────────────────┘
                           │ Read-only filtered evaluation
                           ▼
┌────────────────────────────────────────────────────────┐
│                      SHOW CLOCK                        │
│   Celery Beat Periodic Task (Every 15 Minutes)         │
│   - IANA Timezone validation & Local time conversion   │
│   - DST gap / fold resiliency                          │
│   - Exclusions (UserLeadAction & DigestSentJob)        │
│   - Candidate fit, relevance & source diversity        │
│   - Stale/expired listing suppression                  │
│   - Meaningful empty-digest policy                     │
└──────────────────────────┬─────────────────────────────┘
                           │ Transactional Enqueue (dedup_key)
                           ▼
┌────────────────────────────────────────────────────────┐
│              TRANSACTIONAL OUTBOX                      │
│ - Dedup key: digest:{user_id}:{date}:{channel}         │
│ - Bounded retries (max 3) & Dead Letter Queue (DLQ)    │
│ - Cost recording ($0.0008/email, etc.)                 │
│ - Masked provider health observability                 │
└────────────┬─────────────────────────────┬─────────────┘
             │ Multi-Channel Dispatch      │ Webhook Feedback
             ▼                             ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│  Delivered Notifications │  │  Provider Webhook Events │
│  - In-App Inbox (unread) │  │  - Bounce / Complaint    │
│  - RFC 8058 HTML Email   │  │  - Auto-unsubscribe     │
│  - Slack / Webhook / TG  │  │  - Sender reputation     │
└──────────────────────────┘  └──────────────────────────┘
```

---

## 1. Notification Preference Model

The notification preferences model is persisted on `UserPreferences` and supported via dedicated REST APIs:
- **Channels**: `in_app`, `email`, `slack`, `telegram`, `discord`, `whatsapp`, `webhook` (Pro vs Free plan gated).
- **Cadence**: `realtime` (immediate alerts), `daily`, `weekly`, `biweekly`.
- **Timezone**: Strict **IANA identifier** (e.g. `America/New_York`, `Europe/London`, `UTC`), validated via Python `zoneinfo.ZoneInfo`. Invalid strings return 400 Bad Request.
- **Local Preferred Time & Days**: Local time string (`"09:00"`) and day array (`["mon", "tue", "wed", "thu", "fri"]`).
- **Quiet Hours**: `quiet_hours_enabled`, `quiet_hours_start` (`"22:00"`), `quiet_hours_end` (`"08:00"`). Supports overnight spans across midnight.
- **Filters & Minimum Relevance**: Keywords, exclude keywords, minimum budget, minimum hourly rate, match threshold (`match_threshold >= 0.35`).
- **Controls**: `is_paused` (pause without losing settings), `is_unsubscribed`, `unsubscribed_at`.
- **Empty Digest Policy**: `"suppress"` (default, zero noise) or `"send_empty_notification"` (helpful filter guidance).

---

## 2. DST Changes, Skipped/Ambiguous Times & Restart Idempotency

- **DST Spring Forward (Gap / Skipped Time)**: Clocks jump over target minutes (e.g. 01:59:59 -> 03:00:00 for a 02:30 target). `digest_scheduler.py` detects that the target local hour has arrived on today's calendar date and permits a safety catch-up window.
- **DST Fall Back (Ambiguous Time / Fold)**: When 01:00 to 01:59 repeats twice, single-send date verification ensures today's digest was already dispatched on user's current local date, guaranteeing zero duplicate sends.
- **Worker Restarts & Celery Retries**: Each digest delivery enqueues a transactional outbox record with a unique `dedup_key = f"digest:{user.id}:{local_calendar_date}:{channel}"`. Database unique constraints prevent duplicate execution.

---

## 3. Digest Selection from Ingested Inventory

`DigestSelector` selects leads strictly from already ingested data:
1. **Freshness & Active Inventory**: Query filters `is_expired is False` and `inventory_state == 'active'`.
2. **Exclusions**: User lead actions (`skip`, `save`, `pitched`, `won`) and excluded keywords are removed.
3. **Deduplication against Past Sends**: Jobs previously recorded in `DigestSentJob` for this user are excluded.
4. **Relevance Threshold**: Candidate match score must meet or exceed user threshold.
5. **Source Diversity Balancing**: Caps single-source monopolization to `ceil(cap / 2)` when multiple sources are available.
6. **Provenance & Details**: Honest provenance ("Source: RemoteOK"), concise why-matched reasoning, actual budget without inventing fake numbers or counts.

---

## 4. In-App Inbox & Accessible Email Templates

- **In-App Inbox**:
  - `GET /api/v1/notifications/inbox` (read/unread filtering, group keys, unread counts).
  - `POST /api/v1/notifications/inbox/{id}/read` (enforces strict cross-user ownership).
  - `POST /api/v1/notifications/inbox/read-all`.
  - `DELETE /api/v1/notifications/inbox/{id}` (archives notification).
- **Accessible HTML Email Templates**:
  - Responsive table and card layout meeting WCAG AA contrast standards.
  - Plain-text fallback for every email.
  - RFC 8058 compliant `List-Unsubscribe` and `List-Unsubscribe-Post` headers.
  - Visible instant unsubscribe and quiet hours adjustment links.
- **Immediate High-Fit Alerts**:
  - Ingested jobs scoring $\ge$ `immediate_alert_threshold` (default 0.85) trigger immediate alerts.
  - Gated by quiet hours suppression and user daily caps (`immediate_alert_cap_per_day`).

---

## 5. Transactional Outbox, Observability & Webhooks

- **Outbox Table (`notification_outbox`)**:
  - Unique index on `dedup_key`.
  - Bounded retries: max 3 attempts with exponential backoff.
  - State machine: `pending` $\rightarrow$ `sending` $\rightarrow$ `delivered` or `failed` $\rightarrow$ `dead_letter`.
  - Records delivery unit costs ($0.0008/email, $0.010/WhatsApp, etc.).
- **Provider Status Observability (`GET /api/v1/notifications/providers/status`)**:
  - Real-time aggregated statistics: delivered, failed, dead-letter, total estimated USD cost.
  - Masks and strips all recipient emails, tokens, and PII.
- **Webhook Ingestion (`POST /api/v1/notifications/webhook/{provider}`)**:
  - Authenticated via `X-Webhook-Secret`.
  - On bounce or spam complaint: automatically flags user `is_unsubscribed = True`, preserving domain and sender reputation.

---

## 6. Gate Verification Summary

All 17 automated gate scenarios verified in `fastapi/tests/test_notifications_digests_phase09.py`:
- `test_duplicate_scheduler_executes`: Idempotent deduplication on retry or restart.
- `test_bounded_retries_and_dead_letter_queue`: Max 3 retries before DLQ transition.
- `test_dst_spring_forward_skipped_time`: Spring-forward gap catch-up.
- `test_dst_fall_back_ambiguous_time_no_duplicate`: Fall-back ambiguous hour idempotency.
- `test_iana_timezone_validation`: Rejection of invalid timezone identifiers.
- `test_quiet_hours_overnight_and_daytime`: Suppression during overnight and daytime quiet spans.
- `test_unsubscribed_and_paused_users_suppressed`: Paused & unsubscribed users skipped.
- `test_expired_and_stale_listings_excluded_from_digest`: Prunes expired listings before send.
- `test_source_outage_does_not_crash_digest`: Scraper failure resilience.
- `test_source_diversity_balancing`: Multi-source diversity enforcement.
- `test_unconfigured_provider_honesty`: Never fakes success on unconfigured providers.
- `test_immediate_alerts_respect_threshold_and_caps`: Daily cap and threshold enforcement.
- `test_calculate_next_send_preview`: Local and UTC scheduling accuracy.
- `test_cross_user_inbox_access_prevention`: 404 on cross-user notification manipulation.
- `test_webhook_bounce_unsubscribes_user`: Reputation protection on provider bounce events.
- `test_unverified_user_cannot_send_test_digest`: 403 when unverified users request test digests.
- `test_provider_status_observability_no_pii`: Privacy-preserving operational metrics.
