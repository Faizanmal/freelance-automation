from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from app.core.logging.logger import get_logger

from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.llm import any_llm_configured, chat_completion

logger = get_logger(__name__)

# Multi-word / dotted skills first; short tokens matched with word boundaries.
SKILL_LEXICON = (
    "machine learning",
    "next.js",
    "node.js",
    "react native",
    "c#",
    ".net",
    "fastapi",
    "django",
    "flask",
    "typescript",
    "javascript",
    "postgresql",
    "postgres",
    "mongodb",
    "graphql",
    "kubernetes",
    "terraform",
    "ansible",
    "playwright",
    "selenium",
    "langchain",
    "wordpress",
    "shopify",
    "tailwind",
    "python",
    "react",
    "nextjs",
    "nodejs",
    "node",
    "golang",
    "rust",
    "java",
    "kotlin",
    "swift",
    "aws",
    "azure",
    "gcp",
    "docker",
    "mysql",
    "redis",
    "figma",
    "vue",
    "angular",
    "php",
    "laravel",
    "ruby",
    "rails",
    "dotnet",
    "devops",
    "fastapi",
    "llm",
    "css",
    "ux",
    "ui",
    "ml",
    "ai",
    "go",
    "rest",
    "api",
)

SENIORITY_NORMALIZE = {
    "intern": "junior",
    "junior": "junior",
    "entry": "junior",
    "associate": "junior",
    "jr": "junior",
    "mid": "mid",
    "mid-level": "mid",
    "intermediate": "mid",
    "senior": "senior",
    "sr": "senior",
    "lead": "lead",
    "principal": "lead",
    "staff": "lead",
    "architect": "lead",
}

QUALITY_PATTERNS = (
    (r"\bunpaid\b", "unpaid"),
    (r"\bfor\s+exposure\b", "exposure"),
    (r"\bcourse\b|\btutorial\b|\bootcamp\b", "course"),
    (r"\bguaranteed\s+income\b", "spam"),
    (r"\bcrypto\s+airdrop\b", "spam"),
)


@dataclass(slots=True)
class JobEnrichment:
    skills: list[str] = field(default_factory=list)
    seniority: str | None = None
    difficulty: str | None = None
    project_type: str | None = None
    engagement_type: str | None = None
    quality_flags: list[str] = field(default_factory=list)
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
        skills = self._extract_skills(text)
        tags = [
            str(tag).lower() for tag in ((candidate.metadata or {}).get("tags") or [])
        ]
        for tag in tags:
            if tag and tag not in skills:
                skills.append(tag)

        seniority = self._detect_seniority(text)
        engagement = self._detect_engagement(text)
        quality_flags = self._detect_quality_flags(text)
        project_type = engagement if engagement != "unknown" else "remote-role"
        difficulty = {
            "lead": "high",
            "senior": "high",
            "mid": "medium",
            "junior": "low",
        }.get(seniority or "", "medium")

        summary = (
            f"{candidate.title} at {candidate.company or 'Unknown'} — "
            f"skills: {', '.join(skills[:8]) or 'general'}"
            f"{f'; {engagement}' if engagement != 'unknown' else ''}."
        )
        return JobEnrichment(
            skills=skills[:20],
            seniority=seniority,
            difficulty=difficulty,
            project_type=project_type,
            engagement_type=engagement,
            quality_flags=quality_flags,
            summary=summary,
            relevance_hints=skills[:5],
            provider="heuristic",
        )

    def _extract_skills(self, text: str) -> list[str]:
        found: list[str] = []
        for skill in SKILL_LEXICON:
            if " " in skill or "." in skill or skill.startswith(".") or len(skill) <= 2:
                pattern = rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])"
                if re.search(pattern, text):
                    found.append(skill)
            elif skill in text:
                # Longer tokens: still use boundaries to avoid substring noise.
                pattern = rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])"
                if re.search(pattern, text):
                    found.append(skill)
        # Prefer longer phrases first already via lexicon order; de-dupe.
        return list(dict.fromkeys(found))

    def _detect_seniority(self, text: str) -> str | None:
        for raw, band in (
            ("principal", "lead"),
            ("staff", "lead"),
            ("architect", "lead"),
            ("lead", "lead"),
            ("senior", "senior"),
            (r"sr\.?", "senior"),
            ("mid-level", "mid"),
            ("intermediate", "mid"),
            (r"\bmid\b", "mid"),
            ("junior", "junior"),
            ("intern", "junior"),
            ("entry", "junior"),
            ("associate", "junior"),
        ):
            if raw.startswith(r"\b") or "?" in raw:
                if re.search(raw, text):
                    return band
            elif re.search(rf"(?<![a-z0-9]){raw}(?![a-z0-9])", text):
                return band
        return None

    def _detect_engagement(self, text: str) -> str:
        if re.search(r"\bfreelance\b|\bcontractor\b|\bgig\b", text):
            return "freelance"
        if re.search(r"\bcontract\b|\bfixed[\s-]?price\b|\bhourly\b", text):
            return "contract"
        if re.search(r"\bfull[\s-]?time\b|\bw-?2\b|\bsalary\b|\bpermanent\b", text):
            return "full_time"
        return "unknown"

    def _detect_quality_flags(self, text: str) -> list[str]:
        flags: list[str] = []
        for pattern, label in QUALITY_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                flags.append(label)
        return list(dict.fromkeys(flags))[:5]

    async def _enrich_llm(self, candidate: JobCandidate) -> JobEnrichment:
        prompt = (
            "Analyze this job and return JSON only with keys: "
            "skills (string array), seniority (junior|mid|senior|lead|null), "
            "difficulty, project_type, engagement_type "
            "(freelance|contract|full_time|unknown), "
            "quality_flags (string array), summary. "
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
        seniority_raw = (data.get("seniority") or "") or ""
        seniority = SENIORITY_NORMALIZE.get(str(seniority_raw).lower().strip()) or (
            str(seniority_raw).lower().strip()
            if str(seniority_raw).lower().strip()
            in {"junior", "mid", "senior", "lead"}
            else None
        )
        return JobEnrichment(
            skills=[str(s).lower() for s in (data.get("skills") or [])][:20],
            seniority=seniority,
            difficulty=data.get("difficulty"),
            project_type=data.get("project_type"),
            engagement_type=data.get("engagement_type") or "unknown",
            quality_flags=[str(f).lower() for f in (data.get("quality_flags") or [])][
                :5
            ],
            summary=data.get("summary"),
            relevance_hints=[str(s).lower() for s in (data.get("skills") or [])][:5],
            provider=result.provider,
        )
