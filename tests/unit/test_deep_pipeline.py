"""Deep tests for the core analysis pipeline: orchestrator → skills → evidence → synthesis → verification."""

from pathlib import Path

import pytest

from tracelens.agent.orchestrator import Orchestrator
from tracelens.agent.planner import generate_plan, AnalysisPlan
from tracelens.agent.synthesis import synthesize_result
from tracelens.agent.verifier import verify_result, apply_corrections
from tracelens.llm import LLMMessage
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill
from tracelens.skills.yaml_engine import SkillRegistry, execute_skill
from tracelens.trace.processor import load_trace, TraceQueryError
from tracelens.types import AnalysisResult, EvidenceItem

JANK_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "jank_example.perfetto-trace")
FLUTTER_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "flutter_app.perfetto-trace")
STARTUP_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "heavy_startup.perfetto-trace")
CPU_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "cpu_contention.perfetto-trace")


# ============================================================
# Orchestrator end-to-end: trace → evidence → conclusion
# ============================================================

class TestOrchestratorEndToEnd:
    def _run(self, trace_path: str, scenario: str, process: str | None = None) -> AnalysisResult:
        with load_trace(trace_path) as session:
            orch = Orchestrator(
                window_skill=AbnormalWindowsSkill(),
                process_thread_skill=ProcessThreadDiscoverySkill(),
            )
            return orch.analyze(scenario=scenario, focused_process=process, trace_session=session)

    def test_jank_trace_finds_long_slices(self):
        result = self._run(JANK_TRACE, "滑动卡顿")
        titles = {e.title for e in result.key_evidence}
        assert "Long slices" in titles
        long_ev = next(e for e in result.key_evidence if e.title == "Long slices")
        assert "Choreographer#doFrame" in long_ev.summary

    def test_jank_trace_identifies_app_main(self):
        result = self._run(JANK_TRACE, "卡顿", "com.example.launcher")
        assert any("app_main" in step for step in result.analysis_chain)

    def test_flutter_trace_identifies_flutter_ui(self):
        result = self._run(FLUTTER_TRACE, "Flutter滑动卡顿")
        assert any("flutter_ui" in step for step in result.analysis_chain)

    def test_startup_trace_finds_bind_application(self):
        result = self._run(STARTUP_TRACE, "冷启动慢", "com.example.heavyapp")
        titles = {e.title for e in result.key_evidence}
        assert "Long slices" in titles
        long_ev = next(e for e in result.key_evidence if e.title == "Long slices")
        assert "bindApplication" in long_ev.summary

    def test_cpu_trace_finds_scheduling_delay(self):
        result = self._run(CPU_TRACE, "后台计算卡顿", "com.example.compute")
        titles = {e.title for e in result.key_evidence}
        assert "Scheduling delay" in titles

    def test_result_has_all_required_fields(self):
        result = self._run(JANK_TRACE, "test")
        assert result.conclusion
        assert len(result.key_evidence) > 0
        assert len(result.analysis_chain) > 0
        assert len(result.optimization_directions) > 0

    def test_nonexistent_process_still_returns_result(self):
        result = self._run(JANK_TRACE, "test", "com.nonexistent.app")
        # Should fall back to inferred process, not crash
        assert result.conclusion


# ============================================================
# Planner: scene classification
# ============================================================

class TestPlannerSceneRouting:
    def test_scrolling_keywords_select_frame_first(self):
        registry = SkillRegistry()
        plan = generate_plan("列表滑动掉帧", True, registry)
        assert plan.strategy == "frame-first"
        assert "frame_rhythm" in plan.skill_ids

    def test_startup_keywords_select_window_first(self):
        registry = SkillRegistry()
        plan = generate_plan("应用冷启动慢", True, registry)
        assert plan.strategy == "window-first"

    def test_generic_scenario_with_process(self):
        registry = SkillRegistry()
        plan = generate_plan("performance issue", True, registry)
        assert plan.strategy == "role-first"

    def test_generic_scenario_without_process(self):
        registry = SkillRegistry()
        plan = generate_plan("performance issue", False, registry)
        assert plan.strategy == "window-first"

    def test_plan_only_contains_valid_skill_ids(self):
        registry = SkillRegistry()
        plan = generate_plan("滑动卡顿", True, registry)
        for sid in plan.skill_ids:
            assert registry.get(sid) is not None, f"Skill {sid} not in registry"


# ============================================================
# YAML Skill error handling
# ============================================================

class TestSkillErrorPaths:
    def test_missing_required_param_reports_error(self):
        registry = SkillRegistry()
        skill = registry.get("long_task_detection")
        with load_trace(JANK_TRACE) as session:
            result = execute_skill(skill, session, {})  # missing pid
        assert len(result.errors) > 0

    def test_skill_with_no_matching_data(self):
        registry = SkillRegistry()
        skill = registry.get("binder_analysis")
        # minimal trace has no binder slices
        minimal = str(Path(__file__).parent.parent / "fixtures" / "traces" / "minimal.perfetto-trace")
        with load_trace(minimal) as session:
            result = execute_skill(skill, session, {"pid": 1000})
        assert not result.errors
        # Should return empty results, not crash
        assert result.step_results.get("binder_calls") == [] or result.step_results.get("binder_summary") == []


# ============================================================
# Trace processor error handling
# ============================================================

class TestTraceProcessorErrors:
    def test_disallowed_table_raises(self):
        with load_trace(JANK_TRACE) as session:
            with pytest.raises(TraceQueryError, match="disallowed table"):
                session.query("select * from sqlite_master")

    def test_multiple_statements_raises(self):
        with load_trace(JANK_TRACE) as session:
            with pytest.raises(TraceQueryError, match="multiple statements"):
                session.query("select 1; select 2")

    def test_context_manager_closes_cleanly(self):
        session = load_trace(JANK_TRACE)
        session.close()
        # Should not raise on double close
        session.close()


# ============================================================
# Synthesis with verification integration
# ============================================================

class TestSynthesisVerification:
    def test_hallucinated_numbers_flagged(self):
        """If LLM produces numbers not in evidence, verifier should catch it."""
        result = AnalysisResult(
            conclusion="Thread blocked for 999ms causing 47 frame drops",
            key_evidence=[EvidenceItem(title="Blocked threads", summary="main: total=35ms")],
            analysis_chain=["step 1"],
            optimization_directions=["fix it"],
            uncertainties=[],
        )
        report = verify_result(result)
        corrected = apply_corrections(result, report)
        assert any("[Verification]" in u for u in corrected.uncertainties)

    def test_clean_result_not_modified(self):
        result = AnalysisResult(
            conclusion="Main thread blocked for 35ms",
            key_evidence=[EvidenceItem(title="Blocked threads", summary="main: total=35ms")],
            analysis_chain=["step 1"],
            optimization_directions=["Reduce blocking"],
            uncertainties=[],
        )
        report = verify_result(result)
        corrected = apply_corrections(result, report)
        assert corrected.uncertainties == []

    def test_llm_fallback_on_error(self):
        """Synthesis should fall back to rules if LLM raises."""
        class BrokenLLM:
            def chat(self, messages):
                raise RuntimeError("timeout")

        evidence = [EvidenceItem(title="Long slices", summary="inflate=50ms")]
        result = synthesize_result(evidence=evidence, chain=["step"], llm=BrokenLLM(), scenario="test")
        assert result.conclusion  # Should not crash
        assert "长耗时" in result.conclusion or "long slices" in result.conclusion.lower()
