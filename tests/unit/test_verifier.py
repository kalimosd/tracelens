from tracelens.agent.verifier import apply_corrections, verify_result
from tracelens.types import AnalysisResult, EvidenceItem


def _make_result(**overrides) -> AnalysisResult:
    defaults = {
        "conclusion": "Analysis complete",
        "key_evidence": [EvidenceItem(title="Long slices", summary="inflate=50ms")],
        "analysis_chain": ["step 1"],
        "optimization_directions": ["fix it"],
        "uncertainties": [],
    }
    defaults.update(overrides)
    return AnalysisResult(**defaults)


def test_clean_result_passes():
    result = _make_result()
    report = verify_result(result)
    assert not report.has_issues


def test_single_frame_critical_caught():
    result = _make_result(conclusion="CRITICAL: single frame anomaly detected, 单帧异常严重")
    report = verify_result(result)
    assert any(f.rule == "single_frame_critical" for f in report.findings)


def test_buffer_stuffing_as_app_jank_caught():
    result = _make_result(
        key_evidence=[EvidenceItem(title="Frame analysis", summary="App jank: Buffer Stuffing detected, 5 frames 掉帧")]
    )
    report = verify_result(result)
    assert any(f.rule == "buffer_stuffing_as_app_jank" for f in report.findings)


def test_vsync_offset_critical_caught():
    result = _make_result(
        conclusion="CRITICAL: VSync timing issue",
        key_evidence=[EvidenceItem(title="VSync", summary="VSync offset detected ±0.3ms")],
    )
    report = verify_result(result)
    assert any(f.rule == "vsync_offset_critical" for f in report.findings)


def test_sleeping_severity_caught():
    result = _make_result(
        conclusion="LOW severity: minor thread blocking",
        key_evidence=[EvidenceItem(title="Thread state distribution", summary="Running=100ms, S=200ms, R=10ms")],
    )
    report = verify_result(result)
    assert any(f.rule == "sleeping_severity" for f in report.findings)


def test_sleeping_severity_ok_when_low_ratio():
    result = _make_result(
        conclusion="LOW severity issue",
        key_evidence=[EvidenceItem(title="Thread state distribution", summary="Running=200ms, S=50ms, R=10ms")],
    )
    report = verify_result(result)
    assert not any(f.rule == "sleeping_severity" for f in report.findings)


def test_hallucinated_numbers_caught():
    result = _make_result(
        conclusion="Main thread blocked for 999ms causing 47 frame drops",
        key_evidence=[EvidenceItem(title="Blocked threads", summary="main: total=35ms, count=3")],
    )
    report = verify_result(result)
    assert any(f.rule == "no_evidence_for_claim" for f in report.findings)


def test_hallucinated_numbers_ok_when_matching():
    result = _make_result(
        conclusion="Main thread blocked for 35ms",
        key_evidence=[EvidenceItem(title="Blocked threads", summary="main: total=35ms")],
    )
    report = verify_result(result)
    assert not any(f.rule == "no_evidence_for_claim" for f in report.findings)


def test_empty_evidence_with_conclusion_caught():
    result = _make_result(conclusion="Severe jank detected", key_evidence=[])
    report = verify_result(result)
    assert any(f.rule == "empty_evidence_with_conclusion" for f in report.findings)


def test_directions_without_evidence_caught():
    result = _make_result(
        key_evidence=[EvidenceItem(title="Long slices", summary="inflate=50ms")],
        optimization_directions=["Check cross-process binder latency"],
    )
    report = verify_result(result)
    assert any(f.rule == "directions_without_evidence" for f in report.findings)


def test_apply_corrections_adds_to_uncertainties():
    result = _make_result(conclusion="CRITICAL: single frame anomaly")
    report = verify_result(result)
    corrected = apply_corrections(result, report)
    assert any("[Verification]" in u for u in corrected.uncertainties)
    assert any("Verification:" in step for step in corrected.analysis_chain)
