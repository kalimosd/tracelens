"""Tests for the YAML skill engine."""

from pathlib import Path

import pytest

from tracelens.skills.yaml_engine import (
    SkillDefinition,
    SkillRegistry,
    _substitute_params,
    execute_skill,
)

FIXTURE_TRACE = str(
    Path(__file__).parent.parent / "fixtures" / "traces" / "minimal.perfetto-trace"
)


def test_substitute_params_basic():
    sql = "SELECT * FROM process WHERE pid = ${pid}"
    assert _substitute_params(sql, {"pid": 1000}) == "SELECT * FROM process WHERE pid = 1000"


def test_substitute_params_with_default():
    sql = "WHERE dur > ${threshold_ms|16} * 1000000"
    assert "16" in _substitute_params(sql, {})


def test_substitute_params_missing_raises():
    with pytest.raises(ValueError, match="Missing required parameter"):
        _substitute_params("WHERE pid = ${pid}", {})


def test_registry_loads_definitions():
    registry = SkillRegistry()
    assert registry.count >= 7
    assert registry.get("thread_state_distribution") is not None
    assert registry.get("long_task_detection") is not None
    assert registry.get("scheduling_delay") is not None
    assert registry.get("blocking_chain") is not None
    assert registry.get("frame_rhythm") is not None


def test_registry_list_by_category():
    registry = SkillRegistry()
    scrolling = registry.list_skills(category="scrolling")
    assert any(s.id == "frame_rhythm" for s in scrolling)
    general = registry.list_skills(category="general")
    assert any(s.id == "long_task_detection" for s in general)


def test_skill_definition_from_yaml():
    path = Path(__file__).parent.parent.parent / "tracelens" / "skills" / "definitions" / "long_task_detection.yaml"
    skill = SkillDefinition.from_yaml(path)
    assert skill.id == "long_task_detection"
    assert len(skill.steps) == 1
    assert "${pid}" in skill.steps[0].sql


@pytest.fixture()
def trace_session():
    from tracelens.trace.processor import load_trace
    session = load_trace(FIXTURE_TRACE)
    yield session
    session.close()


def test_execute_skill_thread_state(trace_session):
    registry = SkillRegistry()
    skill = registry.get("thread_state_distribution")
    result = execute_skill(skill, trace_session, {"pid": 1000})
    assert not result.errors
    rows = result.step_results["state_distribution"]
    assert len(rows) > 0
    states = {r["state"] for r in rows}
    assert "Running" in states


def test_execute_skill_long_task(trace_session):
    registry = SkillRegistry()
    skill = registry.get("long_task_detection")
    result = execute_skill(skill, trace_session, {"pid": 1000})
    assert not result.errors
    rows = result.step_results["long_slices"]
    # minimal trace has a 50ms inflate slice
    assert any(r["name"] == "inflate" for r in rows)


def test_execute_skill_scheduling_delay(trace_session):
    registry = SkillRegistry()
    skill = registry.get("scheduling_delay")
    result = execute_skill(skill, trace_session, {"pid": 1000})
    assert not result.errors


def test_execute_skill_process_overview(trace_session):
    registry = SkillRegistry()
    skill = registry.get("process_overview")
    result = execute_skill(skill, trace_session, {"pid": 1000})
    assert not result.errors
    overview = result.step_results["overview"][0]
    assert overview["thread_count"] >= 2
    assert overview["slice_count"] >= 3
