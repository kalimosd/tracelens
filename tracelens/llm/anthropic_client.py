from __future__ import annotations

from dataclasses import dataclass

from tracelens.llm import LLMMessage

DEFAULT_MODEL = "claude-sonnet-4-20250514"


@dataclass(slots=True)
class AnthropicClient:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = ""

    def chat(self, messages: list[LLMMessage]) -> str:
        import anthropic

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        client = anthropic.Anthropic(**kwargs)

        system = ""
        chat_msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                chat_msgs.append({"role": m.role, "content": m.content})

        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system or "You are a performance analysis assistant.",
            messages=chat_msgs,
        )
        return response.content[0].text
