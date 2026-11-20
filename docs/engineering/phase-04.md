# Phase 04 — UX, interaction design, accessibility

## Scope

Coherent freelancer workspace on the existing Fraunces/Manrope + CSS-variable system. No stock metrics, no invented testimonials, no decorative dashboard chrome.

## Delivered

| Area | Change |
|------|--------|
| Tokens | Quieter backgrounds; fit/trust/fresh tones; spacing scale; skip-link |
| A11y | Skip link → `#main-content`; meters with roles; reduced-motion preserved; emoji status badges removed |
| Homepage | Outcome-first hero; discovery vs marketplace; fee transparency; FAQ; Start free primary CTA |
| SEO | `metadataBase`, canonical, `sitemap.ts`, `robots.ts` (private paths disallowed) |
| Shell | Role-aware nav; Alerts; marketplace feature-flagged; Admin for staff/superuser |
| Desk | Hunt Rules plain-language preview; capacity sketch (not earnings promise) |
| Leads | Fit/trust/fresh meters; Save/Skip undo toast |
| Gallery | `/design-system` (noindex) with synthetic fixtures |
| Tests | Skip link, meters, nav filter unit tests |

## Gate notes

| Check | Status |
|-------|--------|
| 360/768/1440 | Layout uses responsive grids; manual browser pass recommended |
| Keyboard skip + focus | Skip link + `:focus-visible` |
| Automated axe | Not fully wired (no axe CI dep); unit roles/names covered |
| Usability timings | **Simulated walkthrough only** — not live user study |
| Screenshots | Not captured this session (no browser automation run) |

## Design rationale

- Preserve existing brand fonts and blue accent; avoid purple/cream AI clichés and fake chart walls.
- Separate fit vs trust vs freshness to prevent false precision.
- Marketplace remains off until `NEXT_PUBLIC_NATIVE_MARKETPLACE=true`.

## Commands

```bash
cd frontend && npm test -- tests/components/skip-link.test.tsx tests/components/lead-signal-meters.test.tsx tests/lib/nav-config.test.ts
```

## Next

Wire axe in CI; Playwright viewport snapshots; optional command palette when it shortens measured journeys.
