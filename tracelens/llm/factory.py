from __future__ import annotations

from tracelens.config import Settings
from tracelens.llm import LLMClient


def create_llm_client(settings: Settings) -> LLMClient | None:
    """Create an LLM client from settings. Returns None if LLM is not configured."""
    if not settings.llm_enabled:
        return None

    if settings.llm_provider == "anthropic":
        from tracelens.llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "claude-sonnet-4-20250514",
            base_url=settings.llm_base_url,
        )

    if settings.llm_provider == "openai":
        from tracelens.llm.openai_client import OpenAIClient

        return OpenAIClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "gpt-4o",
            base_url=settings.llm_base_url,
        )

    return None
