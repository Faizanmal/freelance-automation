from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class SelectorFallbackError(Exception):
    field_name: str
    current_selector: str
    candidates: Sequence[str]

    def __str__(self) -> str:
        return (
            f"Selector fallback required for field '{self.field_name}'. "
            f"Current selector: '{self.current_selector}'. "
            f"Candidates: {list(self.candidates)}"
        )
