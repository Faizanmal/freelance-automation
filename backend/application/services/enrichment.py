from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from app.core.logging.logger import get_logger

from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.llm import any_llm_configured, chat_completion

logger = get_logger(__name__)

SKILL_LEXICON = {
    "python",
    "fastapi",
    "django",
    "flask",
    "react",
    "next.js",
    "nextjs",
    "typescript",
    "javascript",
    "node",
    "nodejs",
    "golang",
    "go",
    "rust",
    "java",
    "kotlin",
    "swift",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "postgres",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "graphql",
    "rest",
    "api",
    "machine learning",
    "ml",
    "ai",
    "llm",
    "langchain",
    "selenium",
    "playwright",
    "figma",
    "ui",
    "ux",
    "css",
    "tailwind",
    "vue",
    "angular",
    "php",
    "laravel",
    "ruby",
    "rails",
    "dotnet",
    ".net",
    "c#",
    "devops",
    "terraform",
    "ansible",
    "wordpress",
    "shopify",
}


@dataclass(slots=True)
class JobEnrichment:
    skills: list[str] = field(default_factory=list)
    seniority: str | None = None
    difficulty: str | None = None
    project_type: str | None = None
    summary: str | None = None
    relevance_hints: list[str] = field(default_factory=list)
    provider: str = "heuristic"

    def to_dict(self) -> dict:
        return asdict(self)


class EnrichmentService:
    """Heuristic enrichment always; LLM via fallback chain when any provider key is set."""

    async def enrich(self, candidate: JobCandidate) -> JobEnrichment:
        if any_llm_configured():
            try:
                return await self._enrich_llm(candidate)
            except Exception:
                logger.warning(
                    "LLM enrichment failed for %s, falling back to heuristic",
                    candidate.title,
                    exc_info=True,
                )
        else:
            logger.info(
                "No LLM configured. Using heuristic enrichment for %s", candidate.title
            )
        return self._enrich_heuristic(candidate)

    def _enrich_heuristic(self, candidate: JobCandidate) -> JobEnrichment:
        text = f"{candidate.title}\n{candidate.description}\n{' '.join((candidate.metadata or {}).get('tags') or [])}".lower()
        text = re.sub(r"<[^>]+>", " ", text)
        skills = sorted({skill for skill in SKILL_LEXICON if skill in text})
        tags = [
            str(tag).lower() for tag in ((candidate.metadata or {}).get("tags") or [])
        ]
        for tag in tags:
            if tag and tag not in skills:
                skills.append(tag)

        seniority = None
        for level in (
            "intern",
            "junior",
            "mid",
            "senior",
            "lead",
            "principal",
            "staff",
        ):
            if re.search(rf"\b{level}\b", text):
                seniority = level
                break

        project_type = (
            "contract"
            if "contract" in text or "freelance" in text
            else (
                "full-time"
                if "full-time" in text or "full time" in text
                else "remote-role"
            )
        )
        difficulty = (
            "high"
            if seniority in {"senior", "lead", "principal", "staff"}
            else (
                "medium"
                if seniority == "mid"
                else "low" if seniority in {"junior", "intern"} else "medium"
            )
        )
        summary = f"{candidate.title} at {candidate.company or 'Unknown'} — skills: {', '.join(skills[:8]) or 'general'}."
        return JobEnrichment(
            skills=skills[:20],
            seniority=seniority,
            difficulty=difficulty,
            project_type=project_type,
            summary=summary,
            relevance_hints=skills[:5],
            provider="heuristic",
        )

    async def _enrich_llm(self, candidate: JobCandidate) -> JobEnrichment:
        prompt = (
            "Analyze this job and return JSON only with keys: "
            "skills (string array), seniority, difficulty, project_type, summary. "
            "No markdown.\n\n"
            f"Title: {candidate.title}\nCompany: {candidate.company}\n"
            f"Description:\n{candidate.description[:4000]}"
        )
        result = await chat_completion(
            system="You analyze freelance job listings. Respond with a single JSON object only.",
            user=prompt,
            temperature=0.1,
            json_mode=True,
            timeout=45.0,
        )
        data = json.loads(result.content)
        return JobEnrichment(
            skills=[str(s).lower() for s in (data.get("skills") or [])][:20],
            seniority=data.get("seniority"),
            difficulty=data.get("difficulty"),
            project_type=data.get("project_type"),
            summary=data.get("summary"),
            relevance_hints=[str(s).lower() for s in (data.get("skills") or [])][:5],
            provider=result.provider,
        )
