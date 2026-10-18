from __future__ import annotations

from typing import Any

import httpx

from ai.providers.base import AIProvider
from ai.schemas.analysis import JobAnalysis


class OllamaProvider(AIProvider):
    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "gpt-4o"
    ) -> None:
        self.base_url = base_url
        self.model = model

    async def analyze_job(self, job_text: str) -> JobAnalysis:
        prompt = self._build_prompt(job_text)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/models/{self.model}/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": 800,
                    "temperature": 0.2,
                    "stream": False,
                },
            )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("output", "")
        data = self._parse_json(content)
        return JobAnalysis(raw_json=data, **data)

    def _build_prompt(self, job_text: str) -> str:
        return (
            "You are a local AI assistant running on Ollama. "
            "Return JSON only with these fields: skills, budget, difficulty, seniority, urgency, timezone, project_type, "
            "relevance_score, success_probability, estimated_hours, estimated_profit, missing_skills, risk_score, summary, proposal_draft, questions_to_ask. "
            "If unknown, return null or empty arrays. "
            f"Job description:\n{job_text}"
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        import json

        return json.loads(content)
