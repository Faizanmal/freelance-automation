from __future__ import annotations

from typing import Any

import httpx

from ai.providers.base import AIProvider
from ai.schemas.analysis import JobAnalysis


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    async def analyze_job(self, job_text: str) -> JobAnalysis:
        prompt = self._build_prompt(job_text)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 800,
                },
            )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return self._parse_response(content)

    def _build_prompt(self, job_text: str) -> str:
        return (
            "You are an AI assistant that analyzes a freelance job description. "
            "Return JSON only with these fields: skills, budget, difficulty, seniority, urgency, timezone, project_type, "
            "relevance_score, success_probability, estimated_hours, estimated_profit, missing_skills, risk_score, summary, proposal_draft, questions_to_ask. "
            "If a field is not present, return null or an empty list. "
            "Do not include any extra keys. "
            f"Job description:\n{job_text}"
        )

    def _parse_response(self, content: str) -> JobAnalysis:
        data = self._parse_json(content)
        return JobAnalysis(raw_json=data, **data)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        import json

        return json.loads(content)
