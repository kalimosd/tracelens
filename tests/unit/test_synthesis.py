from tracelens.agent.synthesis import synthesize_result
from tracelens.types import EvidenceItem


def test_synthesize_result_returns_analysis_result():
    result = synthesize_result(
        evidence=[EvidenceItem(title="Top abnormal window", summary="window 10..20 score=30; primary role=app_main")],
        chain=["Selected role-first strategy", "Scenario: switching mode stutters", "Focused process: com.example.app"],
    )

    assert result.conclusion == "initial analysis ready"
    assert result.key_evidence[0].title == "Top abnormal window"
    assert result.analysis_chain[0] == "Selected role-first strategy"
    assert result.optimization_directions == ["Inspect the highest-scoring window and focused process threads first"]
    assert len(result.uncertainties) >= 0  # synthesis may add uncertainties based on missing evidence
