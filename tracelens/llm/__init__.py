from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient(Protocol):
    """Abstract interface for LLM providers."""

    def chat(self, messages: list[LLMMessage]) -> str:
        """Send messages and return the assistant's response text."""
        ...
