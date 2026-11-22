# Phase 13 — Verified Talent and Employer Network (Marketplace Foundation)

## Executive Summary & Architectural Overview

Phase 13 establishes the **verified talent and employer network foundation** as an additive, privacy-first, identity-reusing layer on top of SignalDesk. In accordance with release gate principles, native marketplace capabilities are **strictly feature-flagged** (`FEATURE_MARKETPLACE_ENABLED=False`, `MARKETPLACE_STATUS="private_preview"`) and kept private until **Gate 18**.

Rather than assuming buyer demand and opening an uncalibrated public marketplace, Phase 13 focuses on:
1. **Initial Proposed Segment**: AI / Software / Automation Services.
2. **Strict Identity Reuse**: Utilizing existing authentication (`User` model) with zero duplicate identity records.
3. **Private-by-Default Architecture**: Talent profiles and artifacts are strictly private until explicit multi-point opt-in consent is provided.
4. **Objective Multi-Level Verification**: Distinguishing user claims from independently verified evidence (GitHub contributions, corporate domain DNS, organization representative roles). No direct government ID storage.
5. **Calibrated Both-Side Reputation**: Driven by observable platform interactions with time decay and sample size indicators (sample size < 3 flags insufficient data rather than negative history). Zero universal single-score distortion.
6. **Buyer Acquisition Validation Plan**: Systematic roadmap to validate buyer demand through curated employer cohorts and search interest analysis prior to Gate 18.

---

## 1. Domain Data Models

All Phase 13 domain models are additive and mapped in `database/models/network.py`.

```
┌────────────────────────────────────────────────────────┐
│                   User (users table)                   │
│   account_role: freelancer | client | staff            │
│   profile_visibility: private | public                 │
└──────────────┬───────────────────────────┬─────────────┘
               │ 1:1                       │ 1:N
               ▼                           ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│  TalentProfile               │ │  EmployerOrg                 │
│  - headline, bio, segment    │ │  - name, slug, org_domain    │
│  - years_experience          │ │  - domain_verified           │
│  - is_published, status      │ │  - verification_status       │
│  - is_sample (demo isolated) │ │  - owner_id                  │
└──────┬───────┬───────┬───────┘ └──────┬───────────────┬───────┘
       │       │       │                │               │
       │       │       │ 1:1            │ 1:N           │ 1:N
       │       │       ▼                ▼               ▼
       │       │  ┌────────────────┐ ┌─────────────┐ ┌─────────────┐
       │       │  │ListingConsent  │ │OrgMembership│ │OrgSeatLog   │
       │       │  │- opt_in_dir    │ │- role       │ │- action     │
       │       │  │- allow_contact │ │- seat_status│ │- actor_id   │
       │       │  │- search_index  │ │- token      │ │- audit info │
       │       │  └────────────────┘ └─────────────┘ └─────────────┘
       │       │
       │ 1:N   │ 1:N
       ▼       ▼
┌────────────┐ ┌────────────────────┐
│TalentSkill │ │PortfolioArtifact   │
│- skill_name│ │- title, url        │
│- category  │ │- contribution_role │
│- status    │ │  (owner/contrib)   │
└────────────┘ └────────────────────┘
```

### Table Definitions

1. **`talent_profiles` (`TalentProfile`)**:
   - `id`: UUID Primary Key.
   - `user_id`: Foreign Key (`users.id`, unique, cascade delete).
   - `headline`: String(256), professional summary.
   - `bio`: Text, optional overview.
   - `primary_segment`: String(64), default `"ai_software_automation"`.
   - `years_experience`: Float, professional tenure.
   - `location_display`: String(128), general location / timezone (e.g. `"Remote (UTC+1)"`).
   - `is_published`: Boolean, default `False`.
   - `is_draft`: Boolean, default `True`.
   - `is_sample`: Boolean, default `False` (isolated demo profiles).
   - `status`: String(32), default `"private"` (`draft`, `private`, `active`, `suspended`, `archived`).

2. **`talent_skills` (`TalentSkill`)**:
   - `id`: UUID Primary Key.
   - `profile_id`: Foreign Key (`talent_profiles.id`, cascade delete).
   - `skill_name`: String(128).
   - `category`: String(64), default `"software"`.
   - `years_of_experience`: Float.
   - `verification_status`: String(32), default `"unverified"` (`unverified`, `claimed`, `evidence_submitted`, `verified`, `rejected`).

