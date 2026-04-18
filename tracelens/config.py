from __future__ import annotations

import os

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "TraceLens"
    env: str = "development"

    # LLM config — leave empty to use rule-based fallback
    llm_provider: str = ""  # "anthropic" or "openai"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""  # for OpenAI-compatible endpoints

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_provider and self.llm_api_key)


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("TRACELENS_APP_NAME", "TraceLens"),
        env=os.getenv("TRACELENS_ENV", "development"),
        llm_provider=os.getenv("TRACELENS_LLM_PROVIDER", ""),
        llm_api_key=os.getenv("TRACELENS_LLM_API_KEY", ""),
        llm_model=os.getenv("TRACELENS_LLM_MODEL", ""),
        llm_base_url=os.getenv("TRACELENS_LLM_BASE_URL", ""),
    )
