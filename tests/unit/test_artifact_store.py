from tracelens.artifacts.store import InMemoryArtifactStore
from tracelens.types import AnalysisResult, EvidenceItem


def test_artifact_store_saves_and_loads_analysis_result():
    store = InMemoryArtifactStore()
    result = AnalysisResult(
        conclusion="initial analysis ready",
        key_evidence=[EvidenceItem(title="Top abnormal window", summary="window 10..20 score=31; primary role=app_main")],
        analysis_chain=["Selected role-first strategy"],
        optimization_directions=["Inspect the highest-scoring window and focused process threads first"],
        uncertainties=[],
    )

    session_id = store.save(result)
    loaded = store.load(session_id)

    assert loaded == result
