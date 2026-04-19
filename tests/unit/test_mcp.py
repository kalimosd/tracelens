"""Tests for MCP server tools."""

import json
from pathlib import Path

import pytest

JANK_TRACE = str(Path(__file__).parent.parent / "fixtures" / "traces" / "jank_example.perfetto-trace")


@pytest.fixture(autouse=True)
def _clean_sessions():
    from tracelens.mcp import _sessions
    _sessions.clear()
    yield
    # Close any remaining sessions
    for s in list(_sessions.values()):
        s.close()
    _sessions.clear()


def test_load_trace_file():
    from tracelens.mcp import load_trace_file
    result = json.loads(load_trace_file(JANK_TRACE))
    assert result["status"] == "loaded"
    assert "trace_id" in result


def test_list_skills():
    from tracelens.mcp import list_skills
    result = json.loads(list_skills())
    assert len(result) >= 10
    ids = {s["id"] for s in result}
    assert "long_task_detection" in ids
    assert "waker_chain" in ids


def test_list_skills_by_category():
    from tracelens.mcp import list_skills
    result = json.loads(list_skills(category="scrolling"))
    assert all(s["category"] == "scrolling" for s in result)


def test_analyze():
    from tracelens.mcp import analyze, load_trace_file
    trace_id = json.loads(load_trace_file(JANK_TRACE))["trace_id"]
    result = json.loads(analyze(trace_id, scenario="滑动卡顿"))
    assert "session_id" in result
    assert result["conclusion"]
    assert len(result["evidence"]) > 0


def test_invoke_skill():
    from tracelens.mcp import invoke_skill, load_trace_file
    trace_id = json.loads(load_trace_file(JANK_TRACE))["trace_id"]
    result = json.loads(invoke_skill(trace_id, "long_task_detection", pid=2000))
    assert not result["errors"]
    assert "long_slices" in result["step_results"]


def test_execute_sql():
    from tracelens.mcp import execute_sql, load_trace_file
    trace_id = json.loads(load_trace_file(JANK_TRACE))["trace_id"]
    result = json.loads(execute_sql(trace_id, "select pid, name from process where pid > 0"))
    assert result["row_count"] >= 2


def test_execute_sql_blocked():
    from tracelens.mcp import execute_sql, load_trace_file
    trace_id = json.loads(load_trace_file(JANK_TRACE))["trace_id"]
    result = json.loads(execute_sql(trace_id, "select * from sqlite_master"))
    assert "error" in result


def test_followup():
    from tracelens.mcp import analyze, followup, load_trace_file
    trace_id = json.loads(load_trace_file(JANK_TRACE))["trace_id"]
    session_id = json.loads(analyze(trace_id, scenario="test"))["session_id"]
    result = json.loads(followup(session_id, "为什么卡顿？"))
    assert "answer" in result


def test_close_trace():
    from tracelens.mcp import close_trace, load_trace_file
    trace_id = json.loads(load_trace_file(JANK_TRACE))["trace_id"]
    result = json.loads(close_trace(trace_id))
    assert result["status"] == "closed"


def test_error_on_missing_trace():
    from tracelens.mcp import analyze
    result = json.loads(analyze("nonexistent", scenario="test"))
    assert "error" in result
