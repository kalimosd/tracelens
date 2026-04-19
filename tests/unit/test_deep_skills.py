"""Tests for deep analysis YAML skills: per_frame, waker_chain, binder."""

from pathlib import Path

import pytest

from tracelens.skills.yaml_engine import SkillRegistry, execute_skill

JANK_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "jank_example.perfetto-trace")
MULTI_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "multi_process.perfetto-trace")
STARTUP_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "heavy_startup.perfetto-trace")


@pytest.fixture()
def registry():
    return SkillRegistry()


@pytest.fixture()
def jank_session():
    from tracelens.trace.processor import load_trace
    s = load_trace(JANK_TRACE)
    yield s
    s.close()


@pytest.fixture()
def multi_session():
    from tracelens.trace.processor import load_trace
    s = load_trace(MULTI_TRACE)
    yield s
    s.close()


@pytest.fixture()
def startup_session():
    from tracelens.trace.processor import load_trace
    s = load_trace(STARTUP_TRACE)
    yield s
    s.close()


class TestPerFrameAnalysis:
    def test_finds_frames(self, registry, jank_session):
        skill = registry.get("per_frame_analysis")
        result = execute_skill(skill, jank_session, {"pid": 2000})
        assert not result.errors
        frames = result.step_results["frame_list"]
        assert len(frames) > 0
        # Should be sorted by duration desc
        assert frames[0]["dur_ms"] >= frames[-1]["dur_ms"]

    def test_frame_thread_state_for_jank_frames(self, registry, jank_session):
        skill = registry.get("per_frame_analysis")
        result = execute_skill(skill, jank_session, {"pid": 2000})
        states = result.step_results.get("frame_thread_state", [])
        # Jank trace has frames > 16ms, so should have state breakdown
        assert len(states) > 0


class TestWakerChain:
    def test_skill_exists(self, registry):
        assert registry.get("waker_chain") is not None

    def test_runs_without_error(self, registry, jank_session):
        skill = registry.get("waker_chain")
        result = execute_skill(skill, jank_session, {"pid": 2000})
        assert not result.errors


class TestBinderAnalysis:
    def test_finds_binder_calls(self, registry, multi_session):
        skill = registry.get("binder_analysis")
        result = execute_skill(skill, multi_session, {"pid": 5000})
        assert not result.errors
        summary = result.step_results.get("binder_summary", [])
        assert len(summary) > 0
        assert summary[0]["call_count"] > 0

    def test_binder_in_startup(self, registry, startup_session):
        skill = registry.get("binder_analysis")
        result = execute_skill(skill, startup_session, {"pid": 4000})
        assert not result.errors
        calls = result.step_results.get("binder_calls", [])
        assert len(calls) > 0


def test_registry_has_10_skills(registry):
    assert registry.count == 10
