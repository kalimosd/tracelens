from tracelens.types import AnalysisResult


def to_result_view_model(result: AnalysisResult) -> dict[str, object]:
    return {
        "conclusion": result.conclusion,
        "key_evidence": result.key_evidence,
        "analysis_chain": result.analysis_chain,
        "optimization_directions": result.optimization_directions,
        "uncertainties": result.uncertainties,
    }