3. **`portfolio_artifacts` (`PortfolioArtifact`)**:
   - `id`: UUID Primary Key.
   - `profile_id`: Foreign Key (`talent_profiles.id`, cascade delete).
   - `title`: String(256).
   - `description`: Text.
   - `artifact_type`: String(64), default `"github_repo"` (`github_repo`, `live_deployment`, `case_study`, `code_sample`).
   - `url`: String(512).
   - `contribution_role`: String(64), default `"contributor"` (`owner`, `core_contributor`, `contributor`, `lead_architect`). *Ownership is never assumed merely from repository URL; explicit role contribution declaration is enforced.*
   - `verification_status`: String(32), default `"unverified"`.

4. **`talent_availabilities` (`WorkAvailability`)**:
   - `id`: UUID Primary Key.
   - `profile_id`: Foreign Key (`talent_profiles.id`, unique, cascade delete).
   - `status`: String(32), default `"available"` (`available`, `partially_available`, `busy`, `unavailable`).
   - `hours_per_week`: Integer, default 40.
   - `available_from`: DateTime(timezone=True).
   - `expires_at`: DateTime(timezone=True), required. Clear availability expiration date policy (defaults to 30 days; auto-expires in directory if past date).

5. **`talent_rates` (`RatePreference`)**:
   - `id`: UUID Primary Key.
   - `profile_id`: Foreign Key (`talent_profiles.id`, unique, cascade delete).
   - `min_rate`: Float, non-negative.
   - `max_rate`: Float, optional upper bound.
   - `currency`: String(8), default `"USD"`.
   - `rate_type`: String(32), default `"hourly"` (`hourly`, `fixed`, `retainer`).

6. **`talent_listing_consents` (`PublicListingConsent`)**:
   - `id`: UUID Primary Key.
   - `profile_id`: Foreign Key (`talent_profiles.id`, unique, cascade delete).
   - `opt_in_directory`: Boolean, default `False`. Private by default.
   - `allow_platform_contact`: Boolean, default `False`. Contact enabled only when opted in.
   - `search_indexing_consent`: Boolean, default `False`. Emits `X-Robots-Tag: noindex, nofollow` when `False`.
   - `consented_at`: DateTime(timezone=True), recorded timestamp.

7. **`employer_organizations` (`EmployerOrg`)**:
   - `id`: UUID Primary Key.
   - `name`: String(256).
   - `slug`: String(128), unique.
   - `website`: String(256), optional.
   - `industry`: String(128), default `"technology"`.
   - `org_domain`: String(128), corporate domain.
   - `domain_verified`: Boolean, default `False`.
   - `verification_status`: String(32), default `"unverified"`.
   - `owner_id`: Foreign Key (`users.id`).
   - `is_sample`: Boolean, default `False`.

8. **`employer_memberships` (`OrgMembership`)**:
   - `id`: UUID Primary Key.
   - `org_id`: Foreign Key (`employer_organizations.id`, cascade delete).
   - `user_id`: Foreign Key (`users.id`, nullable).
   - `email`: String(256).
   - `role`: String(32), default `"member"` (`owner`, `admin`, `hiring_manager`, `member`).
   - `seat_status`: String(32), default `"invited"` (`invited`, `active`, `suspended`, `revoked`).
   - `invitation_token`: String(128), unique.
   - `invited_by_id`: Foreign Key (`users.id`).
   - `invited_at`, `accepted_at`, `revoked_at`.

9. **`employer_seat_audit_logs` (`OrgSeatLog`)**:
   - `id`: UUID Primary Key.
   - `org_id`: Foreign Key (`employer_organizations.id`, cascade delete).
   - `actor_id`: Foreign Key (`users.id`).
   - `target_user_id`: Foreign Key (`users.id`).
   - `action`: String(64) (`organization_created`, `invite_sent`, `invite_accepted`, `role_changed`, `seat_revoked`, `seat_suspended`).
   - `ip_address`: String(64), `user_agent`: String(256), `details`: JSON.

10. **`verification_claims` (`VerificationClaim`)**:
    - `id`: UUID Primary Key.
    - `user_id`: Foreign Key (`users.id`, cascade delete).
    - `profile_id`: Foreign Key (`talent_profiles.id`, optional).
    - `claim_type`: String(64) (`email_domain`, `org_representative`, `github_contribution`, `portfolio_artifact`, `skill_assessment`).
    - `level`: Integer, default 1 (Level 1: email/domain; Level 2: org representative; Level 3: portfolio/skill).
    - `claim_source`: String(32) (`user_claimed`, `independently_verified`).
    - `status`: String(32) (`pending`, `under_review`, `verified`, `rejected`, `revoked`).

