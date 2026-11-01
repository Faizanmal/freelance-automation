# Signal Desk UI/UX Transformation

Implementation notes for the premium SaaS redesign of the Next.js frontend.

## Summary

Signal Desk moved from a marketing-style top-nav editorial layout (forest/lime glass cards) to a production SaaS shell:

- Slate / zinc surfaces with a single electric blue accent
- Authenticated **sidebar product shell** (collapsible, mobile drawer)
- Logged-out **marketing header** preserved for acquisition pages
- Shared design tokens, UI primitives, empty/loading states, and toasts
- Desk, Leads, Hunt Rules, Pricing, Auth, and Account polished without mock data or API contract changes

## Pages redesigned

| Route | Changes |
|-------|---------|
| `/` Desk | Greeting, KPI cards from real findings/jobs, best matches, digest card, discovery status, empty states |
| `/leads` | Opportunity cards, match score UI, filters (all/new/high/saved/skipped), search, detail panel, Save/Skip optimistic update |
| `/preferences` | Sectioned Hunt Rules + Digest (show clock vs hunt clock), Billing, Security tabs restyled |
| `/pricing` | Plan comparison cards with real `/billing/plans` data |
| `/auth` | Cleaner sign-in card + Account Settings when logged in |
| Shell | Sidebar nav: Workspace / Management / Account |

## New reusable components

- `src/lib/cn.ts`
- `src/components/nav-config.ts`
- `src/components/app-shell.tsx`
- `src/components/ui/badge.tsx`
- `src/components/ui/skeleton.tsx`
- `src/components/ui/empty-state.tsx`
- `src/components/ui/match-score.tsx`
- `src/components/ui/page-header.tsx`
- `src/components/ui/toast.tsx`
- Updated `button.tsx`, `card.tsx`, `theme-toggle.tsx`, `account-settings.tsx`, `activation-checklist.tsx`

## Design tokens

Defined in `frontend/src/app/globals.css`:

- `--bg`, `--surface`, `--border`, `--text*`, `--accent`, `--success`, `--warning`, `--danger`
- Legacy aliases `--signal`, `--paper`, `--fog`, `--mute`, `--ember` kept for gradual migration
- Light + dark via `data-theme` (next-themes)

## Functionality preserved

- JWT auth (`signal_desk_token`)
- Hunt Rules CRUD, digest schedule, Save/Skip
- Scrape / refresh inventory, findings ranking
- Draft bid drawer + `confirm: true` apply
- Billing checkout / portal / Activate Pro (dev)
- 2FA, account delete, onboarding wizard, cookie consent
- Nav contracts: public Desk/Pricing/Leads/Account; auth Hunt Rules; no Sources/Findings/Matches in main nav

## Backend / API

No backend changes. Frontend continues to call existing FastAPI routes.

## Dependencies

No new packages. Reused `lucide-react`, `framer-motion`, `next-themes`, `clsx`, `tailwind-merge`.

## Known issues / follow-ups

- Some secondary pages (`/jobs`, `/sources`, `/help`, `/admin`, auth subpages) still use older surface styles; they inherit the new shell/tokens but are not fully rewritten.
- Password change and profile edit UIs are documented as unsupported where the API does not expose them.
- Pipeline nav is omitted (no backend pipeline feature).
- Match scores are labeled as estimates, not verified facts.
- Prefer further filter server-side when findings pagination expands beyond the current limit of 10.

## Remaining recommendations

1. Add React Query / SWR for request dedupe and cache.
2. Introduce `loading.tsx` / `error.tsx` route boundaries.
3. Expand Vitest coverage for sidebar collapse and lead filters.
4. Complete light-theme pass on security/onboarding/cookie banner.
5. Consider a command palette once search APIs support global query.
