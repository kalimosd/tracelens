from tracelens.config import Settings
from tracelens.llm import LLMMessage
from tracelens.llm.factory import create_llm_client
from tracelens.agent.synthesis import synthesize_result
from tracelens.types import EvidenceItem


class FakeLLM:
    def chat(self, messages: list[LLMMessage]) -> str:
        return (
            "CONCLUSION: Main thread blocked by binder calls causing 50ms jank.\n\n"
            "DIRECTIONS:\n"
            "- Move binder calls off the main thread\n"
            "- Check system_server response latency\n\n"
            "UNCERTAINTIES:\n"
            "- GPU contribution not measured\n"
        )


def test_factory_returns_none_when_no_key():
    settings = Settings(llm_provider="", llm_api_key="")
    assert create_llm_client(settings) is None


def test_factory_returns_none_for_unknown_provider():
    settings = Settings(llm_provider="unknown", llm_api_key="sk-test")
    assert create_llm_client(settings) is None


def test_llm_enabled_property():
    assert not Settings(llm_provider="", llm_api_key="").llm_enabled
    assert not Settings(llm_provider="anthropic", llm_api_key="").llm_enabled
    assert Settings(llm_provider="anthropic", llm_api_key="sk-test").llm_enabled


def test_synthesize_with_fake_llm():
    evidence = [
        EvidenceItem(title="Long slices", summary="inflate=50ms on main"),
        EvidenceItem(title="Blocked threads", summary="main: total=35ms"),
    ]
    chain = ["Selected role-first strategy", "Scenario: scroll jank"]

    result = synthesize_result(evidence=evidence, chain=chain, llm=FakeLLM(), scenario="scroll jank")

    assert "binder" in result.conclusion.lower()
    assert len(result.optimization_directions) == 2
    assert "GPU" in result.uncertainties[0]


def test_synthesize_falls_back_without_llm():
    evidence = [EvidenceItem(title="Long slices", summary="inflate=50ms")]
    chain = ["step 1"]

    result = synthesize_result(evidence=evidence, chain=chain, llm=None)

    assert result.conclusion  # non-empty after fallback


def test_synthesize_falls_back_on_llm_error():
    class BrokenLLM:
        def chat(self, messages):
            raise RuntimeError("API error")

    evidence = [EvidenceItem(title="Long slices", summary="inflate=50ms")]
    result = synthesize_result(evidence=evidence, chain=["step"], llm=BrokenLLM(), scenario="test")

    # Should fall back to rules, not crash
    assert result.conclusion  # non-empty after fallback