11. **`verification_evidences` (`VerificationEvidence`)**:
    - `id`: UUID Primary Key.
    - `claim_id`: Foreign Key (`verification_claims.id`, cascade delete).
    - `provider`: String(64) (`sandbox_github`, `sandbox_dns`, `approved_idp_sandbox`).
    - `evidence_type`: String(64) (`commit_history`, `domain_txt_record`, `oauth_grant`).
    - `provider_reference_id`: String(256) (Never collect government ID directly; stores only provider references and status).
    - `evidence_payload`: JSON (sanitized commits, granted scopes, minimal scopes).
    - `is_valid`: Boolean, default `True`.
    - `submitted_at`, `corrected_at`, `correction_notes`.

12. **`marketplace_reports_and_appeals` (`MarketplaceReport`)**:
    - `id`: UUID Primary Key.
    - `reporter_user_id`: Foreign Key (`users.id`, cascade delete).
    - `target_type`: String(32) (`talent_profile`, `org_profile`, `verification_claim`, `evidence`).
    - `target_id`: String(36).
    - `report_type`: String(32) (`report`, `appeal`).
    - `reason`: String(128), `details`: Text.
    - `status`: String(32) (`opened`, `in_review`, `resolved`, `dismissed`).
    - `resolution_notes`: Text, `resolved_by_id`: Foreign Key (`users.id`).

13. **`reputation_activities` (`ReputationActivity`)**:
    - `id`: UUID Primary Key.
    - `user_id`: Foreign Key (`users.id`, cascade delete).
    - `counterparty_id`: Foreign Key (`users.id`, optional).
    - `entity_type`: String(32) (`freelancer`, `employer`).
    - `event_type`: String(64) (`response_recorded`, `delivery_confirmed`, `repeat_hire`, `paid_transaction`, `dispute_resolved`).
    - `transaction_amount`: Float, optional.
    - `response_time_seconds`: Integer, optional.
    - `event_timestamp`: DateTime(timezone=True).
    - `is_verified_event`: Boolean, default `True`.
    - `is_suspicious`: Boolean, default `False` (moderation & manipulation check).
    - `decay_weight`: Float, default 1.0.

---

## 2. REST API Reference

All endpoints are registered under `/api/v1/network` and require authentication.

### Freelancer Profile & Privacy
- `GET /api/v1/network/profile`
  - Returns currently authenticated freelancer's full profile, skills, artifacts, rates, availability, and privacy consent.
- `PUT /api/v1/network/profile`
  - Updates headline, bio, segment, experience, and location display.
- `POST /api/v1/network/profile/skills`
  - Adds or updates a talent skill. Status defaults to `"unverified"`.
- `DELETE /api/v1/network/profile/skills/{skill_id}`
  - Removes a skill. Returns 404 on invalid ID / IDOR attempt.
- `POST /api/v1/network/profile/artifacts`
  - Adds or updates a portfolio artifact with declared `contribution_role`.
- `DELETE /api/v1/network/profile/artifacts/{artifact_id}`
  - Removes an artifact.
- `PUT /api/v1/network/profile/availability`
  - Updates status (`available`, `busy`, etc.), hours per week, and required `expires_at` date.
- `PUT /api/v1/network/profile/rates`
  - Updates min/max rates, currency, and rate type.
- `PUT /api/v1/network/profile/consent`
  - Configures `opt_in_directory`, `allow_platform_contact`, and `search_indexing_consent`. Opting out immediately sets profile visibility to private.
- `POST /api/v1/network/profile/publish`
  - Publishes profile. Fails (400) if `opt_in_directory` consent is False or headline is missing.
- `POST /api/v1/network/profile/unpublish`
  - Unpublishes profile; immediately hides profile from public directory.
- `GET /api/v1/network/profile/preview`
  - Generates the exact sanitized public view seen by external viewers. Redacts email, phone, and internal identifiers.

### Talent Discovery Directory
- `GET /api/v1/network/directory`
  - Queries public opt-in talent directory.
  - Query parameters: `skills`, `work_type`, `min_rate`, `max_rate`, `currency`, `availability`, `min_level`, `primary_segment`, `include_sample`, `limit`, `offset`.
  - Enforces:
    - `is_published == True`
    - `opt_in_directory == True`
    - `status == "active"`
    - `expires_at > now`
    - `is_sample == False` (unless explicitly requested)
  - Headers: Emits `X-Robots-Tag: noindex, nofollow`.
