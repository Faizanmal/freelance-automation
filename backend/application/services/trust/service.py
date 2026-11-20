"""Compose extraction + evidence + risk + employer + checklist for a lead."""

from __future__ import annotations

from typing import Any

from backend.application.services.trust.due_diligence import build_due_diligence_checklist
from backend.application.services.trust.employer_research import build_employer_panel
from backend.application.services.trust.evidence import (
    build_evidence_bundle,
    evidence_summary,
)
from backend.application.services.trust.project_extraction import extract_from_job_record
from backend.application.services.trust.risk_indicators import (
    assess_risk_indicators,
    risk_panel_payload,
)


class TrustIntelligenceService:
    """
    Keep relevance / freshness / hiring intent / risk separate.
    Never emits an automatic scam verdict or model-only exclusion.
    """

    def analyze_job(self, job: Any, *, include_evidence_records: bool = True) -> dict[str, Any]:
        enrichment = getattr(job, "enrichment", None) or {}
        extraction = extract_from_job_record(job, prefer_llm=False)
        # Persist-ready extraction snapshot without PII beyond listing text already stored
        extraction_meta = {
            "provider": extraction.provider,
            "model": extraction.model,
            "prompt_version": extraction.prompt_version,
            "extraction_version": extraction.extraction_version,
            "cost_usd": extraction.cost_usd,
        }

        indicators = assess_risk_indicators(
            title=getattr(job, "title", "") or "",
            description=getattr(job, "description", "") or "",
            url=getattr(job, "url", None),
            company=getattr(job, "company", None),
            source_name=getattr(job, "source_name", None),
            enrichment=enrichment if isinstance(enrichment, dict) else {},
            is_duplicate_suspected=bool(
                (getattr(job, "duplicate_confidence", None) or 0) >= 0.85
            ),
            budget_min=getattr(job, "budget_min", None),
            budget_max=getattr(job, "budget_max", None),
        )
        employer = build_employer_panel(
            company=getattr(job, "company", None),
            listing_url=getattr(job, "url", None),
            source_name=getattr(job, "source_name", None),
            posted_at=getattr(job, "posted_at", None),
            first_seen_at=(
                job.first_seen_at.isoformat()
                if getattr(job, "first_seen_at", None)
                else None
            ),
            enrichment=enrichment if isinstance(enrichment, dict) else {},
        )
        evidence_rows = build_evidence_bundle(
            job_id=getattr(job, "id", None),
            source_name=str(getattr(job, "source_name", "") or ""),
            source_url=getattr(job, "url", None),
            company=getattr(job, "company", None),
            title=str(getattr(job, "title", "") or ""),
            extraction=extraction,
            risk_indicators=indicators,
            employer_panel=employer,
        )
        checklist = build_due_diligence_checklist(
            indicators=indicators,
            extraction=extraction,
            employer_panel=employer,
        )
        risk_panel = risk_panel_payload(indicators)

        # Separate signal channels (do not blend into one "trust score")
        return {
            "channels": {
                "relevance": "see_match_score",
                "freshness": "see_freshness_score",
                "hiring_intent": "see_signals_and_extraction",
                "risk": "see_risk_indicators",
            },
            "extraction": extraction.to_dict(),
            "extraction_meta": extraction_meta,
            "risk": risk_panel,
            "employer": employer,
            "due_diligence": checklist,
            "evidence": evidence_summary(evidence_rows)
            if include_evidence_records
            else {
                "count": len(evidence_rows),
                "by_semantics": evidence_summary(evidence_rows)["by_semantics"],
                "note": evidence_summary(evidence_rows)["note"],
            },
            "policy": {
                "automatic_exclusion_from_model": False,
                "unknown_company_is_not_scam": True,
                "llm_fraud_verdict_forbidden": True,
                "high_risk_native_needs_human_review": risk_panel["requires_human_review"],
                "untrusted_listing_input": True,
            },
        }
