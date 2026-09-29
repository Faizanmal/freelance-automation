from __future__ import annotations

import logging
import re

from backend.domain.interfaces import IJobEnrichmentService
from backend.domain.models import EnrichedJob, JobOpportunity

logger = logging.getLogger(__name__)

SKILL_LEXICON = {
    "python", "fastapi", "django", "flask", "react", "next.js", "nextjs",
    "typescript", "javascript", "node", "nodejs", "golang", "go", "rust",
    "java", "kotlin", "swift", "aws", "azure", "gcp", "docker", "kubernetes",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "graphql", "rest",
    "api", "machine learning", "ml", "ai", "llm", "langchain", "selenium",
    "playwright", "figma", "ui", "ux", "css", "tailwind", "vue", "angular",
    "php", "laravel", "ruby", "rails", "dotnet", ".net", "c#", "devops",
    "terraform", "ansible", "wordpress", "shopify",
}

class DomainJobEnrichmentService(IJobEnrichmentService):
    """Heuristic enrichment wrapped in the domain layer."""

    async def enrich(self, job: JobOpportunity) -> EnrichedJob:
        # LLM logic requires dependencies that are currently in fastapi/app/services/llm.py
        # For this domain adaptation, we'll focus on the heuristic logic to avoid coupling 
        # heavily to the unmigrated LLM service unless we inject it.
        # We can implement heuristic directly.
        return self._enrich_heuristic(job)

    def _enrich_heuristic(self, job: JobOpportunity) -> EnrichedJob:
        tags = " ".join([str(t) for t in job.metadata.get("tags") or []])
        text = f"{job.title}\n{job.description}\n{tags}".lower()
        text = re.sub(r"<[^>]+>", " ", text)
        
        skills = sorted({skill for skill in SKILL_LEXICON if skill in text})
        for tag in [str(t).lower() for t in job.metadata.get("tags") or []]:
            if tag and tag not in skills:
                skills.append(tag)

        seniority = None
        for level in ("intern", "junior", "mid", "senior", "lead", "principal", "staff"):
            if re.search(rf"\b{level}\b", text):
                seniority = level
                break

        is_freelance = "contract" in text or "freelance" in text
        summary = f"{job.title} at {job.company or 'Unknown'} — skills: {', '.join(skills[:8]) or 'general'}."

        return EnrichedJob(
            source=job.source,
            external_id=job.external_id,
            title=job.title,
            company=job.company,
            location=job.location,
            description=job.description,
            url=job.url,
            posted_at=job.posted_at,
            metadata=job.metadata,
            skills_required=skills[:20],
            is_freelance=is_freelance,
            match_score_hints={"seniority": seniority, "summary": summary}
        )
