from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path


class ISelectorStore(ABC):
    @abstractmethod
    async def get_selector(self, field_name: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def save_selector(self, field_name: str, selector: str) -> None:
        raise NotImplementedError


class MemorySelectorStore(ISelectorStore):
    def __init__(self) -> None:
        self._selectors: dict[str, str] = {}

    async def get_selector(self, field_name: str) -> str | None:
        return self._selectors.get(field_name)

    async def save_selector(self, field_name: str, selector: str) -> None:
        self._selectors[field_name] = selector


class FileSelectorStore(ISelectorStore):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._selectors = self._load_selectors()

    def _load_selectors(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        content = self.path.read_text(encoding="utf-8")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    async def get_selector(self, field_name: str) -> str | None:
        return self._selectors.get(field_name)

    async def save_selector(self, field_name: str, selector: str) -> None:
        self._selectors[field_name] = selector
        self.path.write_text(json.dumps(self._selectors, indent=2), encoding="utf-8")
