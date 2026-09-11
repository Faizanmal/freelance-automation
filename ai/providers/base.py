from __future__ import annotations

from abc import ABC, abstractmethod

from ai.schemas.analysis import JobAnalysis


class AIProvider(ABC):
    @abstractmethod
    async def analyze_job(self, job_text: str) -> JobAnalysis:
        raise NotImplementedError
