# Runbook — deployment rollback

## Before deploy

- Note image tags / commit SHA  
- Confirm migrations are additive; have down SQL or expand/backfill/contract plan  

## Rollback app only (no migration)

1. Redeploy previous image/tag (`cloudbuild` / compose pull previous).  
2. Verify `/health/live` and `/health/ready`.  
3. Smoke: sign-in + leads list.  

## Rollback after migration

1. Prefer forward-fix.  
2. If contract migration already ran, restore DB from pre-deploy backup on disposable clone, validate, then approve prod restore.  
3. Never run destructive SQL without explicit approval.

## Secrets

Rotate only via secret manager / env replace; restart api+worker+beat after rotation.
