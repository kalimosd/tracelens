"""TraceLens MCP Server — exposes trace analysis capabilities via Model Context Protocol."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from tracelens.agent.followup import answer_followup
from tracelens.agent.orchestrator import Orchestrator
from tracelens.artifacts.store import InMemoryArtifactStore
from tracelens.config import get_settings
from tracelens.llm.factory import create_llm_client
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill
from tracelens.skills.yaml_engine import SkillRegistry, execute_skill
from tracelens.trace.processor import TraceSession, load_trace

mcp = FastMCP(
    "TraceLens",
    instructions="Perfetto trace analysis agent for Android/Flutter performance investigations. "
    "Use load_trace_file first, then analyze or invoke_skill to investigate performance issues.",
)

# Global state
_sessions: dict[str, TraceSession] = {}
_store = InMemoryArtifactStore()
_registry = SkillRegistry()
_settings = get_settings()
_llm = create_llm_client(_settings)


@mcp.tool(description="Load a Perfetto trace file and return a trace_id for subsequent queries")
def load_trace_file(path: str) -> str:
    """Load a .perfetto-trace file. Returns a trace_id to use with other tools."""
    import uuid

    trace_id = str(uuid.uuid4())[:8]
    _sessions[trace_id] = load_trace(path)
    return json.dumps({"trace_id": trace_id, "status": "loaded"})


@mcp.tool(description="Run a full TraceLens analysis on a loaded trace")
def analyze(trace_id: str, scenario: str, process: str = "") -> str:
    """Run full analysis pipeline. Returns structured result with evidence and conclusions."""
    session = _sessions.get(trace_id)
    if session is None:
        return json.dumps({"error": f"trace_id '{trace_id}' not found. Call load_trace_file first."})

    orchestrator = Orchestrator(
        window_skill=AbnormalWindowsSkill(),
        process_thread_skill=ProcessThreadDiscoverySkill(),
        llm=_llm,
    )
    result = orchestrator.analyze(
        scenario=scenario,
        focused_process=process or None,
        trace_session=session,
    )
    session_id = _store.save(result)

    return json.dumps({
        "session_id": session_id,
        "conclusion": result.conclusion,
        "evidence": [{"title": e.title, "summary": e.summary} for e in result.key_evidence],
        "analysis_chain": result.analysis_chain,
        "optimization_directions": result.optimization_directions,
        "uncertainties": result.uncertainties,
    }, ensure_ascii=False)


@mcp.tool(description="List available analysis skills, optionally filtered by category")
def list_skills(category: str = "") -> str:
    """List available YAML skills. Categories: scrolling, general, startup."""
    skills = _registry.list_skills(category=category or None)
    return json.dumps([
        {"id": s.id, "name": s.name, "description": s.description, "category": s.category}
        for s in skills
    ], ensure_ascii=False)


@mcp.tool(description="Execute a specific analysis skill on a loaded trace")
def invoke_skill(trace_id: str, skill_id: str, pid: int, extra_params: str = "{}") -> str:
    """Execute a YAML skill by ID. Returns structured results."""
    session = _sessions.get(trace_id)
    if session is None:
        return json.dumps({"error": f"trace_id '{trace_id}' not found"})

    skill = _registry.get(skill_id)
    if skill is None:
        return json.dumps({"error": f"skill '{skill_id}' not found"})

    params: dict[str, Any] = {"pid": pid}
    if extra_params and extra_params != "{}":
        params.update(json.loads(extra_params))

    result = execute_skill(skill, session, params)

    return json.dumps({
        "skill_id": skill_id,
        "step_results": {k: v[:50] for k, v in result.step_results.items()},  # cap rows
        "errors": result.errors,
    }, ensure_ascii=False, default=str)


@mcp.tool(description="Execute a SQL query on a loaded trace (with safety guards)")
def execute_sql(trace_id: str, sql: str) -> str:
    """Execute a SQL query against trace_processor. Subject to table whitelist and row limits."""
    session = _sessions.get(trace_id)
    if session is None:
        return json.dumps({"error": f"trace_id '{trace_id}' not found"})

    try:
        rows = session.query(sql)
        return json.dumps({
            "row_count": len(rows),
            "rows": rows[:100],  # cap at 100 rows
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(description="Ask a follow-up question about a previous analysis")
def followup(session_id: str, question: str) -> str:
    """Ask a follow-up question based on existing analysis results."""
    result = _store.load(session_id)
    if result is None:
        return json.dumps({"error": f"session '{session_id}' not found"})

    answer = answer_followup(question=question, result=result, llm=_llm)
    return json.dumps({"question": question, "answer": answer}, ensure_ascii=False)


@mcp.tool(description="Close a loaded trace and free resources")
def close_trace(trace_id: str) -> str:
    """Close a trace session and free resources."""
    session = _sessions.pop(trace_id, None)
    if session is None:
        return json.dumps({"error": f"trace_id '{trace_id}' not found"})
    session.close()
    return json.dumps({"status": "closed"})
