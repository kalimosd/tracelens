from tracelens.artifacts.store import InMemoryArtifactStore
from tracelens.types import AnalysisResult, EvidenceItem


def test_artifact_store_saves_and_loads_analysis_result():
    store = InMemoryArtifactStore()
    result = AnalysisResult(
        conclusion="初步分析完成",
        key_evidence=[EvidenceItem(title="Top abnormal window", summary="window 10..20 score=31; primary role=app_main")],
        analysis_chain=["Selected role-first strategy"],
        optimization_directions=["检查异常窗口中得分最高的区间和目标进程的关键线程"],
        uncertainties=[],
    )

    session_id = store.save(result)
    loaded = store.load(session_id)

    assert loaded == result
