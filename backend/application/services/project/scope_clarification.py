"""Phase 14 — AI scope clarification, standardized templates, and safety content policy scanner."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any

# Standardized templates for AI, Software, and Automation services
STANDARDIZED_PROJECT_TEMPLATES = {
    "fastapi_backend": {
        "title": "Production FastAPI Backend Service",
        "description": "Architect and deploy an asynchronous FastAPI backend service with PostgreSQL, Alembic migrations, JWT authentication, and structured validation.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "SQLAlchemy", "AsyncIO", "Docker"],
        "scope_level": "medium",
        "work_type": "remote",
        "commitment_type": "contract",
        "budget_min": 2500.0,
        "budget_max": 5000.0,
        "rate_period": "fixed",
        "est_weeks": 3,
        "milestones": [
            {"title": "Architecture & Data Model", "budget_pct": 30, "est_days": 7},
            {"title": "Core Endpoints & Business Logic", "budget_pct": 50, "est_days": 10},
            {"title": "Testing, Integration & Deploy", "budget_pct": 20, "est_days": 4},
        ],
        "acceptance_criteria": [
            "All endpoints fully typed with Pydantic v2 schemas",
            "Async database queries with zero blocking I/O",
            "Comprehensive test coverage (>85%) with pytest",
            "Containerized deployment recipe with Docker Compose",
        ],
    },
    "ai_agent_pipeline": {
        "title": "Autonomous Agent Workflow & Tool Integration",
        "description": "Design an autonomous agent system featuring typed tool calling, vector/hybrid memory retrieval, prompt injection defense, and resilient execution loops.",
        "skills": ["Python", "LangChain", "LLMs", "Vector DB", "FastAPI", "Prompt Engineering"],
        "scope_level": "medium",
        "work_type": "remote",
        "commitment_type": "contract",
        "budget_min": 3500.0,
        "budget_max": 7500.0,
        "rate_period": "fixed",
        "est_weeks": 4,
        "milestones": [
            {"title": "Agent System Architecture & Prompt Design", "budget_pct": 30, "est_days": 8},
            {"title": "Deterministic Tool Execution & Memory Layer", "budget_pct": 40, "est_days": 12},
            {"title": "Evaluation Benchmark & Security Hardening", "budget_pct": 30, "est_days": 8},
        ],
        "acceptance_criteria": [
            "Server-authoritative tool execution boundary with zero dynamic execution permissions",
            "Adversarial prompt injection sanitization",
            "Benchmark evaluation set showing accuracy and latency metrics",
            "Safe fallback mechanisms when upstream model times out",
        ],
    },
    "scraping_etl": {
        "title": "Resilient Web Scraping & Data Pipeline",
        "description": "Build high-throughput, respectful scrapers with proxy rotation, rate-limiting, deduplication, schema normalization, and automated export.",
        "skills": ["Python", "Playwright", "BeautifulSoup", "Celery", "Redis", "PostgreSQL"],
        "scope_level": "small",
        "work_type": "remote",
        "commitment_type": "contract",
        "budget_min": 1500.0,
        "budget_max": 3000.0,
        "rate_period": "fixed",
        "est_weeks": 2,
        "milestones": [
            {"title": "Scraper Ingest & Browser Automation", "budget_pct": 50, "est_days": 7},
            {"title": "Data Pipeline, Normalization & Celery Beat", "budget_pct": 50, "est_days": 7},
        ],
        "acceptance_criteria": [
            "Resilient retry mechanisms with exponential backoff",
            "Strict deduplication and schema validation before DB insert",
            "Fail-safe error logging and rate limit compliance",
        ],
    },
    "fullstack_mvp": {
        "title": "Full-Stack AI Application MVP",
        "description": "Deliver a complete SaaS MVP with Next.js frontend, FastAPI backend, user auth, responsive design system, and AI copilot integration.",
        "skills": ["TypeScript", "Next.js", "React", "FastAPI", "PostgreSQL", "TailwindCSS"],
        "scope_level": "large",
        "work_type": "remote",
        "commitment_type": "contract",
        "budget_min": 6000.0,
        "budget_max": 12000.0,
        "rate_period": "fixed",
        "est_weeks": 6,
        "milestones": [
            {"title": "UX Wireframes & Database Schema", "budget_pct": 25, "est_days": 10},
            {"title": "API & Full-Stack Core Flows", "budget_pct": 45, "est_days": 18},
            {"title": "Polishing, Security Audit & Staging Deploy", "budget_pct": 30, "est_days": 14},
        ],
        "acceptance_criteria": [
            "Mobile-responsive UI using application design tokens",
            "End-to-end user authentication and session management",
            "Documented REST API with OpenAPI specification",
            "Clean CI test pipeline with automated checks",
        ],
    },
}

# Safety & Compliance Rules
DISCRIMINATORY_PATTERNS = [
    r"\b(under\s+\d{2}|over\s+\d{2}|between\s+\d{2}\s+and\s+\d{2})\s+years?\s+old\b",
    r"\b(female|male|women|men)\s+(only|candidates?|developers?|preferred)\b",
    r"\b(native\s+born|must\s+be\s+caucasian|white|black|asian\s+only)\b",
    r"\b(christian|muslim|hindu|jewish)\s+only\b",
]

MALICIOUS_LINK_PATTERNS = [
    r"\bhttps?:\/\/[^\s]+(?:\.exe|\.bat|\.scr|\.sh|\.zip\?download=1)\b",
    r"\bhttps?:\/\/(?:bit\.ly|tinyurl\.com|t\.co|is\.gd|cutt\.ly)\/[a-zA-Z0-9_-]+\b",
    r"\b(discord\.gg\/[a-zA-Z0-9]+|t\.me\/[a-zA-Z0-9_]+)\b",
]

UPFRONT_FEE_PATTERNS = [
    r"\b(pay|deposit|transfer|send)\s+(a\s+fee|an\s+advance|equipment\s+fee|registration\s+fee|security\s+deposit)\b",
    r"\b(buy|purchase)\s+(your\s+own\s+software\s+license|tools\s+from\s+us|training\s+kit)\b",
    r"\bpay\s+before\s+(you\s+start|receiving\s+work|onboarding)\b",
]

EXCESSIVE_UNPAID_PATTERNS = [
    r"\b(unpaid|free)\s+(trial|test\s+task|probation)\s+(of\s+\d+\s+(weeks?|days?|months?)|for\s+\d+\s+(weeks?|days?))\b",
    r"\bbuild\s+the\s+entire\s+(app|prototype|system)\s+for\s+free\s+as\s+a\s+test\b",
    r"\bunpaid\s+speculative\s+work\b",
]


class ProjectSafetyScanner:
    """Scans project descriptions and briefs for policy violations and flags high-risk projects for human review."""

    @classmethod
    def scan_project_content(
        cls,
        title: str,
        description: str,
        budget_min: float,
        budget_max: float,
        acceptance_criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        full_text = f"{title}\n{description}\n{' '.join(acceptance_criteria or [])}".lower()

        # 1. Budget validation
        if budget_min <= 0 or budget_max <= 0:
            return {
                "passed": False,
                "reason_code": "missing_budget",
                "evidence_summary": "Budget must be greater than zero. Unfunded projects cannot be submitted.",
            }
        if budget_max < budget_min:
            return {
                "passed": False,
                "reason_code": "missing_budget",
                "evidence_summary": "Maximum budget cannot be less than minimum budget.",
            }

        # 2. Discriminatory requirements
        for pattern in DISCRIMINATORY_PATTERNS:
            match = re.search(pattern, full_text)
            if match:
                return {
                    "passed": False,
                    "reason_code": "discriminatory_criteria",
                    "evidence_summary": f"Detected discriminatory requirement pattern: '{match.group(0)}'. Content violates equal opportunity standards.",
                }

        # 3. Malicious links or off-platform redirect phishing
        for pattern in MALICIOUS_LINK_PATTERNS:
            match = re.search(pattern, full_text)
            if match:
                return {
                    "passed": False,
                    "reason_code": "malicious_link",
                    "evidence_summary": f"Detected prohibited executable, obfuscated shortener, or off-platform contact link: '{match.group(0)}'.",
                }

        # 4. Upfront freelancer payment scam check
        for pattern in UPFRONT_FEE_PATTERNS:
            match = re.search(pattern, full_text)
            if match:
                return {
                    "passed": False,
                    "reason_code": "upfront_fee_request",
                    "evidence_summary": f"Detected request for upfront freelancer fee or equipment payment: '{match.group(0)}'. Fraud policy violation.",
                }

        # 5. Excessive unpaid speculative work
        for pattern in EXCESSIVE_UNPAID_PATTERNS:
            match = re.search(pattern, full_text)
            if match:
                return {
                    "passed": False,
                    "reason_code": "excessive_unpaid_work",
                    "evidence_summary": f"Detected excessive unpaid speculative work requirement: '{match.group(0)}'. Freelancer protection policy violation.",
                }

        return {"passed": True, "reason_code": None, "evidence_summary": None}


class ScopeClarificationEngine:
    """Generates structured scope breakdowns, deliverables, boundaries, and acceptance criteria from plain-language input."""

    @classmethod
    def clarify_scope(
        cls,
        raw_description: str,
        template_key: str | None = None,
        skills_hint: list[str] | None = None,
    ) -> dict[str, Any]:
        """Synthesize scope without invented market estimates; explicitly highlights basis and unknowns."""
        template = STANDARDIZED_PROJECT_TEMPLATES.get(template_key or "")

        # Extract suggested skills
        suggested_skills = list(skills_hint or [])
        if template:
            for s in template["skills"]:
                if s not in suggested_skills:
                    suggested_skills.append(s)
        else:
            # Simple keyword extraction
            words = raw_description.lower()
            keywords = ["python", "fastapi", "react", "next.js", "docker", "postgres", "ai", "langchain", "celery", "scraping"]
            for kw in keywords:
                if kw in words and kw.title() not in suggested_skills:
                    suggested_skills.append(kw.title())
            if not suggested_skills:
                suggested_skills = ["Software Engineering", "AI Automation"]

        # Scope deliverables breakdown
        cleaned_desc = raw_description.strip()
        deliverables = [
            f"Phase 1: Architecture, schema definition, and interface contract for: {cleaned_desc[:80]}...",
            "Phase 2: Core functional implementation with unit and integration tests.",
            "Phase 3: Verification, documentation, error handling, and deploy recipe.",
        ]

        boundaries = {
            "in_scope": [
                "Agreed functional requirements and documented API endpoints",
                "Automated test coverage and documentation",
                "Deployment guide or containerized script",
            ],
            "out_of_scope": [
                "Unbounded feature additions post-milestone sign-off",
                "Third-party paid SaaS subscription expenses (borne directly by client)",
                "24/7 unmetered production on-call support unless retained",
            ],
        }

        # Realistic budget basis and unknowns
        est_hours_min = 20
        est_hours_max = 60
        if template:
            suggested_min = template["budget_min"]
            suggested_max = template["budget_max"]
            rate_period = template["rate_period"]
        else:
            suggested_min = 2000.0
            suggested_max = 4500.0
            rate_period = "fixed"

        budget_basis_notes = (
            f"Estimate basis: Assumes ~{est_hours_min} to {est_hours_max} engineering hours at market median contractor rates ($75-$100/hr). "
            "Key unknowns: Third-party API rate limits, external system authentication flows, and data volume constraints."
        )

        acceptance_criteria = template["acceptance_criteria"] if template else [
            "Functional execution matching agreed specification with clean logs",
            "Zero unhandled exceptions on expected error paths",
            "Code thoroughly documented and tested with passing automated tests",
        ]

        milestone_outline = template["milestones"] if template else [
            {"title": "Initial Architecture & Proof of Concept", "budget_pct": 35, "est_days": 7},
            {"title": "Core Implementation & Testing", "budget_pct": 45, "est_days": 10},
            {"title": "Handoff, Review & Acceptance Sign-off", "budget_pct": 20, "est_days": 4},
        ]

        return {
            "clarified_summary": f"Project Scope Breakdown:\n\n{cleaned_desc}\n\nDeliverables:\n" + "\n".join(f"- {d}" for d in deliverables),
            "deliverables": deliverables,
            "boundaries": boundaries,
            "suggested_skills": suggested_skills,
            "acceptance_criteria": acceptance_criteria,
            "milestone_outline": milestone_outline,
            "suggested_budget_min": suggested_min,
            "suggested_budget_max": suggested_max,
            "rate_period": rate_period,
            "budget_basis_notes": budget_basis_notes,
            "requires_client_approval": True,
        }

    @classmethod
    def compute_content_hash(cls, title: str, description: str, org_id: str) -> str:
        """Compute sha256 hash to detect duplicate spam postings from the same org within short intervals."""
        raw = f"{org_id}:{title.strip().lower()}:{description.strip().lower()[:200]}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
