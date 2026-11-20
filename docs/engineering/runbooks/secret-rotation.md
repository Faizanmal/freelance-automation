# Runbook — secret rotation

## Scope

JWT signing key, Stripe webhook secret, OAuth client secrets, Redis/DB URLs, hunter API keys.

## Steps

1. Generate new secret offline; store in secret manager / host env — **never commit**.  
2. For JWT: expect existing sessions to invalidate; announce or dual-publish only if a documented bridge exists (currently single-key).  
3. For Stripe webhook: update Dashboard + `STRIPE_WEBHOOK_SECRET` together; send test event.  
4. For OAuth: update provider console redirect URIs + client secret atomically.  
5. Restart `api`, `worker`, `beat`.  
6. Confirm `/health/ready` and one login + one webhook test.  
7. Revoke old credentials after verification window.

## Logging

Ensure rotation exercises do not print secret values. Request IDs are safe to share.
