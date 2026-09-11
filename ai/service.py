from __future__ import annotations

from ai.providers.base import AIProvider
from ai.schemas.analysis import JobAnalysis


class AIService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def analyze(self, job_text: str) -> JobAnalysis:
        return await self.provider.analyze_job(job_text)
