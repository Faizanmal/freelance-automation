from __future__ import annotations

import json
import re
from typing import Any

from backend.application.services.llm import any_llm_configured, chat_completion
from database.models.job import JobRecord
from database.models.preference import UserPreferences
from database.models.user import User

MARKETPLACE_API_BID = {"freelancer"}
MARKETPLACE_API_PROPOSAL = {"upwork"}
PUBLIC_EMAIL_APPLY = {
    "remoteok",
    "arbeitnow",
    "remotive",
    "weworkremotely",
    "himalayas",
    "jobicy",
    "peopleperhour",
    "guru",
    "serpapi_freelance",
    "serpapi_jobs",
    "serpapi_companies",
    "serpapi_maps",
}


def submit_mode_for_source(source_name: str) -> str:
    """Source-level default without inspecting listing content."""
    name = (source_name or "").lower()
    if name in MARKETPLACE_API_BID:
        return "api_bid"
    if name in MARKETPLACE_API_PROPOSAL:
        # Upwork search works; proposal API submit is not enabled yet.
        return "external_apply"
    if name in PUBLIC_EMAIL_APPLY:
        # Prefer open-listing unless a concrete mailto/email is found on the job.
        return "external_apply"
    return "unsupported"


def submit_mode_for_job(job: JobRecord) -> str:
    name = (job.source_name or "").lower()
    if name in MARKETPLACE_API_BID:
        return "api_bid"
    if name in MARKETPLACE_API_PROPOSAL:
        return "external_apply"
    if name in PUBLIC_EMAIL_APPLY:
        if extract_apply_email(job):
            return "email_apply"
        return "external_apply"
    return "unsupported"


