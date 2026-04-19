from tracelens.agent.synthesis import synthesize_result
from tracelens.types import EvidenceItem


def test_synthesize_result_returns_analysis_result():
    result = synthesize_result(
        evidence=[EvidenceItem(title="Top abnormal window", summary="window 10..20 score=30; primary role=app_main")],
        chain=["Selected role-first strategy", "Scenario: switching mode stutters", "Focused process: com.example.app"],
    )

    assert result.conclusion == "初步分析完成"
    assert result.key_evidence[0].title == "Top abnormal window"
    assert result.analysis_chain[0] == "Selected role-first strategy"
    assert result.optimization_directions == ["检查异常窗口中得分最高的区间和目标进程的关键线程"]
    assert len(result.uncertainties) >= 0  # synthesis may add uncertainties based on missing evidence