- `GET /api/v1/network/directory/{profile_id}`
  - Fetches individual public profile. Returns 404 if private, draft, unpublished, or unconsented.

### Employer Organizations & Seat Lifecycle
- `POST /api/v1/network/organizations`
  - Creates employer organization. Assigns creator as `owner`. Records `OrgSeatLog`.
- `GET /api/v1/network/organizations`
  - Lists organizations the current user belongs to.
- `GET /api/v1/network/organizations/{org_id}`
  - Retrieves organization details, domain verification status, and team members. 403 Forbidden for non-members.
- `POST /api/v1/network/organizations/{org_id}/invitations`
  - Invites colleague via email with role (`admin`, `hiring_manager`, `member`). Generates invitation token. Owner/admin only.
- `POST /api/v1/network/organizations/invitations/{token}/accept`
  - Accepts invitation and activates seat.
- `PUT /api/v1/network/organizations/{org_id}/members/{membership_id}`
  - Updates member role. Admins cannot alter owner or other admins.
- `DELETE /api/v1/network/organizations/{org_id}/members/{membership_id}`
  - Revokes seat. Revoked members immediately lose access.
- `GET /api/v1/network/organizations/{org_id}/audit-logs`
  - Retrieves seat audit trail. Owner/admin only.

### Verification & Sandbox Providers
- `POST /api/v1/network/verification/claims`
  - Submits verification claim (`email_domain`, `org_representative`, `github_contribution`, etc.).
- `POST /api/v1/network/verification/claims/{claim_id}/evidence`
  - Submits evidence payload. Prohibits direct government ID submission (400 Bad Request).
- `PUT /api/v1/network/verification/evidence/{evidence_id}/correction`
  - Submits correction notes and updated references for rejected evidence.
- `POST /api/v1/network/verification/claims/{claim_id}/sandbox-verify`
  - Executes sandbox verification: validates repo URL, verifies contribution role, checks commit count, records minimal scopes (`read:user`, `public_repo`).

### Reputation & Reports
- `GET /api/v1/network/reputation/{user_or_org_id}`
  - Returns multi-component reputation breakdown, time decay audit, sample size, and `status_label` (`"New talent (insufficient data)"` if sample size < 3).
- `POST /api/v1/network/reports`
  - Files marketplace report or verification appeal.

---

## 3. Verification Protocols & Anti-Fraud Architecture

### Verification Levels
- **Level 1 — Email & Domain Verification**:
  - Personal email confirmed via verification token or corporate domain matched via DNS TXT record (`signaldesk-verification=...`).
- **Level 2 — Organization Representative / Identity Status**:
  - Validated via approved provider (Stripe Identity / Sandbox IDP). Stores ONLY provider reference ID (`provider_reference_id`) and status. Never directly captures or stores government ID scans.
- **Level 3 — Portfolio & Contribution Evidence**:
  - Minimal OAuth scopes (`read:user`, `public_repo`).
  - Differentiates `owner` from `contributor` based on commit author matching, PR history, and branch ownership.
  - Revocation supported: tokens can be disconnected at any time without impacting verified historical claims.

### Anti-Fraud & Commercial Neutrality
1. **No Paid Pay-to-Win**:
   - Upgrading to paid subscription plans (Pro) **never** influences verification badge eligibility, rank in the talent directory, or client visibility.
2. **No Fabricated Badges**:
   - Verification status is strictly derived from valid `VerificationEvidence` records. Mock or unverified claims remain explicitly marked as `"Unverified Claim"` or `"Claimed"`.
3. **Manipulation Safeguards**:
   - Self-hires and self-reviews (`user_id == counterparty_id`) are flagged `is_suspicious=True` and discarded from reputation calculations.
   - Circular review rings (reciprocal rapid transactions between two accounts) are detected and suppressed.
   - Bursts of rapid events from a single IP/actor are clustered and throttled.

---

## 4. Reputation Mathematical Model & Fairness

Universal uncalibrated single ratings (e.g. "4.8 / 5.0") distort marketplace dynamics by punishing newcomers and incentivizing review trading. SignalDesk computes an **observable multidimensional breakdown**:

1. **Confirmed Deliveries**: Integer count of confirmed milestone / task completions.
2. **Response Metrics**:
   - `response_rate_pct`: Percentage of inbound opportunities acknowledged within 24 hours.
   - `avg_response_minutes`: Average response latency in minutes.