class ProposalDraftService:
    """Generate editable apply form fields. Never auto-submits."""

    async def draft(
        self, *, user: User, preferences: UserPreferences, job: JobRecord
    ) -> dict[str, object]:
        template_fields = self._template_form_fields(
            user=user, preferences=preferences, job=job
        )
        provider = "template"
        form_fields = template_fields

        if any_llm_configured():
            llm_fields, llm_provider = await self._maybe_llm_form_fields(
                job=job,
                preferences=preferences,
                user=user,
                fallback=template_fields,
            )
            if llm_fields:
                form_fields = llm_fields
                provider = llm_provider

        draft_text = str(form_fields.get("proposal") or "")
        return {
            "job_id": job.id,
            "title": job.title,
            "source_name": job.source_name,
            "source_url": job.url,
            "provider": provider,
            "draft": draft_text,
            "form_fields": form_fields,
            "disclaimer": (
                "Review and edit before confirming. Signal Desk only submits after you click Confirm."
            ),
        }

    def _template_form_fields(
        self,
        *,
        user: User,
        preferences: UserPreferences,
        job: JobRecord,
    ) -> dict[str, Any]:
        keywords = [k for k in (preferences.keywords or [])[:6] if k]
        skill_line = ", ".join(keywords) if keywords else "relevant experience"
        budget = self._budget_line(job)
        name = (user.full_name or user.email.split("@")[0]).strip()
        notes = (preferences.notes or "").strip()
        enrichment = job.enrichment if isinstance(job.enrichment, dict) else {}
        summary = job.analysis_summary or enrichment.get("summary") or ""

        opener = (
            f"Hi — I’m {name}, and your {job.title} posting looks like a strong fit "
            f"based on my work with {skill_line}."
        )
        notes_line = f"\n\nAbout me: {notes}" if notes else ""
        summary_line = f"\n\nI reviewed the scope ({summary[:180]})." if summary else ""
        proposal = (
            f"{opener}{summary_line}{notes_line}\n\n"
            f"I’ve shipped similar work and can move quickly on the core scope"
            f"{' within your stated budget' if budget else ''}. "
            f"I can start with a short discovery pass, confirm deliverables, "
            f"and share a concrete timeline within one business day.\n\n"
            f"Happy to jump on a quick call or reply here with a scoped plan.\n\n"
            f"— {name}"
        )

        bid_amount = self._suggest_bid_amount(job, preferences)
        delivery_days = (
            7 if (job.budget_max or 0) and (job.budget_max or 0) < 1000 else 14
        )
        milestone = (
            "Milestone 1: discovery + written plan (30%). "
            "Milestone 2: core delivery (50%). "
            "Milestone 3: revisions + handoff (20%)."
        )

        return {
            "proposal": proposal,
            "bid_amount": bid_amount,
            "currency": "USD",
            "delivery_days": delivery_days,
            "milestone_plan": milestone,
            "milestone_percentage": 100,
            "source_name": job.source_name,
            "source_id": job.source_id,
            "project_url": job.url,
            "submit_mode": submit_mode_for_job(job),
            "apply_url": job.url,
        }

    async def _maybe_llm_form_fields(
        self,
        *,
        job: JobRecord,
        preferences: UserPreferences,
        user: User,
        fallback: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        excerpt = (job.description or "")[:1200]
        enrichment = job.enrichment if isinstance(job.enrichment, dict) else {}
        prompt = (
            "Fill a freelance application form as JSON only. Keys: "
            "proposal (120-200 words), bid_amount (number or null), currency (string), "
            "delivery_days (integer), milestone_plan (short string), milestone_percentage (1-100).\n"
            "Be specific and professional. Never invent clients, metrics, or fake experience.\n"
            f"Freelancer name: {user.full_name or user.email}\n"
            f"Skills: {', '.join(preferences.keywords or [])}\n"
            f"Profile notes: {(preferences.notes or '')[:500]}\n"
            f"Preferred budget range: {preferences.min_budget}-{preferences.max_budget}\n"
            f"Job title: {job.title}\n"
            f"Company: {job.company or 'Unknown'}\n"
            f"Listed budget: {self._budget_line(job) or 'not specified'}\n"
            f"Source: {job.source_name}\n"
            f"Enrichment summary: {job.analysis_summary or enrichment.get('summary') or 'n/a'}\n"
            f"Excerpt: {excerpt}"
        )
        try:
            result = await chat_completion(
                system="You fill freelance bid/apply forms. Respond with a single JSON object only.",
                user=prompt,
                temperature=0.4,
                json_mode=True,
                timeout=30.0,
            )
            parsed = json.loads(result.content)
            return self._merge_llm_fields(fallback, parsed), result.provider
        except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
            return None, "template"

    def _merge_llm_fields(
        self, fallback: dict[str, Any], parsed: dict[str, Any]
    ) -> dict[str, Any]:
        merged = dict(fallback)
        proposal = parsed.get("proposal") or parsed.get("draft")
        if isinstance(proposal, str) and proposal.strip():
            merged["proposal"] = proposal.strip()
        if "bid_amount" in parsed:
            merged["bid_amount"] = self._to_float(parsed.get("bid_amount"))
        if isinstance(parsed.get("currency"), str) and parsed["currency"].strip():
            merged["currency"] = parsed["currency"].strip().upper()[:8]
        if "delivery_days" in parsed:
            days = self._to_int(parsed.get("delivery_days"))
            if days and days > 0:
                merged["delivery_days"] = days
        if (
            isinstance(parsed.get("milestone_plan"), str)
            and parsed["milestone_plan"].strip()
        ):
            merged["milestone_plan"] = parsed["milestone_plan"].strip()
        if "milestone_percentage" in parsed:
            pct = self._to_int(parsed.get("milestone_percentage"))
            if pct is not None and 1 <= pct <= 100:
                merged["milestone_percentage"] = pct
        return merged

    def _suggest_bid_amount(
        self, job: JobRecord, preferences: UserPreferences
    ) -> float | None:
        if job.budget_min is not None and job.budget_max is not None:
            return round((float(job.budget_min) + float(job.budget_max)) / 2, 2)
        if job.budget_max is not None:
            return float(job.budget_max)
        if job.budget_min is not None:
            return float(job.budget_min)
        if preferences.min_budget is not None and preferences.max_budget is not None:
            return round(
                (float(preferences.min_budget) + float(preferences.max_budget)) / 2, 2
            )
        if preferences.max_budget is not None:
            return float(preferences.max_budget)
        return None

    def _budget_line(self, job: JobRecord) -> str | None:
        if job.budget_min and job.budget_max:
            return f"${job.budget_min:,.0f}–${job.budget_max:,.0f}"
        if job.budget_max:
            return f"up to ${job.budget_max:,.0f}"
        if job.budget_min:
            return f"from ${job.budget_min:,.0f}"
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_MAILTO_RE = re.compile(r"mailto:([^?\s\"']+)", re.IGNORECASE)


def extract_apply_email(job: JobRecord) -> str | None:
    for blob in (job.url or "", job.description or ""):
        mailto = _MAILTO_RE.search(blob)
        if mailto:
            return mailto.group(1).strip()
        match = _EMAIL_RE.search(blob)
        if match:
            return match.group(0).strip()
    return None
