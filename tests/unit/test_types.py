from tracelens.types import AnalysisResult, EvidenceItem


def test_analysis_result_requires_core_sections():
    result = AnalysisResult(
        conclusion="main thread blocked",
        key_evidence=[EvidenceItem(title="long task", summary="42ms on main thread")],
        analysis_chain=["detected abnormal window", "found long task on main thread"],
        optimization_directions=["reduce synchronous work on main thread"],
        uncertainties=[],
    )

    assert result.conclusion == "main thread blocked"
    assert result.key_evidence[0].title == "long task"
    assert result.analysis_chain == ["detected abnormal window", "found long task on main thread"]
    assert result.optimization_directions == ["reduce synchronous work on main thread"]
    assert result.uncertainties == []