3. **Repeat Client Rate**: Percentage of counterparties engaging in 2+ transactions.
4. **Disputes Resolved**: Percentage of contested scopes concluded amicably.
5. **Sample Size & Insufficient Data Gate**:
   - If `sample_size < 3`: Flagged as `has_sufficient_data = False`. Displayed with neutral badge: **`"New talent (insufficient data)"`**. Calibrated percentage is not shown, preventing 0% penalties for new joiners.
6. **Time Decay Weighting**:
   - Interaction age $\le 30$ days: Weight $1.0$
   - Interaction age $31 - 90$ days: Weight $0.8$
   - Interaction age $91 - 180$ days: Weight $0.5$
   - Interaction age $> 180$ days: Weight $0.2$
7. **Fair Exposure Policy**:
   - Directory discovery interleaves newcomers with established profiles to prevent liquidity capture by early accounts.

---

## 5. Buyer Acquisition Validation Plan

### Objective
Validate commercial buyer demand in the **AI / Software / Automation Services** segment before activating the public marketplace at Gate 18.

### Phase 1: Problem & ICP Discovery (Weeks 1–3)
- **Target Ideal Customer Profiles (ICPs)**:
  1. Early-stage AI startups needing custom autonomous agent pipelines (LangChain, Celery, LlamaIndex).
  2. B2B SaaS agencies needing FastAPI backend integrations and workflow scraping.
  3. Mid-market engineering leads seeking vetted contract developers with verified commit histories.
- **Demand Validation Interviews**:
  - Conduct 25 structured interviews with technical hiring managers.
  - Hypothesis: Buyers value verifiable commit history and contribution role distinction over unverified self-claimed portfolio links.
  - Success metric: $\ge 70\%$ of interviewees state verified contribution evidence would reduce their screening time by half.

### Phase 2: Inbound Demand & Shadow Matching (Weeks 4–6)
- **Continuous Scraper Lead Correlation**:
  - Aggregate incoming scraped leads (`JobRecord`) matching the `"ai_software_automation"` segment.
  - Evaluate how many active lead opportunities match verified talent profiles on the platform.
- **Employer Waitlist & Curated Pilot Cohort**:
  - Onboard 15 pilot employers into the private employer workspace (`/employer/settings`).
  - Grant pilot hiring managers preview access to search the directory and review evidence drawers.
  - Measure: Search-to-contact intent rate (clicks on "Contact via Platform").
  - Target: $\ge 15\%$ contact intent rate across pilot employers.

### Phase 3: Pilot Transactions & Feedback Loops (Weeks 7–9)
- **Controlled Scope Deliveries**:
  - Track 10 mediated pilot contracts between opted-in freelancers and pilot employers.
  - Validate response times, milestone confirmations, and dispute resolution workflows.
  - Gather structured appeal/feedback data via `/api/v1/network/reports`.
- **Gate 18 Readiness Gate Check**:
  - [ ] $\ge 10$ confirmed pilot deliveries concluded without unresolvable disputes.
  - [ ] Buyer NPS $\ge 50$ on candidate verification fidelity.
  - [ ] Zero security incidents or IDOR leakages in private preview.
  - [ ] Clear proof of organic repeat hiring demand.

---

## 6. Verification Evidence Summary

- **FastAPI Test Suite**: `fastapi/tests/test_phase13_talent_employer_network.py`
  - `test_freelancer_profile_lifecycle`: 100% pass (editor, skills, artifacts, availability expiry, rates, opt-in consent, preview).
  - `test_employer_org_and_seat_lifecycle`: 100% pass (org creation, invite, token accept, role update, seat revoke, audit logs).
  - `test_verification_levels_and_sandbox_provider`: 100% pass (Level 1/2/3 claims, sandbox provider, role discrimination, correction workflow, government ID rejection).
  - `test_both_side_reputation_and_manipulation_checks`: 100% pass (events, time decay, sample size threshold, newcomer badge, self-hire suppression).
  - `test_directory_discovery_privacy_and_security`: 100% pass (search filters, non-discriminatory filters, opt-out unpublish, IDOR prevention, X-Robots-Tag).
- **Frontend Test Suite**: `frontend/tests/app/talent-network.test.tsx`
  - Profile editor UI rendering & privacy toggles: Pass.
  - Directory search, cards & evidence drawer: Pass.
  - Employer organization settings & seat management: Pass.
- **Alembic Migration**: `20261126_talent_employer_network_phase13` (single head verified).
- **Public Marketplace Activation**: Feature flag `FEATURE_MARKETPLACE_ENABLED=False`, kept in private preview until Gate 18.
