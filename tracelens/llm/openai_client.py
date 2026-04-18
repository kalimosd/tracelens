from __future__ import annotations

from dataclasses import dataclass

from tracelens.llm import LLMMessage

DEFAULT_MODEL = "gpt-4o"


@dataclass(slots=True)
class OpenAIClient:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = ""

    def chat(self, messages: list[LLMMessage]) -> str:
        import openai

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        client = openai.OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""
