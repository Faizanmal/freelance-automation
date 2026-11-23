# Public presentation readiness review

**Decision: NOT READY for open public signup, billing, or production promotion.** Code-side fixes below improve the preview and make failure states safer, but several external facts are not verified in this workspace. This review does not authorize deployment or invitations.

## Fixed in this review

- Production frontend no longer silently sends API requests to a visitor's localhost when `NEXT_PUBLIC_API_URL` is missing. Non-production builds retain a local development default.
- Canonical URLs now use the configured application origin or the Vercel deployment origin. Preview/local builds default to noindex, and only a configured public origin produces sitemap entries. Authenticated/product pages receive `X-Robots-Tag: noindex` and stay out of the sitemap.
- Added a branded social share card and route-specific titles, descriptions, and canonicals for the primary public pages and skill listings.
- Content Security Policy now limits `connect-src` to the configured API origin and Plausible; `unsafe-eval` is limited to development. Added camera/microphone/geolocation denial. Existing inline-script allowance remains and needs a nonce-based follow-up review.
- Client error reporting no longer transmits exception text, stack traces, or route paths. It sends only a fixed error category; API rejects extra fields.
- Pipeline and earnings CSV exports now use authenticated bearer-token downloads with a refresh retry. The previous links sent no bearer token; pipeline URLs also repeated the API prefix in production.
- Public status page reports API reachability only, not internal database/worker readiness. Pricing no longer promises “free forever” or an absolute ranking guarantee, and the displayed price comes from the plan response.
- Subscription checkout now requires explicit `STRIPE_CHECKOUT_ENABLED`; production additionally requires `STRIPE_LIVE_CHARGES_ENABLED`. Both are false in the production example. Marketplace payments remain independently disabled.
- Privacy copy now separates browser site analytics from consented product events and describes the currently instrumented save/skip/external-click actions.

## Release blockers requiring external evidence or owner decisions

| Severity | Gate | Evidence still required |
|---|---|---|
| Critical | Operator identity and jurisdictions | Confirm legal contracting entity, registration jurisdiction, service regions, and qualified legal review of Terms, Privacy, cancellation/refund and data-rights copy. Current copy explicitly identifies this as incomplete. |
| Critical | Privacy and retention | Confirm actual provider list, processing locations/transfers, retention periods, deletion completion across backups/logs/analytics, and support process. Product-event retention automation is not implemented. |
| Critical | Production account and security | Verify domain/DNS/TLS, Vercel project, API origin, CORS and OAuth callbacks; run security review and rotate the credentials implicated by the earlier local-config diagnostic. Rotation has not been verified here. |
| Critical | User support and incident response | Verify the public support address is owned and monitored; name staffed support, privacy, moderation, on-call and incident owners with response hours and an exercised disable/rollback path. |
| High | Listing legitimacy and usefulness | Verify source licenses/terms for each enabled adapter and run a dated, authorized sample of up to 200 fresh listings for relevance, dead links, staleness, duplicates, budget uncertainty and attribution. Do not describe the preview pool as verified until measured. |
| High | Billing | Confirm account/provider eligibility, price/currency/tax, cancellation, refunds, invoicing, dispute and support procedures. Keep checkout flags off until the separate approval and sandbox/reconciliation gate passes. |
| High | Accessibility and browser quality | Run real-browser staging journeys with keyboard, screen reader, mobile layouts, auth, recovery, deletion, export, error/failure paths, and consent behavior. |
| High | CI and release integrity | Commit/review a clean release SHA; pass Node 22/Linux build, backend Python 3.12/Linux full tests, dependency/security review, migration/restore rehearsal, staging smoke and monitoring checks. |
| High | Secret incident | Rotate any applicable API/provider/OAuth/JWT/database credentials from the exposed local configuration and review logs/access. Never paste replacement values into this repository's public materials or chat. |

## Local verification

- Frontend tests: 22 files / 61 tests passed after the API default and export fixes.
- TypeScript: `npx tsc --noEmit` passed.
- Focused Phase 19 tests: 6 passed, including payload privacy and the production billing default gate.
- Workspace ESLint: 0 errors, 73 warnings. Targeted modified UI/API files have 0 errors; one pre-existing navigation warning remains in `api.ts`.
- Production build is **blocked locally**: after clearing the ignored `.next` cache and retrying with `npx next build --webpack`, Next.js 16.3.4 failed during compilation with `EPERM: operation not permitted, mkdir 'frontend/.next/server/app/freelance-jobs/[skill]'`. Earlier Turbopack build also stalled. The build environment is Node 26; the release gate expects a supported Node 22/Linux CI build. A Next warning also reports custom Cache-Control headers on `/_next/image` and `/_next/static`; review those headers against the deployment/CDN setup.
- The combined billing backend test process did not complete during this review. Treat full billing test evidence as incomplete until CI confirms it.
- No DB migration, staging deployment, production setting change, charge, payout, or user invitation was performed.
- A local visual browser review was attempted, but the in-app browser could not reach the local preview and Windows browser control stopped at its URL-safety check. No visual browser journey is claimed as passed.

## Public-facing copy and configuration

The Terms page lists `support@signaldesk.com`; ownership, mailbox delivery and legal operator identity have not been verified. The production example identifies a Vercel origin, but actual Vercel, DNS, TLS, CORS and provider settings were not inspected. Missing frontend API configuration now fails visibly instead of silently targeting localhost.

**Next release scope:** a no-payment, invite-only discovery preview after legal/operator identity, support coverage, source review, fresh inventory sampling, credential rotation, staging restoration and CI evidence are supplied and explicitly approved by the release owner. Marketplace/payment flags remain off.
