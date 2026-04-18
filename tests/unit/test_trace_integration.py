"""Tests using the minimal fixture trace to verify real trace integration."""

from pathlib import Path

import pytest

FIXTURE_TRACE = str(
    Path(__file__).parent.parent / "fixtures" / "traces" / "minimal.perfetto-trace"
)


@pytest.fixture()
def trace_session():
    from tracelens.trace.processor import load_trace

    session = load_trace(FIXTURE_TRACE)
    yield session
    session.close()


class TestTraceSession:
    def test_load_and_query_processes(self, trace_session):
        rows = trace_session.query("select pid, name from process where pid > 0 order by pid")
        names = {r["name"] for r in rows}
        assert "com.example.app" in names
        assert "system_server" in names

    def test_query_guard_blocks_disallowed_table(self, trace_session):
        from tracelens.trace.processor import TraceQueryError

        with pytest.raises(TraceQueryError, match="disallowed table"):
            trace_session.query("select * from sqlite_master")


class TestQueries:
    def test_get_processes(self, trace_session):
        from tracelens.trace.queries import get_processes

        procs = get_processes(trace_session)
        assert any(p["name"] == "com.example.app" for p in procs)

    def test_get_threads_for_process(self, trace_session):
        from tracelens.trace.queries import get_threads_for_process

        threads = get_threads_for_process(trace_session, 1000)
        names = {t["thread_name"] for t in threads if t["thread_name"]}
        assert "main" in names
        assert "RenderThread" in names

    def test_get_slices_for_process(self, trace_session):
        from tracelens.trace.queries import get_slices_for_process

        slices = get_slices_for_process(trace_session, 1000)
        names = {s["name"] for s in slices}
        assert "inflate" in names
        assert "performTraversals" in names

    def test_get_thread_states(self, trace_session):
        from tracelens.trace.queries import get_thread_states_for_process

        states = get_thread_states_for_process(trace_session, 1000)
        assert len(states) > 0
        state_values = {s["state"] for s in states}
        assert "Running" in state_values


class TestOrchestratorWithTrace:
    def test_analyze_with_real_trace(self, trace_session):
        from tracelens.agent.orchestrator import Orchestrator
        from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
        from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill

        orch = Orchestrator(
            window_skill=AbnormalWindowsSkill(),
            process_thread_skill=ProcessThreadDiscoverySkill(),
        )
        result = orch.analyze(
            scenario="mode switch stutters",
            focused_process="com.example.app",
            trace_session=trace_session,
        )

        assert result.conclusion
        assert len(result.key_evidence) >= 1
        assert len(result.analysis_chain) >= 3
        # Should find the 50ms inflate slice
        evidence_text = " ".join(e.summary for e in result.key_evidence)
        assert "inflate" in evidence_text

    def test_analyze_without_focused_process(self, trace_session):
        from tracelens.agent.orchestrator import Orchestrator
        from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
        from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill

        orch = Orchestrator(
            window_skill=AbnormalWindowsSkill(),
            process_thread_skill=ProcessThreadDiscoverySkill(),
        )
        result = orch.analyze(
            scenario="general jank",
            trace_session=trace_session,
        )

        # Should still produce a result by inferring the focused process
        assert result.conclusion
        assert len(result.key_evidence) >= 1
