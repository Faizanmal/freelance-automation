# Phase 03 — Identity, onboarding, privacy

## Scope

Harden auth (OAuth linking, anti-enumeration, refresh rotation, logout revoke), privacy center, onboarding recovery, roles/visibility defaults. No prod deploy.

## Implemented

| Item | Status |
|------|--------|
| OAuth will not merge into **unverified** local emails | Done — `AccountLinkError` → 409 |
| Register anti-enumeration (no 409 “already registered”) | Done — `RegisterResponse.created` |
| Refresh tokens + `/auth/refresh` + HttpOnly `sd_refresh` cookie | Done (access still Bearer for SPA) |
| Logout revokes access (+ refresh cookie) from Account Settings | Done |
| Roles `account_role` + `profile_visibility` (default private) | Done + Alembic `20261120_identity_privacy` |
| Audit events + consent records | Done |
| Privacy center UI `/privacy/center` | Done |
| Session expired page `/auth/session-expired` | Done |
| Onboarding step persistence; no silent complete on save fail | Done |
| Export from Account + Privacy center | Done |

## Blocked / partial

| Item | Notes |
|------|--------|
| Full HttpOnly-only access tokens | Cross-origin SPA; Bearer access kept; refresh cookie + body rotation |
| Browser E2E with real test inbox | Needs SMTP/Resend sandbox + Playwright CI; covered by API unit/integration instead |
| Client/staff product surfaces | Role field + `require_roles`; hiring client UX still future |
| Retention automation jobs | Documented behavior; no automated PII TTL purge yet |

## Verification

```bash
cd fastapi && python -m pytest tests/test_identity_phase03.py tests/test_google_auth.py tests/test_github_auth.py tests/test_auth_verify.py tests/test_qa_flows.py -q
```

## Next

Wire orphan Celery beat carefully; source-registry docs; Playwright smoke with mail catcher when secrets available.
