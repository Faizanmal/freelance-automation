from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IScraper(ABC):
    @abstractmethod
    async def login(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def extract_jobs(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def save(self, job: dict[str, Any]) -> None:
        raise NotImplementedError
